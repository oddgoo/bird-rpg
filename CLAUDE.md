# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bird RPG is a bird-themed Discord bot game with an accompanying Flask web server. Players collect birds, tend gardens, and engage in community activities.

## Commands

```bash
# Setup
python3 -m venv venv
source ./venv/bin/activate  # Mac/Linux
pip install -r requirements.txt

# Run the bot (starts both Discord bot and Flask server on port 10000)
python bot.py

# Run tests
pytest ./tests

# Run a single test file
pytest ./tests/test_manifest.py

# Run a specific test
pytest ./tests/test_manifest.py::test_function_name

# Migrate JSON data to Supabase (one-time)
python scripts/migrate_to_supabase.py
```

Set `DEBUG=true` in `.env` to enable debug commands and template auto-reload.

### Environment Variables

Required in `.env`:
- `DISCORD_TOKEN` - Discord bot token
- `SUPABASE_URL` - Supabase project URL (e.g. `https://your-project.supabase.co`)
- `SUPABASE_KEY` - Supabase anon/public key
- `ADMIN_PASSWORD` - Password for web admin panel
- `DEBUG` - Set to `true` for debug mode (optional)

## Architecture

**Dual-server design**: `bot.py` starts both the Discord bot (`discord.py` with slash commands) and Flask web server in a separate thread.

**Commands**: Discord slash commands live in `commands/` as cogs. Each cog class inherits from `commands.Cog` and registers via `async def setup(bot)`. Add new commands by creating a cog file and adding it to the `COGS` list in `bot.py`.

**Web**: Flask routes in `web/server.py`, templates in `templates/` (Jinja2), static assets in `static/`. `templates/base.html` provides the layout with a mystical/papyrus aesthetic.

**Data storage**: Supabase (PostgreSQL) via the `supabase-py` library. All game state is stored in ~20 normalized tables (players, player_birds, eggs, daily_actions, etc.).

- `data/db.py` - Supabase client singleton (`get_sync_client()` for Flask, `get_async_client()` for Discord commands)
- `data/storage.py` - All database operations as async functions (with `_sync` suffixed variants for Flask routes)
- `data/models.py` - Game logic functions (async) that call storage.py

Reference data files (read-only, bundled with code):
- `data/bird_species.json` - Base bird species catalog
- `data/plant_species.json` - Base plant species catalog
- `data/treasures.json` - Treasure/sticker items
- `data/human_entities.json` - Human spawner data
- `data/research_entities.json` - Research system config
- `data/realm_lore.json` - Realm narrative messages

**Configuration**: `config/config.py` holds limits (MAX_BIRDS_PER_NEST, MAX_GARDEN_SIZE), Supabase connection config, and environment variables. Game constants in `constants.py` and `data/constants.py`.

## Database Schema

Schema SQL is at `scripts/schema.sql`. Key tables:
- `players` - Player data (twigs, seeds, inspiration, etc.)
- `player_birds` / `player_plants` - Birds and plants owned by players
- `common_nest` - Shared community nest (singleton)
- `eggs` / `egg_multipliers` / `egg_brooders` - Egg incubation system
- `daily_actions` / `daily_songs` / `daily_brooding` - Daily activity tracking
- `manifested_birds` / `manifested_plants` - Community-created species
- `research_progress` / `exploration` - Progression systems

RPC functions (`increment_common_nest`, `increment_player_field`) provide atomic operations.

## Key Patterns

- **Async/sync split**: Discord commands use async DB functions; Flask routes use `_sync` suffixed variants
- **Atomic operations**: Use `db.increment_player_field()` / `db.increment_common_nest()` (RPC calls) instead of read-modify-write for numeric fields
- **No load-everything pattern**: Each command makes targeted DB calls (SELECT/INSERT/UPDATE) instead of loading all data
- Slash commands auto-sync on bot startup
- Use `utils.logging.log_debug` for debug output
- Time functions in `utils/time_utils.py` use Australian timezone
- `templates/help.html` is the authoritative user-facing command guide - update when gameplay changes

## Testing

Tests in `tests/` use pytest with pytest-asyncio for async tests. Tests mock the Supabase client via `unittest.mock.AsyncMock` on `data.storage` functions. Prefer targeted tests near changed logic.

## Workflow Rules

- **Update this file after every task**: After completing any task, review `CLAUDE.md` and update it with any new relevant information (new commands, patterns, architecture changes, etc.) so it stays accurate.
- **Use MCP Context7 for documentation lookups**: When you need documentation for any library or framework, always use the Context7 MCP tools (`resolve-library-id` then `query-docs`) to get up-to-date docs instead of relying on training data.
