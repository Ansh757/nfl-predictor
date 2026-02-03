-- NFL Teams Database Initialization
-- This file runs automatically when PostgreSQL container starts for the first time
DROP VIEW IF EXISTS games_with_teams;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create teams table with fixed IDs for consistency
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY,  -- Fixed IDs, not SERIAL
    name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,
    abbreviation VARCHAR(10) NOT NULL UNIQUE,
    conference VARCHAR(10) NOT NULL CHECK (conference IN ('AFC', 'NFC')),
    division VARCHAR(10) NOT NULL CHECK (division IN ('North', 'South', 'East', 'West')),
    logo_url VARCHAR(255),
    primary_color VARCHAR(7),
    secondary_color VARCHAR(7),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert all 32 NFL teams with consistent IDs (matching common NFL API standards)
-- AFC East
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(2, 'Bills', 'Buffalo', 'BUF', 'AFC', 'East', '#00338D', '#C60C30'),
(15, 'Dolphins', 'Miami', 'MIA', 'AFC', 'East', '#008E97', '#FC4C02'),
(17, 'Patriots', 'New England', 'NE', 'AFC', 'East', '#002244', '#C60C30'),
(20, 'Jets', 'New York', 'NYJ', 'AFC', 'East', '#125740', '#FFFFFF');

-- AFC North  
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(31, 'Ravens', 'Baltimore', 'BAL', 'AFC', 'North', '#241773', '#000000'),
(4, 'Bengals', 'Cincinnati', 'CIN', 'AFC', 'North', '#FB4F14', '#000000'),
(5, 'Browns', 'Cleveland', 'CLE', 'AFC', 'North', '#311D00', '#FF3C00'),
(23, 'Steelers', 'Pittsburgh', 'PIT', 'AFC', 'North', '#FFB612', '#101820');

-- AFC South
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(32, 'Texans', 'Houston', 'HOU', 'AFC', 'South', '#03202F', '#A71930'),
(11, 'Colts', 'Indianapolis', 'IND', 'AFC', 'South', '#002C5F', '#A2AAAD'),
(30, 'Jaguars', 'Jacksonville', 'JAX', 'AFC', 'South', '#101820', '#D7A22A'),
(10, 'Titans', 'Tennessee', 'TEN', 'AFC', 'South', '#0C2340', '#4B92DB');

-- AFC West
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(7, 'Broncos', 'Denver', 'DEN', 'AFC', 'West', '#FB4F14', '#002244'),
(12, 'Chiefs', 'Kansas City', 'KC', 'AFC', 'West', '#E31837', '#FFB31C'),
(13, 'Raiders', 'Las Vegas', 'LV', 'AFC', 'West', '#000000', '#A5ACAF'),
(24, 'Chargers', 'Los Angeles', 'LAC', 'AFC', 'West', '#0080C6', '#FFC20E');

-- NFC East
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(6, 'Cowboys', 'Dallas', 'DAL', 'NFC', 'East', '#003594', '#041E42'),
(19, 'Giants', 'New York', 'NYG', 'NFC', 'East', '#0B2265', '#A71930'),
(21, 'Eagles', 'Philadelphia', 'PHI', 'NFC', 'East', '#004C54', '#A5ACAF'),
(28, 'Commanders', 'Washington', 'WAS', 'NFC', 'East', '#5A1414', '#FFB612');

-- NFC North
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(3, 'Bears', 'Chicago', 'CHI', 'NFC', 'North', '#0B162A', '#C83803'),
(8, 'Lions', 'Detroit', 'DET', 'NFC', 'North', '#0076B6', '#B0B7BC'),
(9, 'Packers', 'Green Bay', 'GB', 'NFC', 'North', '#203731', '#FFB612'),
(16, 'Vikings', 'Minnesota', 'MIN', 'NFC', 'North', '#4F2683', '#FFC62F');

-- NFC South  
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(1, 'Falcons', 'Atlanta', 'ATL', 'NFC', 'South', '#A71930', '#000000'),
(29, 'Panthers', 'Carolina', 'CAR', 'NFC', 'South', '#0085CA', '#101820'),
(18, 'Saints', 'New Orleans', 'NO', 'NFC', 'South', '#D3BC8D', '#101820'),
(27, 'Buccaneers', 'Tampa Bay', 'TB', 'NFC', 'South', '#D50A0A', '#FF7900');

-- NFC West
INSERT INTO teams (id, name, city, abbreviation, conference, division, primary_color, secondary_color) VALUES
(22, 'Cardinals', 'Arizona', 'ARI', 'NFC', 'West', '#97233F', '#000000'),
(14, 'Rams', 'Los Angeles', 'LAR', 'NFC', 'West', '#003594', '#FFA300'),
(25, '49ers', 'San Francisco', 'SF', 'NFC', 'West', '#AA0000', '#B3995D'),
(26, 'Seahawks', 'Seattle', 'SEA', 'NFC', 'West', '#002244', '#69BE28');

-- Create games table
CREATE TABLE IF NOT EXISTS games (
    id SERIAL PRIMARY KEY,
    home_team_id INTEGER REFERENCES teams(id) NOT NULL,
    away_team_id INTEGER REFERENCES teams(id) NOT NULL,
    game_time TIMESTAMP NOT NULL,
    week INTEGER,
    season INTEGER DEFAULT 2024,
    game_type VARCHAR(20) DEFAULT 'REGULAR',
    home_score INTEGER,
    away_score INTEGER,
    status VARCHAR(20) DEFAULT 'SCHEDULED',
    venue VARCHAR(255),
    is_dome BOOLEAN DEFAULT FALSE,
    surface VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT different_teams CHECK (home_team_id != away_team_id)
);

-- Create news_sentiment_predictions table for tracking News Sentiment Agent predictions
CREATE TABLE IF NOT EXISTS news_sentiment_predictions (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) NOT NULL,
    predicted_winner VARCHAR(100) NOT NULL,
    confidence DECIMAL(5,3) CHECK (confidence >= 0.5 AND confidence <= 1.0),
    sentiment_differential DECIMAL(6,3),
    home_sentiment JSONB,
    away_sentiment JSONB,
    key_factors JSONB,
    reasoning TEXT,
    data_source VARCHAR(20) DEFAULT 'real_news',
    prediction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    agent_version VARCHAR(50) DEFAULT 'news_sentiment_v1.0',
    is_correct BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create general agent_predictions table for other agents
CREATE TABLE IF NOT EXISTS agent_predictions (
    id SERIAL PRIMARY KEY,
    game_id INTEGER REFERENCES games(id) NOT NULL,
    agent_type VARCHAR(50) NOT NULL,  -- 'news_sentiment', 'weather', 'stats', etc.
    predicted_home_score INTEGER,
    predicted_away_score INTEGER,
    predicted_winner VARCHAR(100),
    confidence DECIMAL(5,3) CHECK (confidence >= 0.0 AND confidence <= 1.0),
    agent_data JSONB,  -- Store agent-specific data
    prediction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_version VARCHAR(50),
    is_correct BOOLEAN,
    accuracy_score DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample games for testing (using correct team IDs)
INSERT INTO games (home_team_id, away_team_id, game_time, week, season, venue, is_dome) VALUES
(12, 2, '2024-01-21 15:30:00', 18, 2024, 'Arrowhead Stadium', false),  -- Chiefs vs Bills
(25, 6, '2024-01-14 20:15:00', 18, 2024, 'Levi''s Stadium', false),    -- 49ers vs Cowboys  
(9, 26, '2024-01-14 16:30:00', 18, 2024, 'Lambeau Field', false),      -- Packers vs Seahawks
(2, 15, '2024-01-25 20:15:00', 19, 2024, 'Highmark Stadium', false),   -- Bills vs Dolphins (Thursday Night)
(14, 1, '2024-01-28 13:00:00', 19, 2024, 'SoFi Stadium', true);        -- Rams vs Falcons

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_games_game_time ON games(game_time);
CREATE INDEX IF NOT EXISTS idx_games_season_week ON games(season, week);
CREATE INDEX IF NOT EXISTS idx_games_status ON games(status);
CREATE INDEX IF NOT EXISTS idx_teams_conference_division ON teams(conference, division);
CREATE INDEX IF NOT EXISTS idx_teams_abbreviation ON teams(abbreviation);
CREATE INDEX IF NOT EXISTS idx_teams_name ON teams(name);
CREATE INDEX IF NOT EXISTS idx_news_predictions_game_id ON news_sentiment_predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_news_predictions_time ON news_sentiment_predictions(prediction_time);
CREATE INDEX IF NOT EXISTS idx_agent_predictions_game_agent ON agent_predictions(game_id, agent_type);

-- Create view for easy game lookups with team names
CREATE OR REPLACE VIEW games_with_teams AS
SELECT 
    g.id,
    g.game_time,
    g.week,
    g.season,
    g.venue,
    g.is_dome,
    g.status,
    g.home_score,
    g.away_score,
    ht.id as home_team_id,
    ht.name as home_team_name,
    ht.abbreviation as home_team_abbr,
    ht.city as home_team_city,
    at.id as away_team_id,
    at.name as away_team_name,
    at.abbreviation as away_team_abbr,
    at.city as away_team_city
FROM games g
JOIN teams ht ON g.home_team_id = ht.id
JOIN teams at ON g.away_team_id = at.id;

-- Create function to get team ID by name (for API use)
CREATE OR REPLACE FUNCTION get_team_id_by_name(team_name TEXT)
RETURNS INTEGER AS $$
BEGIN
    RETURN (SELECT id FROM teams WHERE name = team_name LIMIT 1);
END;
$$ LANGUAGE plpgsql;

-- Create function to get team name by ID (for API use)  
CREATE OR REPLACE FUNCTION get_team_name_by_id(team_id INTEGER)
RETURNS TEXT AS $$
BEGIN
    RETURN (SELECT name FROM teams WHERE id = team_id LIMIT 1);
END;
$$ LANGUAGE plpgsql;

-- Display summary
SELECT 'NFL Database initialization complete!' as message;
SELECT 'Fixed team IDs for API consistency' as note;

-- Show team distribution
SELECT conference, division, COUNT(*) as team_count 
FROM teams 
GROUP BY conference, division 
ORDER BY conference, division;

-- Show sample games
SELECT 
    'Sample games created:' as message,
    home_team_name || ' vs ' || away_team_name as matchup,
    game_time::date as game_date
FROM games_with_teams 
ORDER BY game_time;

-- Show key team ID mappings for API reference
SELECT 'Key team ID mappings for API:' as reference;
SELECT id, name, abbreviation 
FROM teams 
WHERE name IN ('Bills', 'Dolphins', 'Chiefs', 'Cowboys', 'Rams', 'Falcons')
ORDER BY id;
