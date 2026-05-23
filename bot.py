import json
import os
import logging
import asyncio
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

# =========================
# SETUP
# =========================

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
KIRKA_API_KEY = os.getenv("KIRKA_API_KEY", "")
KIRKA_API_BASE = "https://api.kirka.io"

CLAN_NAME = os.getenv("KIRKA_CLAN_TAG", "UsAsOne!")

MONDAY_SNAPSHOT_PATH = Path("xp_monday.json")
SUNDAY_SNAPSHOT_PATH = Path("xp_sunday.json")

logging.basicConfig(level=logging.INFO)

# =========================
# KEEP ALIVE
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
# HTTP CLIENT
# =========================

class ClanClient:
    def __init__(self, base, key):
        self.base = base
        self.key = key
        self.session: aiohttp.ClientSession | None = None

    async def start(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def request(self, method, url, json=None):
        headers = {
            "accept": "application/json",
            "ApiKey": self.key
        }

        async with self.session.request(method, url, headers=headers, json=json) as r:
            return await r.json()

    async def get_clan(self, name):
        url = f"{self.base}/api/clan/{quote(name)}"
        return await self.request("GET", url)

    async def get_top_clans(self):
        url = f"{self.base}/api/leaderboard/clan"
        return await self.request("GET", url)

# =========================
# SNAPSHOTS
# =========================

def load_snapshot(path):
    if not path.exists():
        return None
    return json.loads(path.read_text())

def save_snapshot(path, data):
    path.write_text(json.dumps(data, indent=2))

def extract_members(data):
    out = {}
    for m in data.get("members", []):
        user = m.get("user", m)

        uid = str(user.get("id") or "")
        if not uid:
            continue

        out[uid] = {
            "name": user.get("name", "Unknown"),
            "shortId": user.get("shortId", "-"),
            "xp": int(m.get("allScores", m.get("scores", 0)))
        }

    return out

# =========================
# IMAGE TOP CLANS
# =========================

def generate_top_image(clans, page, total):
    img = Image.new("RGB", (900, 600), (20, 20, 35))
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default()

    draw.text((20, 20), "🏆 TOP CLANS GLOBAL", fill=(255, 215, 0), font=font)
    draw.text((20, 45), f"Page {page}/{total}", fill=(200, 200, 200), font=font)

    y = 100

    for i, c in enumerate(clans, start=1):
        draw.rectangle([20, y, 880, y+40], fill=(40, 40, 60))

        draw.text((30, y+10), f"{i}", fill="white", font=font)
        draw.text((80, y+10), c["name"], fill="white", font=font)
        draw.text((400, y+10), str(c["membersCount"]), fill="white", font=font)
        draw.text((600, y+10), f"{c['scores']:,}", fill="white", font=font)

        y += 45

    buf = BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

# =========================
# VIEW (PAGINATION)
# =========================

class TopView(discord.ui.View):
    def __init__(self, data):
        super().__init__(timeout=120)
        self.data = data
        self.page = 1
        self.per = 10

    def pages(self):
        return max(1, (len(self.data)+self.per-1)//self.per)

    def slice(self):
        s = (self.page-1)*self.per
        return self.data[s:s+self.per]

 async def refresh(self, interaction):
    page_data = self.slice()

    img = generate_top_image(page_data, self.page, self.pages())
    file = discord.File(img, "top.png")

    embed = discord.Embed(
        title="🏆 Global Top Clans",
        color=discord.Color.gold()
    )

    embed.add_field(name="📄 Página", value=f"{self.page}/{self.pages()}", inline=True)
    embed.add_field(name="📊 Clans", value=str(len(self.data)), inline=True)

    embed.set_image(url="attachment://top.png")

    await interaction.response.edit_message(
        embed=embed,
        attachments=[file],
        view=self
    )

    @discord.ui.button(label="⬅", style=discord.ButtonStyle.gray)
    async def back(self, i, b):
        if self.page > 1:
            self.page -= 1
        await self.refresh(i)

    @discord.ui.button(label="➡", style=discord.ButtonStyle.gray)
    async def next(self, i, b):
        if self.page < self.pages():
            self.page += 1
        await self.refresh(i)

# =========================
# BOT
# =========================

class Bot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.api = ClanClient(KIRKA_API_BASE, KIRKA_API_KEY)

    async def setup_hook(self):
        await self.api.start()
        await self.tree.sync()


bot = Bot()

# =========================
# TOP CLANS COMMAND
# =========================

@bot.tree.command(name="top_clans")
async def top_clans(interaction: discord.Interaction):
    await interaction.response.defer()

    data = await bot.api.get_top_clans()
    results = data.get("results", [])

    view = TopView(results)

    page_data = view.slice()

    img = generate_top_image(page_data, 1, view.pages())
    file = discord.File(img, "top.png")

    # =========================
    # EMBED
    # =========================
    embed = discord.Embed(
        title="🏆 Global Top Clans",
        description="Leaderboard oficial de Kirka",
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )

    embed.add_field(
        name="📊 Total clans",
        value=str(len(results)),
        inline=True
    )

    embed.add_field(
        name="📄 Página",
        value=f"1 / {view.pages()}",
        inline=True
    )

    embed.add_field(
        name="⚡ Status",
        value="Live data from api.kirka.io",
        inline=False
    )

    embed.set_image(url="attachment://top.png")

    await interaction.followup.send(
        embed=embed,
        file=file,
        view=view
    )
# =========================
# START
# =========================

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing DISCORD_TOKEN")

    keep_alive()
    bot.run(DISCORD_TOKEN)
