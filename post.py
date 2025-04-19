import requests
import psycopg2
import schedule
import time
from datetime import datetime
import json

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1363246183761580094/8_w4mrDjBopAMF9GJcI32xwCcY-LdSdI5OTq8828BYdfw9Lg9H3N101TIvBCknUFdGXy"

API_KEY = "133e5899443071bce3c2b7002ab8243a"
MARKET = "outrights"

SPORTS = [
    "basketball_nba_championship_winner",
    "americanfootball_nfl_super_bowl_winner",
    "soccer_fifa_world_cup_winner"
]

def send_discord_alert(message):
    try:
        payload = {"content": message}
        requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except Exception as e:
        print(f"Discord notification failed: {e}")

class OddFetcher:
    def __init__(self, api_key, sport, market="outrights"):
        self.api_key = api_key
        self.sport = sport
        self.market = market

    def fetch_odds(self):
        url = f"https://api.the-odds-api.com/v4/sports/{self.sport}/odds"
        params = {
            "api_key": self.api_key,
            "regions": "us",
            "markets": self.market,
            "oddsFormat": "decimal"
        }

        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching {self.sport}: {e}")
            return []

class DatabaseService:
    def __init__(self, dbname, user, password, host, port):
        self.conn = psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)
        self.cursor = self.conn.cursor()

    def insert_team(self, team_name):
        self.cursor.execute(
            "INSERT INTO teams (name) VALUES (%s) ON CONFLICT (name) DO NOTHING;",
            (team_name,)
        )

    def insert_game(self, home, away, start_time):
        self.cursor.execute("""
            INSERT INTO games (home_team_id, away_team_id, start_time)
            VALUES (
                (SELECT id FROM teams WHERE name = %s),
                (SELECT id FROM teams WHERE name = %s),
                %s
            )
            ON CONFLICT DO NOTHING RETURNING id;
        """, (home, away, start_time))
        result = self.cursor.fetchone()
        if result:
            return result[0]
        else:
            self.cursor.execute("""
                SELECT id FROM games
                WHERE home_team_id = (SELECT id FROM teams WHERE name = %s)
                AND away_team_id = (SELECT id FROM teams WHERE name = %s)
                AND start_time = %s;
            """, (home, away, start_time))
            return self.cursor.fetchone()[0]

    def insert_odds(self, game_id, bookmaker, market_type, value):
        self.cursor.execute("""
            INSERT INTO odds (game_id, bookmaker, market_type, value)
            VALUES (%s, %s, %s, %s);
        """, (game_id, bookmaker, market_type, value))

    def get_last_odds(self, game_id, bookmaker, market_type):
        self.cursor.execute("""
            SELECT value FROM odds_history
            WHERE game_id = %s AND bookmaker = %s AND market_type = %s
            ORDER BY last_updated DESC LIMIT 1;
        """, (game_id, bookmaker, market_type))
        result = self.cursor.fetchone()
        return result[0] if result else None

    def update_odds_history(self, game_id, bookmaker, market_type, value):
        self.cursor.execute("""
            INSERT INTO odds_history (game_id, bookmaker, market_type, value)
            VALUES (%s, %s, %s, %s);
        """, (game_id, bookmaker, market_type, value))

    def commit_and_close(self):
        self.conn.commit()
        self.cursor.close()
        self.conn.close()

class OddsTracker:
    def __init__(self, sports, fetcher_class, db_service):
        self.sports = sports
        self.fetcher_class = fetcher_class
        self.db = db_service

    def run(self):
        for sport in self.sports:
            print(f"Getting data for: {sport}")
            fetcher = self.fetcher_class(API_KEY, sport)
            events = fetcher.fetch_odds()
            if not events:
                print(f"No data for {sport}")
                continue

            for event in events:
                for bookmaker in event.get("bookmakers", []):
                    book_name = bookmaker.get("title", "")
                    for market in bookmaker.get("markets", []):
                        market_type = market.get("key", "")
                        for outcome in market.get("outcomes", []):
                            try:
                                name = outcome.get("name")
                                price = float(outcome.get("price"))
                                self.db.insert_team(name)
                                game_id = self.db.insert_game(name, name, event.get("commence_time", "2099-01-01T00:00:00Z"))

                                # Detect changes
                                previous = self.db.get_last_odds(game_id, book_name, market_type)
                                if previous:
                                    previous = float(previous)
                                    change = abs(price - previous) / previous
                                    if change > 0.05:
                                        msg = f"Odds changed for {name}: {previous:.2f} → {price:.2f}"
                                        print(msg)
                                        send_discord_alert(msg)
                                else:
                                    print(f"New odds for {name}: {price}")

                                self.db.insert_odds(game_id, book_name, market_type, price)
                                self.db.update_odds_history(game_id, book_name, market_type, price)

                            except Exception as e:
                                print(f"Failed to process outcome: {e}")

# Scheduler
if __name__ == "__main__":
    def job():
        db_service = DatabaseService("postgres", "postgres", "1234", "localhost", "5432")
        tracker = OddsTracker(SPORTS, OddFetcher, db_service)
        tracker.run()
        db_service.commit_and_close()
        print(f"Complete at {datetime.now()}")

    job()
    schedule.every(10).minutes.do(job)
    print("Polling started. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(1)
