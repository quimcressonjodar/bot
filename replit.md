# Discord Bot — WeeklyXP / Moderation & Economy

A Discord bot built with `discord.py` featuring moderation, economy, pets, games, Kirka.io integration, and more.

## Stack
- **Language**: Python 3.12
- **Bot framework**: discord.py
- **Database**: MongoDB (via pymongo)
- **Keep-alive**: Flask (background thread, port 10000)

## Project Structure
- `main.py` — entry point, loads all Cogs and starts Flask keep-alive
- `cogs/` — feature modules (admin, economy, pets, games, kirka, utility, events, starboard, stocks, bounties, fake_admin_ai)
- `utils/` — shared helpers (economy DB ops, kirka API client, misc helpers)
- `views/` — Discord UI components (buttons, selects)
- `config.py` — all constants, loot tables, shop prices, and env var loading
- `database.py` — MongoDB connection setup

## Running Locally
```bash
pip install -r requirements.txt
python main.py
```

## Required Environment Variables
- `DISCORD_TOKEN` — Discord bot token
- `KIRKA_API_KEY` — Kirka.io API key
- `MONGO_URI` — MongoDB connection string (used in `database.py`)
- `PORT` — Flask keep-alive port (defaults to `10000`)

## GitHub Remote
- `origin` → `https://github.com/quimcressonjodar/bot`

## User Preferences
- Make requested code changes and commit + push to GitHub after each change.
