import json
import os
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

from flask import Flask
from threading import Thread

# =========================
# FLASK KEEP ALIVE
# =========================
app = Flask('')

@app.route('/')
def home():
    return "Bot activo"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start()

# =========================
# ENV
# =========================
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("weekly-xp-bot")

DEFAULT_WEEKLY_XP_REQUIREMENT = 30_000
WEEKLY_XP_REQUIREMENT = int(os.getenv("WEEKLY_XP_REQUIREMENT", str(DEFAULT_WEEKLY_XP_REQUIREMENT)))

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
KIRKA_API_KEY = os.getenv("KIRKA_API_KEY", "")
CLAN_NAME = os.getenv("KIRKA_CLAN_TAG", "UsAsOne!")
KIRKA_API_BASE = os.getenv("KIRKA_API_BASE", "https://api.kirka.io")

MONDAY_SNAPSHOT_PATH = Path(os.getenv("MONDAY_SNAPSHOT_FILE", "xp_monday.json"))
SUNDAY_SNAPSHOT_PATH = Path(os.getenv("SUNDAY_SNAPSHOT_FILE", "xp_sunday.json"))

HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_RETRY_BASE_DELAY = float(os.getenv("HTTP_RETRY_BASE_DELAY", "0.8"))

# =========================
# API CLIENT
# =========================
class ClanClient:
    def __init__(self, api_base: str, api_key: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS))

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def get_clan_data(self, clan_name: str) -> dict[str, Any]:
        encoded_name = quote(clan_name.strip(), safe="")
        url = f"{self.api_base}/api/clan/{encoded_name}"
        return await self._request_json_with_retry("GET", url)

    async def get_top_clans(self) -> dict[str, Any]:
        url = f"{self.api_base}/api/leaderboard/clan"
        return await self._request_json_with_retry("GET", url)

    async def _request_json_with_retry(self, method: str, url: str, json_payload: dict[str, Any] | None = None) -> Any:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        headers = {
            "accept": "application/json",
            "ApiKey": self.api_key,
        }

        last_error: Exception | None = None

        for attempt in range(1, HTTP_MAX_RETRIES + 1):
            try:
                async with self.session.request(method, url, headers=headers, json=json_payload) as r:
                    text = await r.text()

                    if r.status >= 200 and r.status < 300:
                        return await r.json(content_type=None)

                    if r.status == 429:
                        await asyncio.sleep(HTTP_RETRY_BASE_DELAY * attempt)
                        continue

                    raise RuntimeError(f"API error {r.status}: {text[:200]}")

            except Exception as e:
                last_error = e
                await asyncio.sleep(HTTP_RETRY_BASE_DELAY * attempt)

        raise RuntimeError(f"Request failed: {last_error}")


# =========================
# BOT
# =========================
class WeeklyXPBot(commands.Bot):
    def __init__(self, clan_client: ClanClient):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.clan_client = clan_client

    async def setup_hook(self):
        await self.clan_client.start()
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def close(self):
        await self.clan_client.close()
        await super().close()


clan_client = ClanClient(KIRKA_API_BASE, KIRKA_API_KEY)
bot = WeeklyXPBot(clan_client)


# =========================
# TOP CLANS (NEW)
# =========================
@bot.tree.command(name="top_clans", description="Global clans leaderboard with pagination")
@app_commands.describe(page="Page number")
async def top_clans(interaction: discord.Interaction, page: int = 1):
    await interaction.response.defer(thinking=True)

    try:
        data = await bot.clan_client.get_top_clans()
        results = data.get("results", [])

        per_page = 10
        total_pages = max(1, (len(results) + per_page - 1) // per_page)

        page = max(1, min(page, total_pages))

        start = (page - 1) * per_page
        end = start + per_page

        chunk = results[start:end]

        lines = []
        lines.append(f"{'Rank':<6}{'Clan':<20}{'Members':<10}{'Scores':>15}")
        lines.append("-" * 60)

        for i, c in enumerate(chunk, start=start + 1):
            name = str(c.get("name", "Unknown"))[:20]
            members = c.get("membersCount", 0)
            scores = f"{c.get('scores', 0):,}"

            # medals
            if i == 1:
                rank = "🥇"
            elif i == 2:
                rank = "🥈"
            elif i == 3:
                rank = "🥉"
            else:
                rank = str(i)

            # highlight clan
            if name == CLAN_NAME:
                name = f"⭐ {name}"

            lines.append(f"{rank:<6}{name:<20}{members:<10}{scores:>15}")

        text = (
            "🏆 **GLOBAL TOP CLANS**\n\n"
            "```" + "\n".join(lines) + "```\n"
            f"Page {page}/{total_pages} | Total: {len(results)}"
        )

        await interaction.followup.send(text)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


# =========================
# START BOT
# =========================
def validate():
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN")
    if not KIRKA_API_KEY:
        raise RuntimeError("Missing KIRKA_API_KEY")


if __name__ == "__main__":
    validate()
    keep_alive()
    bot.run(DISCORD_TOKEN)
