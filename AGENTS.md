# AGENTS PLAYBOOK

- Mission: keep the bird-themed Discord RPG running smoothly. Read `README.md` for setup/run basics and skim `templates/help.html` to understand the game rules, commands, and tone before changing gameplay logic or copy.
- Stack: Discord bot (`discord.py` slash commands in `commands/` cogs) plus a Flask web server (`web/server.py`) serving templates in `templates/` and static assets in `static/`.
- Data: JSON files are stored under `config.config.DATA_PATH` (defaults to `./bird-rpg`, switches to `/var/data/bird-rpg` if available). Core files include `nests.json`, `lore.json`, `realm_lore.json`, and manifested/research JSONs. Use helpers in `data/storage.py` instead of writing files directly.
- Backups: `data/backup.py` runs once per day on the first recorded action, copying key JSONs into `DATA_PATH/backups` (rotates the newest 10) and marks completion in `last_backup.txt`.
- Runtime: create a venv, `pip install -r requirements.txt`, set `DISCORD_TOKEN` (and optionally `DEBUG=true`, `PORT`, `ADMIN_PASSWORD`), then `python bot.py`. This starts both the Discord bot and the Flask server (default port 10000). Slash commands auto-sync on startup; logs print to stdout.
- Testing: run `pytest ./tests`. Prefer targeted tests near changed logic; avoid modifying user data fixtures unless necessary.
- Web tips: `templates/base.html` drives layout; keep styles aligned with existing mystical/papyrus vibe. `help.html` is the authoritative user-facing command guide—update it if gameplay changes.
- Bot tips: add new commands as cogs in `commands/` and register slash commands via `bot.tree` (see existing cogs for patterns). Respect limits/configs in `config/config.py`. Use `utils.logging.log_debug` for debug prints.
- Data safety: migrations and username sync run on bot startup (`bot.py`). When altering stored shapes, add safe migrations rather than breaking existing JSON.
- Library docs: when you need library specifics (e.g., `discord.py`, Flask, pytest), fetch references via the Context7 MCP docs tool to stay accurate.

If anything is unclear, check `README.md`, the `templates/help.html` guide, and nearby module docstrings before coding. Keep changes small, tested, and in-theme with the bird RPG world.
