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
```

Set `DEBUG=true` in `.env` to enable debug commands and template auto-reload.

## Architecture

**Dual-server design**: `bot.py` starts both the Discord bot (`discord.py` with slash commands) and Flask web server in a separate thread.

**Commands**: Discord slash commands live in `commands/` as cogs. Each cog class inherits from `commands.Cog` and registers via `async def setup(bot)`. Add new commands by creating a cog file and adding it to the `COGS` list in `bot.py`.

**Web**: Flask routes in `web/server.py`, templates in `templates/` (Jinja2), static assets in `static/`. `templates/base.html` provides the layout with a mystical/papyrus aesthetic.

**Data storage**: JSON files stored at `config.config.DATA_PATH` (defaults to `./bird-rpg`, uses `/var/data/bird-rpg` if available). Core files:
- `nests.json` - player data (nests, birds, gardens, resources)
- `lore.json` - player memoirs
- `manifested_birds.json` / `manifested_plants.json` - community-created species
- `research_progress.json` - research system state

Always use helpers in `data/storage.py` (`load_data`, `save_data`, etc.) instead of writing JSON directly.

**Backups**: `data/backup.py` runs daily on first action, copies key JSONs to `DATA_PATH/backups`, rotates to keep 10 newest.

**Configuration**: `config/config.py` holds paths, limits (MAX_BIRDS_PER_NEST, MAX_GARDEN_SIZE), and environment variables. Game constants in `constants.py` and `data/constants.py`.

## Key Patterns

- Slash commands auto-sync on bot startup
- Use `utils.logging.log_debug` for debug output
- Time functions in `utils/time_utils.py` use Australian timezone
- Data migrations run on startup in `bot.py` - add safe migrations for schema changes
- `templates/help.html` is the authoritative user-facing command guide - update when gameplay changes

## Testing

Tests in `tests/` use pytest. The `conftest.py` sets up test environment with DEBUG mode and creates isolated test_data directory. Prefer targeted tests near changed logic.

## Workflow Rules

- **Update this file after every task**: After completing any task, review `CLAUDE.md` and update it with any new relevant information (new commands, patterns, architecture changes, etc.) so it stays accurate.
- **Use MCP Context7 for documentation lookups**: When you need documentation for any library or framework, always use the Context7 MCP tools (`resolve-library-id` then `query-docs`) to get up-to-date docs instead of relying on training data.
