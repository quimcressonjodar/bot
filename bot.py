import os
import logging
import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
import aiohttp

import discord
from discord.ext import commands
from discord import app_commands

from dotenv import load_dotenv
from pymongo import MongoClient

from flask import Flask
from threading import Thread

# =========================
# FLASK KEEP ALIVE
# =========================
app = Flask("")

@app.route("/")
def home():
    return "Bot activo"

def run():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    Thread(target=run).start()

# =========================
# ENV
# =========================
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
KIRKA_API_KEY = os.getenv("KIRKA_API_KEY", "")
KIRKA_API_BASE = os.getenv("KIRKA_API_BASE", "https://api.kirka.io")
CLAN_NAME = os.getenv("KIRKA_CLAN_TAG", "UsAsOne!")
WEEKLY_XP_REQUIREMENT = int(os.getenv("WEEKLY_XP_REQUIREMENT", "30000"))
MONGO_URI = os.getenv("MONGO_URI", "")

# =========================
# MONGO DB
# =========================
mongo = MongoClient(MONGO_URI)
db = mongo["weekly_bot"]
snapshots = db["snapshots"]

# =========================
# LOGGING
# =========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weekly-xp-bot")

# =========================
# CLAN CLIENT
# =========================
class ClanClient:
    def __init__(self, api_base: str, api_key: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.session: aiohttp.ClientSession | None = None

    async def start(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def get_clan_data(self, clan_name: str):
        url = f"{self.api_base}/api/clan/{quote(clan_name)}"
        headers = {"ApiKey": self.api_key}

        async with self.session.get(url, headers=headers) as r:
            return await r.json()

# =========================
# HELPERS
# =========================
def is_admin(interaction: discord.Interaction):
    return interaction.user.guild_permissions.administrator


def extract_member_map(clan_data: dict[str, Any]):
    result = {}

    for item in clan_data.get("members", []):
        user = item.get("user", item)

        user_id = str(user.get("id") or "")
        if not user_id:
            continue

        result[user_id] = {
            "id": user_id,
            "name": user.get("name", "Unknown"),
            "shortId": user.get("shortId", "-"),
            "role": item.get("role", "UNKNOWN"),
            "allScores": int(item.get("allScores", 0) or 0),
        }

    return result


def build_weekly_rows(monday, sunday):
    rows = []
    all_ids = set(monday.keys()) | set(sunday.keys())

    for uid in all_ids:
        mon = monday.get(uid)
        sun = sunday.get(uid)

        if mon and sun:
            xp = sun["allScores"] - mon["allScores"]
            status = "OK" if xp >= WEEKLY_XP_REQUIREMENT else "MISSING"
            rows.append([sun["name"], sun["shortId"], sun["role"], xp, status])

        elif sun:
            rows.append([sun["name"], sun["shortId"], sun["role"], 0, "JOINED"])

        elif mon:
            rows.append([mon["name"], mon["shortId"], mon["role"], 0, "LEFT"])

    return rows


# =========================
# BOT
# =========================
class WeeklyXPBot(commands.Bot):
    def __init__(self, clan_client):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.clan_client = clan_client

    async def setup_hook(self):
        await self.clan_client.start()
        await self.tree.sync()
        logger.info("Bot listo")

    async def close(self):
        await self.clan_client.close()
        await super().close()


clan_client = ClanClient(KIRKA_API_BASE, KIRKA_API_KEY)
bot = WeeklyXPBot(clan_client)

# =========================
# SAVE SNAPSHOT (MONGO)
# =========================
def save_snapshot(snapshot_type: str, data: dict):
    snapshots.update_one(
        {"type": snapshot_type},
        {"$set": data},
        upsert=True
    )


def load_snapshot(snapshot_type: str):
    return snapshots.find_one({"type": snapshot_type})


def delete_snapshot(snapshot_type: str):
    snapshots.delete_one({"type": snapshot_type})


# =========================
# COMMANDS
# =========================
@bot.tree.command(name="register_monday")
async def register_monday(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin only", ephemeral=True)

    await interaction.response.defer()

    data = await bot.clan_client.get_clan_data(CLAN_NAME)

    snapshot = {
        "type": "monday",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "clan_name": CLAN_NAME,
        "members": extract_member_map(data),
    }

    save_snapshot("monday", snapshot)

    await interaction.followup.send("Monday guardado en MongoDB")


@bot.tree.command(name="register_sunday")
async def register_sunday(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin only", ephemeral=True)

    await interaction.response.defer()

    data = await bot.clan_client.get_clan_data(CLAN_NAME)

    snapshot = {
        "type": "sunday",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "clan_name": CLAN_NAME,
        "members": extract_member_map(data),
    }

    save_snapshot("sunday", snapshot)

    await interaction.followup.send("Sunday guardado en MongoDB")


@bot.tree.command(name="weekly_lb")
async def weekly_lb(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin only", ephemeral=True)

    await interaction.response.defer()

    monday = load_snapshot("monday")
    sunday = load_snapshot("sunday")

    if not monday or not sunday:
        return await interaction.followup.send("Falta Monday o Sunday")

    rows = build_weekly_rows(monday["members"], sunday["members"])

    text = "Player | Short | XP | Status\n"
    text += "-" * 50 + "\n"

    for r in rows:
        text += f"{r[0]} | {r[1]} | {r[3]} | {r[4]}\n"

    await interaction.followup.send(f"```{text}```")


@bot.tree.command(name="delete_snaps")
async def delete_snaps(interaction: discord.Interaction):
    if not is_admin(interaction):
        return await interaction.response.send_message("Admin only", ephemeral=True)

    delete_snapshot("monday")
    delete_snapshot("sunday")

    await interaction.response.send_message("Snapshots borrados de MongoDB")


@bot.tree.command(name="set_xp")
async def set_xp(interaction: discord.Interaction, xp: int):
    global WEEKLY_XP_REQUIREMENT

    if not is_admin(interaction):
        return await interaction.response.send_message("Admin only", ephemeral=True)

    WEEKLY_XP_REQUIREMENT = xp
    await interaction.response.send_message(f"XP requerido: {xp}")


# =========================
# START
# =========================
if __name__ == "__main__":
    keep_alive()
    bot.run(DISCORD_TOKEN)
