# Bird RPG

A bird-themed Discord RPG where players build nests, hatch eggs, collect birds, tend gardens, and protect the realm from human intruders. Comes with a web dashboard to view the village.

## How It Works

You start with nothing. Use `/build` to gather twigs for your nest, `/add_seed` to fill it with seeds, and `/lay_egg` to start incubating your first bird. Other players can `/sing` to you (granting bonus actions) and `/brood` your eggs to help them hatch faster. Over time you'll grow a flock of Australian birds, each with unique abilities that boost your actions.

The game runs on a daily action economy -- you get a base number of actions per day, plus one per bird in your nest, plus any bonus actions from singing. Everything resets at midnight AEST.

## Features

**Nest Building** -- Gather twigs and seeds for your personal nest, or contribute to the shared common nest that benefits everyone.

**Egg Incubation** -- Convert seeds into eggs, brood them (or ask friends to help), and hatch random bird species weighted by rarity. Bless eggs and pray for specific species to influence the outcome.

**102+ Bird Species** -- Common to mythical rarity, each with effects like extra twigs on first build, bonus singing actions, garden growth, or swooping power. Community members can `/manifest_bird` to add new real-world species to the game.

**Gardening** -- Plant species in your garden for passive effects like reduced brooding requirements or extra bird chances on hatch. 10+ base plant species, expandable via `/manifest_plant`.

**Foraging** -- Spend actions to search locations for treasures and stickers. Use them to decorate your nest, birds, and plants.

**Swooping** -- Human intruders appear in the realm. Coordinate with other players to `/swoop` them away. Defeating a human grants blessings to all players (bonus seeds, actions, garden growth, etc).

**Research** -- `/graduate_bird` to release birds and boost study efficiency, then `/study` authors to unlock lore milestones.

**Social** -- `/sing` to grant bonus actions, `/entrust` birds to other players, `/regurgitate` to share bonus actions, `/gift_treasure` to share loot, `/start_flock` for pomodoro sessions.

**Wings of Time** -- Write `/memoir` entries to leave your mark in the realm's history.

**Web Dashboard** -- A live village view at `http://localhost:10000` showing all nests, the common nest, discovered species, exploration progress, current human intruder, and the Wings of Time timeline. Each player has a `/user/<id>` profile page.

## Setup

### Prerequisites

- Python 3.10+
- A Discord bot token ([Discord Developer Portal](https://discord.com/developers/applications))
- A Supabase project ([supabase.com](https://supabase.com))

### Discord Bot Setup

Create a bot application with these OAuth2 scopes and permissions:

**Scopes:** `bot`, `applications.commands`

**Bot Permissions:** Read Messages/View Channels, Send Messages, Read Message History

### Installation

```bash
python -m venv venv

# Mac/Linux
source ./venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```
DISCORD_TOKEN=your-discord-bot-token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-public-key
ADMIN_PASSWORD=your-admin-panel-password
DEBUG=false
```

### Database Setup

1. In the Supabase dashboard, go to **SQL Editor**
2. Paste the contents of `scripts/schema.sql` and run it
3. Disable Row Level Security on all tables (or add permissive policies):

```sql
ALTER TABLE players DISABLE ROW LEVEL SECURITY;
ALTER TABLE common_nest DISABLE ROW LEVEL SECURITY;
ALTER TABLE player_birds DISABLE ROW LEVEL SECURITY;
ALTER TABLE bird_treasures DISABLE ROW LEVEL SECURITY;
ALTER TABLE player_plants DISABLE ROW LEVEL SECURITY;
ALTER TABLE plant_treasures DISABLE ROW LEVEL SECURITY;
ALTER TABLE player_treasures DISABLE ROW LEVEL SECURITY;
ALTER TABLE nest_treasures DISABLE ROW LEVEL SECURITY;
ALTER TABLE eggs DISABLE ROW LEVEL SECURITY;
ALTER TABLE egg_multipliers DISABLE ROW LEVEL SECURITY;
ALTER TABLE egg_brooders DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_actions DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_songs DISABLE ROW LEVEL SECURITY;
ALTER TABLE daily_brooding DISABLE ROW LEVEL SECURITY;
ALTER TABLE last_song_targets DISABLE ROW LEVEL SECURITY;
ALTER TABLE released_birds DISABLE ROW LEVEL SECURITY;
ALTER TABLE defeated_humans DISABLE ROW LEVEL SECURITY;
ALTER TABLE memoirs DISABLE ROW LEVEL SECURITY;
ALTER TABLE realm_messages DISABLE ROW LEVEL SECURITY;
ALTER TABLE manifested_birds DISABLE ROW LEVEL SECURITY;
ALTER TABLE manifested_plants DISABLE ROW LEVEL SECURITY;
ALTER TABLE research_progress DISABLE ROW LEVEL SECURITY;
ALTER TABLE exploration DISABLE ROW LEVEL SECURITY;
ALTER TABLE weather_channels DISABLE ROW LEVEL SECURITY;
```

### Data Migration (if upgrading from JSON storage)

If you have existing game data in JSON files:

```bash
python scripts/migrate_to_supabase.py
```

### Run

```bash
python bot.py
```

This starts both the Discord bot and the web dashboard on port 10000.

### Tests

```bash
pytest ./tests
```

Tests mock the database layer and don't require a Supabase connection.

## Commands

### Nest Building
| Command | Description |
|---------|-------------|
| `/build [amount]` | Add twigs to your personal nest |
| `/build_common [amount]` | Add twigs to the common nest |
| `/add_seed [amount]` | Add seeds to your nest |
| `/add_seed_common [amount]` | Add seeds to the common nest |
| `/donate_seeds [amount]` | Move seeds from your nest to common |
| `/borrow_seeds [amount]` | Move seeds from common to your nest |

### Incubation
| Command | Description |
|---------|-------------|
| `/lay_egg` | Convert seeds into an egg |
| `/brood [@user]` | Brood an egg to help it hatch |
| `/brood_random` | Brood a random unbrooded nest |
| `!brood_all` | Brood all available nests |
| `/bless_egg` | Bless your egg (1 inspiration + 30 seeds) |
| `/pray_for_bird [name] [amount]` | Increase a species' hatching chance |
| `/lock_nest` / `/unlock_nest` | Control who can brood your eggs |

### Social
| Command | Description |
|---------|-------------|
| `/sing @user1 @user2 ...` | Grant 3 bonus actions to each target |
| `/sing_repeat` | Repeat your last sing targets |
| `/entrust [bird] @user` | Give a bird to another player |
| `/regurgitate @user [amount]` | Share bonus actions |
| `/gift_treasure [treasure] @user` | Give a treasure |
| `/nests` | View nest status |
| `/showcase_nest [@user]` | Post a rendered nest showcase image in Discord |

### Garden & Foraging
| Command | Description |
|---------|-------------|
| `/plant_new [name]` | Plant a species in your garden |
| `/plant_compost [name]` | Remove a plant (80% refund) |
| `/forage [actions]` | Search for treasures |
| `/cancel_forage` | Cancel ongoing forage |
| `/weather` | Melbourne weather report |

### Customisation
| Command | Description |
|---------|-------------|
| `/rename_nest [name]` | Rename your nest |
| `/feature_bird [name]` | Set your featured bird |
| `/decorate_nest [treasure] [x] [y]` | Decorate your nest |
| `/decorate_bird [bird] [treasure] [x] [y]` | Decorate a bird |
| `/decorate_plant [plant] [treasure] [x] [y]` | Decorate a plant |
| `/clean_nest` / `/clean_bird` / `/clean_plant` | Remove decorations |

### Combat & Exploration
| Command | Description |
|---------|-------------|
| `/swoop [amount]` | Attack the current human intruder |
| `/current_human` | Check intruder status |
| `/explore [region] [amount]` | Explore Oceania |

### Research & Manifestation
| Command | Description |
|---------|-------------|
| `/graduate_bird [name]` | Release a bird (+1% study bonus) |
| `/study [actions]` | Research authors for lore milestones |
| `/manifest_bird [scientific_name] [actions]` | Add a new bird species |
| `/manifest_plant [scientific_name] [actions]` | Add a new plant species |

### Other
| Command | Description |
|---------|-------------|
| `/memoir [text]` | Write a Wings of Time entry |
| `/start_flock` | Start a pomodoro session |
| `/join_flock` | Join an active pomodoro |

## Architecture

The bot runs two servers in one process:

- **Discord bot** (`discord.py`) -- slash commands as cogs in `commands/`
- **Flask web server** -- dashboard and player pages in `web/` and `templates/`

Game state lives in **Supabase (PostgreSQL)** across ~20 normalized tables. All database operations use atomic increments (via PostgreSQL RPC functions) to prevent data loss from concurrent commands.

Reference data (bird species, plant species, treasures, research entities) stays as local JSON files bundled with the code.

## Web Pages

| Route | Description |
|-------|-------------|
| `/` | Village overview -- all nests, common nest, species discovery |
| `/user/<id>` | Player profile -- birds, plants, treasures, egg status |
| `/codex` | Species codex -- all birds and plants, discovered status |
| `/research` | Research progress -- author milestones |
| `/wings-of-time` | Timeline of memoirs and realm events |
| `/help` | Command guide |
| `/admin/` | Admin panel (password protected) |
