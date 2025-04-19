CREATE TABLE teams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
);

CREATE TABLE games (
    id SERIAL PRIMARY KEY,
    home_team_id INTEGER REFERENCES teams(id),
    away_team_id INTEGER REFERENCES teams(id),
    start_time TIMESTAMP
);

CREATE TABLE odds (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id),
    bookmaker VARCHAR(255),
    market_type VARCHAR(255),
    value DECIMAL
);

CREATE TABLE odds_history (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id),
    bookmaker VARCHAR(255),
    market_type VARCHAR(255),
    value DECIMAL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);