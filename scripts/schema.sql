-- Bird RPG Supabase Schema
-- Run this in the Supabase SQL Editor to create all tables and RPC functions

-- Players (from personal_nests)
CREATE TABLE players (
    user_id TEXT PRIMARY KEY,
    discord_username TEXT,
    nest_name TEXT DEFAULT 'Some Bird''s Nest',
    twigs INTEGER DEFAULT 0,
    seeds INTEGER DEFAULT 0,
    inspiration NUMERIC DEFAULT 0,
    garden_size INTEGER DEFAULT 0,
    bonus_actions INTEGER DEFAULT 0,
    locked BOOLEAN DEFAULT FALSE,
    featured_bird_common_name TEXT,
    featured_bird_scientific_name TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Common nest (singleton shared resource)
CREATE TABLE common_nest (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    twigs INTEGER DEFAULT 0,
    seeds INTEGER DEFAULT 0
);

-- Initialize common nest
INSERT INTO common_nest (id, twigs, seeds) VALUES (1, 0, 0) ON CONFLICT DO NOTHING;

-- Birds in player nests
CREATE TABLE player_birds (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES players(user_id),
    common_name TEXT NOT NULL,
    scientific_name TEXT NOT NULL
);

-- Treasures/decorations on birds
CREATE TABLE bird_treasures (
    id SERIAL PRIMARY KEY,
    bird_id INTEGER NOT NULL REFERENCES player_birds(id) ON DELETE CASCADE,
    treasure_id TEXT NOT NULL,
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0
);

-- Plants in player gardens
CREATE TABLE player_plants (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES players(user_id),
    common_name TEXT NOT NULL,
    scientific_name TEXT NOT NULL,
    planted_date TEXT
);

-- Treasures/decorations on plants
CREATE TABLE plant_treasures (
    id SERIAL PRIMARY KEY,
    plant_id INTEGER NOT NULL REFERENCES player_plants(id) ON DELETE CASCADE,
    treasure_id TEXT NOT NULL,
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0
);

-- Treasure inventory (unplaced)
CREATE TABLE player_treasures (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES players(user_id),
    treasure_id TEXT NOT NULL
);

-- Treasures applied on nest itself
CREATE TABLE nest_treasures (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES players(user_id),
    treasure_id TEXT NOT NULL,
    x INTEGER DEFAULT 0,
    y INTEGER DEFAULT 0
);

-- Eggs (0 or 1 per player)
CREATE TABLE eggs (
    user_id TEXT PRIMARY KEY REFERENCES players(user_id),
    brooding_progress INTEGER DEFAULT 0,
    protected_prayers BOOLEAN DEFAULT FALSE
);

-- Egg prayer multipliers
CREATE TABLE egg_multipliers (
    id SERIAL PRIMARY KEY,
    egg_user_id TEXT NOT NULL REFERENCES eggs(user_id) ON DELETE CASCADE,
    scientific_name TEXT NOT NULL,
    multiplier NUMERIC NOT NULL DEFAULT 0,
    UNIQUE(egg_user_id, scientific_name)
);

-- Egg brooders
CREATE TABLE egg_brooders (
    id SERIAL PRIMARY KEY,
    egg_user_id TEXT NOT NULL REFERENCES eggs(user_id) ON DELETE CASCADE,
    brooder_user_id TEXT NOT NULL,
    UNIQUE(egg_user_id, brooder_user_id)
);

-- Daily actions tracking
CREATE TABLE daily_actions (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES players(user_id),
    action_date TEXT NOT NULL,
    used INTEGER DEFAULT 0,
    action_history TEXT[] DEFAULT '{}',
    UNIQUE(user_id, action_date)
);

-- Daily songs
CREATE TABLE daily_songs (
    id SERIAL PRIMARY KEY,
    song_date TEXT NOT NULL,
    singer_user_id TEXT NOT NULL,
    target_user_id TEXT NOT NULL,
    UNIQUE(song_date, singer_user_id, target_user_id)
);

-- Daily brooding records
CREATE TABLE daily_brooding (
    id SERIAL PRIMARY KEY,
    brooding_date TEXT NOT NULL,
    brooder_user_id TEXT NOT NULL,
    target_user_id TEXT NOT NULL,
    UNIQUE(brooding_date, brooder_user_id, target_user_id)
);

-- Last song targets (for /sing_repeat)
CREATE TABLE last_song_targets (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES players(user_id),
    target_user_id TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);

-- Released birds (global)
CREATE TABLE released_birds (
    id SERIAL PRIMARY KEY,
    common_name TEXT NOT NULL,
    scientific_name TEXT NOT NULL UNIQUE,
    count INTEGER DEFAULT 1
);

-- Defeated humans
CREATE TABLE defeated_humans (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    max_resilience INTEGER,
    defeat_date TEXT NOT NULL,
    blessing_name TEXT,
    blessing_amount INTEGER
);

-- Memoirs
CREATE TABLE memoirs (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    nest_name TEXT,
    text TEXT NOT NULL,
    memoir_date TEXT NOT NULL
);

-- Realm lore messages
CREATE TABLE realm_messages (
    id SERIAL PRIMARY KEY,
    message_date TEXT NOT NULL,
    message TEXT NOT NULL
);

-- Manifested birds
CREATE TABLE manifested_birds (
    id SERIAL PRIMARY KEY,
    common_name TEXT NOT NULL,
    scientific_name TEXT NOT NULL UNIQUE,
    rarity_weight NUMERIC DEFAULT 0,
    rarity TEXT DEFAULT 'common',
    effect TEXT DEFAULT '',
    manifested_points INTEGER DEFAULT 0,
    fully_manifested BOOLEAN DEFAULT FALSE
);

-- Manifested plants
CREATE TABLE manifested_plants (
    id SERIAL PRIMARY KEY,
    common_name TEXT NOT NULL,
    scientific_name TEXT NOT NULL UNIQUE,
    rarity_weight NUMERIC DEFAULT 0,
    rarity TEXT DEFAULT 'common',
    effect TEXT DEFAULT '',
    seed_cost INTEGER DEFAULT 30,
    size_cost INTEGER DEFAULT 1,
    inspiration_cost NUMERIC DEFAULT 0.2,
    manifested_points INTEGER DEFAULT 0,
    fully_manifested BOOLEAN DEFAULT FALSE
);

-- Research progress
CREATE TABLE research_progress (
    author_name TEXT PRIMARY KEY,
    points INTEGER DEFAULT 0
);

-- Exploration progress
CREATE TABLE exploration (
    region TEXT PRIMARY KEY,
    points INTEGER DEFAULT 0
);

-- Weather channels
CREATE TABLE weather_channels (
    guild_id TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL
);


-- =============================================================
-- RPC Functions (for atomic operations — solves race conditions)
-- =============================================================

-- Atomic increment for common nest
CREATE OR REPLACE FUNCTION increment_common_nest(field_name TEXT, amount INTEGER)
RETURNS void AS $$
BEGIN
    IF field_name = 'twigs' THEN
        UPDATE common_nest SET twigs = twigs + amount WHERE id = 1;
    ELSIF field_name = 'seeds' THEN
        UPDATE common_nest SET seeds = seeds + amount WHERE id = 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Game settings (key-value config, e.g. active_event)
CREATE TABLE game_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO game_settings (key, value) VALUES ('active_event', 'default');

-- Birdwatch sightings (user-uploaded bird photos)
CREATE TABLE birdwatch_sightings (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES players(user_id),
    image_url TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    original_filename TEXT,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_birdwatch_user ON birdwatch_sightings(user_id);

-- Atomic increment for player resources
CREATE OR REPLACE FUNCTION increment_player_field(p_user_id TEXT, field_name TEXT, amount NUMERIC)
RETURNS void AS $$
BEGIN
    EXECUTE format('UPDATE players SET %I = %I + $1, updated_at = now() WHERE user_id = $2', field_name, field_name)
    USING amount, p_user_id;
END;
$$ LANGUAGE plpgsql;
