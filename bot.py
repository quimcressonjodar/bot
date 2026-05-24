import json
import os
import logging
import asyncio
import random
import hashlib
import pymongo
import uuid
from datetime import datetime, timezone
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client["kirka_bot"]
pets_col = db["pets"]
warns_col = db["warns"]
snaps_col = db["snapshots"]
eco_col = db["economy"]
def get_user_data(user_id: str):
    user = eco_col.find_one({"_id": user_id})

    if not user:
        user = {
            "_id": user_id,
            "wallet": 0,
            "bank": 0
        }
        eco_col.insert_one(user)

    # MIGRACIÓN automática del antiguo balance
    if "balance" in user:
        wallet_amount = user.get("balance", 0)

        eco_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "wallet": wallet_amount,
                    "bank": 0
                },
                "$unset": {
                    "balance": ""
                }
            }
        )

        user["wallet"] = wallet_amount
        user["bank"] = 0

    return user


def get_wallet(user_id: str) -> int:
    return get_user_data(user_id)["wallet"]


def get_bank(user_id: str) -> int:
    return get_user_data(user_id)["bank"]


def update_wallet(user_id: str, amount: int):
    eco_col.update_one(
        {"_id": user_id},
        {"$inc": {"wallet": amount}},
        upsert=True
    )


def update_bank(user_id: str, amount: int):
    eco_col.update_one(
        {"_id": user_id},
        {"$inc": {"bank": amount}},
        upsert=True
    )

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot activo"

def run():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

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
WELCOME_CHANNEL_ID = 1206229312743809054 
PET_SHOP = {
    # Tier 1: Básicos
    "dog":      {"price": 500,    "hp": 100, "damage": 20, "emoji": "🐕"},
    "cat":      {"price": 600,    "hp": 80,  "damage": 25, "emoji": "🐈"},
    
    # Tier 2: Avanzados
    "wolf":     {"price": 1500,   "hp": 150, "damage": 40, "emoji": "🐺"},
    "bear":     {"price": 2500,   "hp": 250, "damage": 35, "emoji": "🐻"},
    
    # Tier 3: Épicos
    "dragon":   {"price": 6000,   "hp": 350, "damage": 70, "emoji": "🐉"},
    "golem":    {"price": 7500,   "hp": 550, "damage": 50, "emoji": "🗿"},
    
    # Tier 4: Míticos (Muy caros)
    "phoenix":  {"price": 15000,  "hp": 400, "damage": 120, "emoji": "🐦‍🔥"},
    "kraken":   {"price": 25000,  "hp": 600, "damage": 150, "emoji": "🦑"},
    "titan":    {"price": 40000,  "hp": 1000, "damage": 200, "emoji": "👑"}
}

class PetSelect(discord.ui.Select):

    def __init__(self, user, pets):

        self.user = user
        self.pets = pets

        options = []

        for index, pet in enumerate(pets):

            options.append(
                discord.SelectOption(
                    label=f"{pet['type'].capitalize()}",
                    description=f"HP {pet['hp']} | DMG {pet['damage']}",
                    value=str(index)
                )
            )

        super().__init__(
            placeholder="Choose your pet...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ This menu isn't for you.",
                ephemeral=True
            )

        self.view.selected_pet = self.pets[int(self.values[0])]

        await interaction.response.send_message(
            f"✅ Selected **{self.view.selected_pet['type'].capitalize()}**",
            ephemeral=True
        )
class PetSelectionView(discord.ui.View):

    def __init__(self, user, pets):

        super().__init__(timeout=300)

        self.user = user
        self.selected_pet = None
        self.message = None

        self.add_item(PetSelect(user, pets))

    async def on_timeout(self):

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="⌛ Battle Cancelled",
            description=(
                "The battle request expired due to inactivity.\n\n"
                "No pet was selected in time."
            ),
            color=0xff0000
        )

        try:
            await self.message.edit(
                embed=embed,
                view=self
            )
        except:
            pass


class ClanClient:
    async def get_top_clans(self):
        url = f"{self.api_base}/api/leaderboard/clan"
        headers = {
            "ApiKey": self.api_key,
            "accept": "application/json"
        }

        async with self.session.get(url, headers=headers) as r:
            return await r.json()

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
        payload = await self._request_json_with_retry("GET", url)

        clan_data = self._normalize_clan_payload(payload)
        members = self._extract_members_list(clan_data)
        clan_data["members"] = members
        return clan_data

    def _normalize_clan_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            if any(k in payload for k in ("members", "clanUsers", "users", "players")):
                return payload
            nested = payload.get("data")
            if isinstance(nested, dict):
                return nested
            nested = payload.get("clan")
            if isinstance(nested, dict):
                return nested

        raise RuntimeError(f"Unexpected Kirka API format. Raw type: {type(payload).__name__}")

    def _extract_members_list(self, clan_data: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("members", "clanUsers", "users", "players"):
            members = clan_data.get(key)
            if isinstance(members, list):
                return members
        raise RuntimeError("Unexpected Kirka response: members list not found")


    async def get_clan_leaderboard(self) -> Any:
        url = f"{self.api_base}/api/leaderboard/clan"
        return await self._request_json_with_retry("GET", url)

    async def get_inventory_user(self, player_id: str, is_short_id: bool = True) -> Any:
        url = f"{self.api_base}/api/inventory/user"
        payload = {"id": player_id, "isShortId": is_short_id}
        return await self._request_json_with_retry("POST", url, json_payload=payload)

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
                async with self.session.request(method.upper(), url, headers=headers, json=json_payload) as response:
                    body = await response.text()
                    if response.status == 429:
                        retry_after = float(response.headers.get("Retry-After", "0") or 0)
                        delay = retry_after if retry_after > 0 else HTTP_RETRY_BASE_DELAY * attempt
                        await asyncio.sleep(delay)
                        continue
                    if response.status >= 500:
                        raise RuntimeError(f"Kirka temporary error {response.status}: {body[:200]}")
                    if response.status in {401, 403}:
                        raise RuntimeError("Kirka API rejected the key (401/403). Check KIRKA_API_KEY in .env")
                    if response.status < 200 or response.status >= 300:
                        raise RuntimeError(f"Kirka API error {response.status}: {body[:300]}")
                    return await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt < HTTP_MAX_RETRIES:
                    await asyncio.sleep(HTTP_RETRY_BASE_DELAY * attempt)

        raise RuntimeError(f"Failed request after {HTTP_MAX_RETRIES} attempts: {last_error}")


def load_snapshot(path) -> dict | None:
    snap_id = str(path)
    doc = snaps_col.find_one({"_id": snap_id})
    return doc["data"] if doc else None

def save_snapshot(path, data: dict) -> None:
    snap_id = str(path)
    snaps_col.update_one({"_id": snap_id}, {"$set": {"data": data}}, upsert=True)


# ACTUALIZADO: is_admin ahora verifica el context (ctx) de comandos híbridos
def is_admin(ctx: commands.Context) -> bool:
    if isinstance(ctx.author, discord.Member):
        return bool(ctx.author.guild_permissions.administrator)
    return False


def extract_member_map(clan_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in clan_data.get("members", []):
        if not isinstance(item, dict):
            continue
        user = item.get("user") if isinstance(item.get("user"), dict) else item

        user_id = str(user.get("id") or item.get("id") or user.get("userId") or "").strip()
        if not user_id:
            continue

        score_raw = item.get("allScores", item.get("scores", item.get("xp", 0)))
        try:
            all_scores = int(score_raw or 0)
        except (TypeError, ValueError):
            all_scores = 0

        result[user_id] = {
            "id": user_id,
            "name": str(user.get("name") or item.get("name") or "Unknown"),
            "shortId": str(user.get("shortId") or item.get("shortId") or "-"),
            "role": str(item.get("role") or "UNKNOWN"),
            "allScores": all_scores,
        }
    return result


def build_weekly_rows(monday: dict[str, dict[str, Any]], sunday: dict[str, dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    all_ids = set(monday.keys()) | set(sunday.keys())

    for user_id in all_ids:
        mon = monday.get(user_id)
        sun = sunday.get(user_id)

        if mon and sun:
            weekly_xp = sun["allScores"] - mon["allScores"]
            if weekly_xp < 0:
                status = "REVIEW"
            elif weekly_xp >= WEEKLY_XP_REQUIREMENT:
                status = "OK"
            else:
                status = "MISSING"
            rows.append([sun["name"], sun["shortId"], sun["role"], weekly_xp, status])
        elif sun and not mon:
            rows.append([sun["name"], sun["shortId"], sun["role"], 0, "JOINED"])
        elif mon and not sun:
            rows.append([mon["name"], mon["shortId"], mon["role"], 0, "LEFT"])

    rows.sort(key=lambda row: (row[4] not in {"OK", "MISSING", "REVIEW"}, -row[3], row[0]))
    return rows


def format_table(rows: list[list[Any]], headers: list[str]) -> str:
    if tabulate:
        return tabulate(rows, headers=headers, tablefmt="github")

    widths = [len(h) for h in headers]
    for row in rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(str(col)))

    def fmt_line(values: list[Any]) -> str:
        cells = [str(v).ljust(widths[i]) for i, v in enumerate(values)]
        return "| " + " | ".join(cells) + " |"

    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    lines = [fmt_line(headers), sep]
    lines.extend(fmt_line(row) for row in rows)
    return "\n".join(lines)


class WeeklyXPBot(commands.Bot):
    def __init__(self, clan_client: ClanClient):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        
        super().__init__(
            command_prefix="!", 
            intents=intents,
            status=discord.Status.online,
            activity=discord.Game(name="Kirka.io 🏆 !help"),
            help_command=None
        )
        self.clan_client = clan_client

    async def setup_hook(self) -> None:
        await self.clan_client.start()
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        logger.info(f"✅ ¡Bot conectado y listo como {self.user}!")
        # Forzamos la actualización de estado para quitar el modo Offline
        await self.change_presence(
            status=discord.Status.online, 
            activity=discord.Game(name="Kirka.io 🏆")
        )

    async def close(self) -> None:
        await self.clan_client.close()
        await super().close()
class BattleView(discord.ui.View):

    def __init__(self, challenger, opponent):
        super().__init__(timeout=60)

        self.challenger = challenger
        self.opponent = opponent

    @discord.ui.button(label="Accept Battle", style=discord.ButtonStyle.green, emoji="⚔️")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ This is not your battle request.",
                ephemeral=True
            )

        attacker_pet = pets_col.find_one({"_id": str(self.challenger.id)})
        defender_pet = pets_col.find_one({"_id": str(self.opponent.id)})

        attacker_power = attacker_pet["damage"] * random.uniform(0.8, 1.3)
        defender_power = defender_pet["damage"] * random.uniform(0.8, 1.3)

        battle_events = [
            "🌩️ A thunderstorm shakes the arena.",
            "🔥 The battlefield erupts in flames.",
            "🌑 Darkness surrounds both pets.",
            "⚡ Electric energy surges through the arena.",
            "❄️ A freezing wind slows everyone down.",
            "☠️ Ancient spirits awaken beneath the battlefield."
        ]

        event = random.choice(battle_events)

        attacker_hits = defender_pet["hp"] / attacker_power
        defender_hits = attacker_pet["hp"] / defender_power

        if attacker_hits <= defender_hits:
            winner = self.challenger
            loser = self.opponent
            winning_pet = attacker_pet
        else:
            winner = self.opponent
            loser = self.challenger
            winning_pet = defender_pet

        reward = random.randint(300, 900)

        update_wallet(str(winner.id), reward)

        embed = discord.Embed(
            title="⚔️ EPIC PET BATTLE",
            description=(
                f"{event}\n\n"
                f"🐾 **{self.challenger.display_name}** summoned **{attacker_pet['type'].capitalize()}**\n"
                f"🐾 **{self.opponent.display_name}** summoned **{defender_pet['type'].capitalize()}**\n\n"
                f"💥 The arena explodes with chaos...\n"
                f"🩸 Both pets fight with everything they have...\n\n"
                f"👑 **Winner:** {winner.mention}\n"
                f"🏆 Pet: **{winning_pet['type'].capitalize()}**\n"
                f"💰 Reward: 🪙 {reward:,}"
            ),
            color=0xff4500
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.red, emoji="❌")
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):

        if interaction.user.id != self.opponent.id:
            return await interaction.response.send_message(
                "❌ This is not your battle request.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="❌ Battle Declined",
            description=f"{self.opponent.mention} declined the battle request.",
            color=0xff0000
        )

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)


class TopClansPagination(discord.ui.View):
    # ACTUALIZADO: Ya no requiere 'interaction' en la inicialización
    def __init__(self, clans: list, page: int, per_page: int):
        super().__init__(timeout=120)
        self.clans = clans
        self.page = page
        self.per_page = per_page
        self.max_page = max(0, (len(clans) - 1) // per_page)
        self.update_buttons()

    def update_buttons(self):
        self.btn_prev.disabled = self.page == 0
        self.btn_next.disabled = self.page >= self.max_page

    async def update_message(self, interaction: discord.Interaction):
        image_path = generate_top_clans_image(self.clans, self.page, self.per_page)
        file = discord.File(image_path, filename="top_clans.png")
        self.update_buttons()
        await interaction.response.edit_message(attachments=[file], view=self)

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.gray)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.max_page, self.page + 1)
        await self.update_message(interaction)


def generate_top_clans_image(clans: list[dict], page: int = 0, per_page: int = 10):
    width, height = 1000, 850 
    img = Image.new("RGB", (width, height), (30, 31, 34)) 
    draw = ImageDraw.Draw(img)

    try:
        font_normal = ImageFont.truetype("arial.ttf", 32)
        font_bold = ImageFont.truetype("arialbd.ttf", 32)
        font_title = ImageFont.truetype("arialbd.ttf", 52)
        font_header = ImageFont.truetype("arialbd.ttf", 34)
    except:
        font_normal = ImageFont.load_default()
        font_bold = font_normal
        font_title = font_normal
        font_header = font_normal

    start = page * per_page
    end = start + per_page
    sliced = clans[start:end]

    draw.text((40, 40), "🏆 GLOBAL LEADERBOARD", fill=(255, 255, 255), font=font_title)
    
    page_text = f"PAGE {page+1} / {max(1, (len(clans)//per_page)+1)}"
    draw.text((width - 250, 55), page_text, fill=(150, 150, 150), font=font_bold)

    y_offset = 140
    cols = [40, 150, 540, 800] 
    headers = ["RANK", "CLAN", "EXPERIENCE", "USERS"]
    
    draw.rectangle([(20, y_offset), (width - 20, y_offset + 70)], fill=(43, 45, 49))
    
    for x, text in zip(cols, headers):
        draw.text((x, y_offset + 15), text, fill=(88, 101, 242), font=font_header)

    y_offset += 100 
    rank = start + 1

    for c in sliced:
        name = c.get("name", "Unknown")
        scores = c.get("scores", 0)
        members = c.get("membersCount", 0)

        is_my_clan = name.lower() == "usasone!"
        
        if is_my_clan:
            text_color = (255, 215, 0) 
            draw.rectangle([(20, y_offset - 10), (width - 20, y_offset + 55)], fill=(49, 51, 56), outline=(255, 215, 0), width=3)
            current_font = font_bold
        else:
            text_color = (220, 221, 222) 
            current_font = font_normal

        draw.text((cols[0], y_offset), f"#{rank}", fill=text_color, font=current_font)
        draw.text((cols[1], y_offset), name, fill=text_color, font=current_font)
        draw.text((cols[2], y_offset), f"{scores:,} XP", fill=text_color, font=current_font)
        draw.text((cols[3], y_offset), f"{members}", fill=text_color, font=current_font)

        y_offset += 65 
        rank += 1

    draw.rectangle([(20, height - 20), (width - 20, height - 15)], fill=(88, 101, 242))

    path = f"top_clans_page_{page}.png"
    img.save(path)
    return path



clan_client = ClanClient(api_base=KIRKA_API_BASE, api_key=KIRKA_API_KEY)
bot = WeeklyXPBot(clan_client=clan_client)






@bot.event
async def on_member_join(member: discord.Member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(
        title=f"Welcome to the server, {member.name}! 🎉",
        description=(
            f"Hello {member.mention}, we are glad to have you here!\n\n"
            f"📜 **First Step:** Please, read the rules in <#1206222685143826485>\n"
            f"⚔️ **Want to join?** If you want to apply for the clan, go to <#1206198139686617088>\n\n"
            f"Enjoy your stay!"
        ),
        color=0x2b2d31
    )
    
    embed.set_image(url="https://i.ibb.co/d4r7Z6f8/248-AB2-AF-21-F0-4384-A53-D-404328353301.png")
    
    await channel.send(content=f"Welcome {member.mention}!", embed=embed)

@bot.event
async def on_member_remove(member: discord.Member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(
        title="Goodbye! 👋",
        description=f"**{member.name}** has left the server. We will miss you!",
        color=0xff2a2a
    )
    await channel.send(embed=embed)
# ==============================================================
# SATELLITE: SISTEMA DE ADVERTENCIAS (BASE DE DATOS EN JSON)
# ==============================================================
WARNS_PATH = Path("warns.json")

def load_warns() -> dict:
    doc = warns_col.find_one({"_id": "all_warns"})
    return doc["data"] if doc else {}

def save_warns(data: dict):
    warns_col.update_one({"_id": "all_warns"}, {"$set": {"data": data}}, upsert=True)

def parse_duration(duration_str: str):
    """Parsea formatos como 10m, 2h, 1d a un objeto timedelta válido"""
    from datetime import timedelta
    try:
        if duration_str.endswith("m"):
            return timedelta(minutes=int(duration_str[:-1]))
        elif duration_str.endswith("h"):
            return timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith("d"):
            return timedelta(days=int(duration_str[:-1]))
        else:
            return timedelta(minutes=int(duration_str))
    except ValueError:
        return None

# ==============================================================
# CATEGORÍA 1: CASTIGOS Y SANCIONES
# ==============================================================

@bot.hybrid_command(name="ban", description="Ban a member from the server (Admin only)")
@app_commands.describe(member="The member to ban", reason="The reason for the ban")
@app_commands.default_permissions(administrator=True)
async def ban(ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    # Intentamos enviar el MD antes de banear
    try:
        await member.send(f"🔨 You have been **banned** from **{ctx.guild.name}**.\n**Reason:** {reason}")
    except discord.Forbidden:
        pass # Si tiene los MDs cerrados, simplemente lo ignoramos y seguimos
        
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **{member.name}** has been permanently banned. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to ban user: {e}", ephemeral=True)

@bot.hybrid_command(name="unban", description="Unban a user by their Discord ID (Admin only)")
@app_commands.describe(user_id="The unique ID of the user to unban")
@app_commands.default_permissions(administrator=True)
async def unban(ctx: commands.Context, user_id: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await ctx.guild.unban(user)
        await ctx.send(f"✅ Successfully unbanned **{user.name}** from the server.")
    except Exception as e:
        await ctx.send(f"❌ Failed to unban user. Make sure the ID is correct: {e}", ephemeral=True)

@bot.hybrid_command(name="kick", description="Kick a member from the server (Admin only)")
@app_commands.describe(member="The member to kick", reason="The reason for the kick")
@app_commands.default_permissions(administrator=True)
async def kick(ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    # Intentamos enviar el MD antes de expulsar
    try:
        await member.send(f"👢 You have been **kicked** from **{ctx.guild.name}**.\n**Reason:** {reason}")
    except discord.Forbidden:
        pass
        
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member.name}** has been kicked from the server. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to kick user: {e}", ephemeral=True)

@bot.hybrid_command(name="timeout", description="Timeout/Mute a member temporarily (Admin only)")
@app_commands.describe(member="The member", duration="Duration (e.g. 10m, 2h, 1d)", reason="Reason for timeout")
@app_commands.default_permissions(administrator=True)
async def timeout(ctx: commands.Context, member: discord.Member, duration: str, reason: str = "No reason provided"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    time_delta = parse_duration(duration)
    if not time_delta:
        return await ctx.send("❌ Invalid duration format! Use formats like `10m` (minutes), `2h` (hours), or `1d` (days).", ephemeral=True)
    
    # Intentamos enviar el MD antes de aplicar el timeout
    try:
        await member.send(f"🔇 You have been **timed out** in **{ctx.guild.name}** for `{duration}`.\n**Reason:** {reason}")
    except discord.Forbidden:
        pass # Si tiene los MDs cerrados, simplemente lo ignoramos y seguimos
    
    try:
        await member.timeout(time_delta, reason=reason)
        await ctx.send(f"🔇 **{member.name}** has been timed out for `{duration}`. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to apply timeout: {e}", ephemeral=True)

@bot.hybrid_command(name="untimeout", description="Remove timeout from a member (Admin only)")
@app_commands.describe(member="The member to untimeout")
@app_commands.default_permissions(administrator=True)
async def untimeout(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.timeout(None)
        await ctx.send(f"🔊 Timeout removed. **{member.name}** can now talk again.")
    except Exception as e:
        await ctx.send(f"❌ Failed to remove timeout: {e}", ephemeral=True)


# ==============================================================
# CATEGORÍA 2: LIMPIEZA Y CONTROL DEL CHAT
# ==============================================================

@bot.hybrid_command(name="purge", description="Purge a specified amount of messages (Admin only)")
@app_commands.describe(amount="Amount of messages to delete")
@app_commands.default_permissions(administrator=True)
async def purge(ctx: commands.Context, amount: int):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    if amount <= 0:
        return await ctx.send("Please specify a number greater than 0.", ephemeral=True)
    
    await ctx.defer(ephemeral=True)
    try:
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"🧹 Successfully deleted **{len(deleted)}** messages.", ephemeral=True)
    except Exception as e:
        await ctx.send(f"❌ Failed to purge messages: {e}", ephemeral=True)

@bot.hybrid_command(name="lock", description="Lock a text channel (Admin only)")
@app_commands.describe(channel="The channel to lock (Defaults to current)")
@app_commands.default_permissions(administrator=True)
async def lock(ctx: commands.Context, channel: discord.TextChannel = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    target_channel = channel or ctx.channel
    try:
        await target_channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"🔒 **{target_channel.mention}** has been locked down.")
    except Exception as e:
        await ctx.send(f"❌ Failed to lock channel: {e}", ephemeral=True)

@bot.hybrid_command(name="unlock", description="Unlock a previously locked channel (Admin only)")
@app_commands.describe(channel="The channel to unlock (Defaults to current)")
@app_commands.default_permissions(administrator=True)
async def unlock(ctx: commands.Context, channel: discord.TextChannel = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    target_channel = channel or ctx.channel
    try:
        await target_channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(f"🔓 **{target_channel.mention}** is now unlocked.")
    except Exception as e:
        await ctx.send(f"❌ Failed to unlock channel: {e}", ephemeral=True)

@bot.hybrid_command(name="slowmode", description="Set slowmode delay for a channel (Admin only)")
@app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)", channel="The channel")
@app_commands.default_permissions(administrator=True)
async def slowmode(ctx: commands.Context, seconds: int, channel: discord.TextChannel = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    target_channel = channel or ctx.channel
    try:
        await target_channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(f"⏱️ Slowmode has been disabled in {target_channel.mention}.")
        else:
            await ctx.send(f"⏱️ Slowmode set to **{seconds}** seconds in {target_channel.mention}.")
    except Exception as e:
        await ctx.send(f"❌ Failed to set slowmode: {e}", ephemeral=True)


# ==============================================================
# CATEGORÍA 3: SISTEMA DE ADVERTENCIAS (WARNS)
# ==============================================================

@bot.hybrid_command(name="warn", description="Issue a warning to a member (Admin only)")
@app_commands.describe(member="The member to warn", reason="The reason for the warning")
@app_commands.default_permissions(administrator=True)
async def warn(ctx: commands.Context, member: discord.Member, reason: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    
    if user_id not in warns_data:
        warns_data[user_id] = []
        
    warn_id = str(len(warns_data[user_id]) + 1)
    new_warn = {
        "id": warn_id,
        "reason": reason,
        "moderator": ctx.author.name,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    }
    warns_data[user_id].append(new_warn)
    save_warns(warns_data)
    
    # Intentamos enviar el MD para avisarle del Warn
    try:
        await member.send(f"⚠️ You received a **warning** in **{ctx.guild.name}**.\n**Reason:** {reason}\n*You now have {len(warns_data[user_id])} warnings.*")
    except discord.Forbidden:
        pass
    
    embed = discord.Embed(
        title="⚠️ Member Warned",
        description=f"**User:** {member.mention}\n**Reason:** {reason}\n**Total Warns:** {len(warns_data[user_id])}",
        color=0xffaa00
    )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="warns", description="Check a member's warning history (Admin only)")
@app_commands.describe(member="The member to check")
@app_commands.default_permissions(administrator=True)
async def check_warns(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    user_warns = warns_data.get(user_id, [])
    
    if not user_warns:
        return await ctx.send(f"✅ **{member.name}** has a clean record (0 warnings).")
        
    embed = discord.Embed(title=f"⚠️ Warning Record: {member.name}", color=0xffaa00)
    for w in user_warns:
        embed.add_field(
            name=f"ID: {w['id']} | {w['date']}",
            value=f"**Reason:** {w['reason']}\n**Staff:** {w['moderator']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="delwarn", description="Delete a specific warning from a member (Admin only)")
@app_commands.describe(member="The member", warn_id="The ID of the warning to remove")
@app_commands.default_permissions(administrator=True)
async def delwarn(ctx: commands.Context, member: discord.Member, warn_id: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    user_warns = warns_data.get(user_id, [])
    
    updated_warns = [w for w in user_warns if w['id'] != warn_id]
    
    if len(updated_warns) == len(user_warns):
        return await ctx.send("❌ Warning ID not found for this user.", ephemeral=True)
    
    # Re-indexar los warns restantes para que queden correlativos (1, 2, 3...)
    for idx, w in enumerate(updated_warns):
        w['id'] = str(idx + 1)
        
    warns_data[user_id] = updated_warns
    save_warns(warns_data)
    await ctx.send(f"✅ Successfully removed warning ID `{warn_id}` from **{member.name}**.")

@bot.hybrid_command(name="clearwarns", description="Clear all warnings from a member (Admin only)")
@app_commands.describe(member="The member to clear")
@app_commands.default_permissions(administrator=True)
async def clearwarns(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    if user_id in warns_data:
        del warns_data[user_id]
        save_warns(warns_data)
    await ctx.send(f"✅ Cleared all warnings for **{member.name}**.")


# ==============================================================
# CATEGORÍA 4: UTILIDADES DE GESTIÓN RÁPIDA
# ==============================================================

@bot.hybrid_command(name="setnick", description="Quickly change a member's nickname (Admin only)")
@app_commands.describe(member="The member", nickname="New nickname (Leave empty to reset)")
@app_commands.default_permissions(administrator=True)
async def setnick(ctx: commands.Context, member: discord.Member, nickname: str = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.edit(nick=nickname)
        await ctx.send(f"✅ Changed nickname for **{member.name}** to `{nickname or member.name}`.")
    except Exception as e:
        await ctx.send(f"❌ Failed to change nickname: {e}", ephemeral=True)

@bot.hybrid_command(name="role_add", description="Assign a role to a member (Admin only)")
@app_commands.describe(member="The member", role="The role to assign")
@app_commands.default_permissions(administrator=True)
async def role_add(ctx: commands.Context, member: discord.Member, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.add_roles(role)
        await ctx.send(f"✅ Assigned the role **{role.name}** to **{member.name}**.")
    except Exception as e:
        await ctx.send(f"❌ Failed to add role: {e}", ephemeral=True)

@bot.hybrid_command(name="role_remove", description="Remove a role from a member (Admin only)")
@app_commands.describe(member="The member", role="The role to remove")
@app_commands.default_permissions(administrator=True)
async def role_remove(ctx: commands.Context, member: discord.Member, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed the role **{role.name}** from **{member.name}**.")
    except Exception as e:
        await ctx.send(f"❌ Failed to remove role: {e}", ephemeral=True)


# ==============================================================
# CATEGORÍA 5: AUDITORÍA E INFORMACIÓN
# ==============================================================

@bot.hybrid_command(name="userinfo", description="Display detailed information about a member")
@app_commands.describe(member="The member to view (Defaults to yourself)")
async def userinfo(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    roles = [role.mention for role in target.roles[1:]] # Evita listar @everyone
    
    embed = discord.Embed(title=f"👤 User Profile: {target.name}", color=0x2b2d31)
    embed.set_thumbnail(url=target.display_avatar.url)
    
    embed.add_field(name="User ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Server Nickname", value=target.nick or "None", inline=True)
    embed.add_field(name="Account Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Joined Server", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "Unknown", inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "No roles assigned", inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="serverinfo", description="Display general information about this server")
async def serverinfo(ctx: commands.Context):
    guild = ctx.guild
    embed = discord.Embed(title=f"🏰 Server Information: {guild.name}", color=0x2b2d31)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
        
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Total Members", value=f"👥 {guild.member_count}", inline=True)
    embed.add_field(name="Channels", value=f"📝 {len(guild.text_channels)} Text | 🔊 {len(guild.voice_channels)} Voice", inline=True)
    embed.add_field(name="Created Date", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Boost Status", value=f"✨ Tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
    embed.set_footer(text=f"Server ID: {guild.id}")
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="avatar", description="Get a member's avatar in high resolution")
@app_commands.describe(member="The member (Defaults to yourself)")
async def avatar(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    embed = discord.Embed(title=f"🖼️ Avatar of {target.name}", color=0x2b2d31)
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="balance", aliases=["bal"], description="Check your economy profile")
async def balance(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author

    wallet = get_wallet(str(target.id))
    bank = get_bank(str(target.id))

    total = wallet + bank

    embed = discord.Embed(
        title=f"💳 {target.display_name}'s Economy",
        color=0x2b2d31
    )

    embed.add_field(
        name="💵 Wallet",
        value=f"🪙 {wallet:,}",
        inline=True
    )

    embed.add_field(
        name="🏦 Bank",
        value=f"🪙 {bank:,}",
        inline=True
    )

    embed.add_field(
        name="📈 Total Net Worth",
        value=f"🪙 {total:,}",
        inline=False
    )

    embed.set_thumbnail(url=target.display_avatar.url)

    await ctx.send(embed=embed)
@bot.hybrid_command(name="deposit", aliases=["dep"], description="Deposit coins into your bank")
async def deposit(ctx: commands.Context, amount: str):
    user_id = str(ctx.author.id)

    wallet = get_wallet(user_id)

    if amount.lower() == "all":
        amount = wallet
    else:
        try:
            amount = int(amount)
        except:
            return await ctx.send("❌ Invalid amount.", ephemeral=True)

    if amount <= 0:
        return await ctx.send("❌ Amount must be positive.", ephemeral=True)

    if amount > wallet:
        return await ctx.send("❌ You don't have enough coins.", ephemeral=True)

    update_wallet(user_id, -amount)
    update_bank(user_id, amount)

    embed = discord.Embed(
        title="🏦 Deposit Successful",
        description=f"You deposited 🪙 {amount:,} coins into your bank.",
        color=0x00ff00
    )

    await ctx.send(embed=embed)
@bot.hybrid_command(name="withdraw", aliases=["with"], description="Withdraw coins from your bank")
async def withdraw(ctx: commands.Context, amount: str):
    user_id = str(ctx.author.id)

    bank = get_bank(user_id)

    if amount.lower() == "all":
        amount = bank
    else:
        try:
            amount = int(amount)
        except:
            return await ctx.send("❌ Invalid amount.", ephemeral=True)

    if amount <= 0:
        return await ctx.send("❌ Amount must be positive.", ephemeral=True)

    if amount > bank:
        return await ctx.send("❌ You don't have enough bank coins.", ephemeral=True)

    update_bank(user_id, -amount)
    update_wallet(user_id, amount)

    embed = discord.Embed(
        title="💸 Withdrawal Successful",
        description=f"You withdrew 🪙 {amount:,} coins from your bank.",
        color=0x3498db
    )

    await ctx.send(embed=embed)

@bot.hybrid_command(name="work", description="Work to earn coins")
@commands.cooldown(1, 2700, commands.BucketType.user) # 45 mins
async def work(ctx: commands.Context):

    earnings = random.randint(250, 800)

    jobs = [
        "developed a futuristic Discord bot for a billionaire",
        "won a late-night poker tournament",
        "repaired a military drone for a secret agency",
        "hacked into an abandoned crypto vault",
        "worked overtime at a cyberpunk nightclub",
        "delivered illegal space tacos across the galaxy",
        "streamed games for 14 hours straight",
        "sold rare dragon eggs on the black market",
        "worked as a bodyguard for a mafia boss",
        "found ancient treasure hidden underground",
        "completed dangerous bounty hunter missions",
        "managed a shady underground casino",
        "worked at a futuristic AI laboratory",
        "helped a millionaire recover lost crypto",
        "participated in illegal street races",
        "sold enchanted weapons to traveling merchants",
        "worked as a mercenary during clan wars",
        "created viral memes that exploded online",
        "found money hidden behind a vending machine",
        "worked at a haunted hotel overnight"
    ]

    reason = random.choice(jobs)

    update_wallet(str(ctx.author.id), earnings)

    embed = discord.Embed(
        title="💼 Work Complete",
        description=f"You {reason} and earned 🪙 **{earnings:,}** coins.",
        color=0x00ff99
    )

    embed.set_footer(text="Come back in 45 minutes for another shift.")

    await ctx.send(embed=embed)
@work.error
async def work_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        minutes = int(error.retry_after // 60)
        seconds = int(error.retry_after % 60)
        await ctx.send(f"⏳ You are too tired! Come back to work in {minutes}m {seconds}s.", ephemeral=True)

@bot.hybrid_command(name="gamble", description="Gamble your coins on a 50/50 chance")
@app_commands.describe(amount="The amount of coins you want to bet (or 'all')")
async def gamble(ctx: commands.Context, amount: str):

    try:

        user_id = str(ctx.author.id)

        current_wallet = get_wallet(user_id)

        if amount.lower() == "all":
            bet = current_wallet
        else:
            try:
                bet = int(amount)
            except ValueError:
                return await ctx.send(
                    "❌ Please enter a valid number or 'all'.",
                    ephemeral=True
                )

        if bet <= 0:
            return await ctx.send(
                "❌ You must bet at least 1 coin.",
                ephemeral=True
            )

        if bet > current_wallet:
            return await ctx.send(
                f"❌ You only have 🪙 {current_wallet:,} in your wallet.",
                ephemeral=True
            )

        wins = random.choice([True, False])

        if wins:

            update_wallet(user_id, bet)

            new_balance = get_wallet(user_id)

            embed = discord.Embed(
                title="🎰 JACKPOT!",
                description=(
                    f"You won 🪙 **{bet:,}** coins!\n\n"
                    f"💵 Wallet Balance: 🪙 **{new_balance:,}**"
                ),
                color=0x00ff00
            )

        else:

            update_wallet(user_id, -bet)

            new_balance = get_wallet(user_id)

            embed = discord.Embed(
                title="📉 You Lost",
                description=(
                    f"You lost 🪙 **{bet:,}** coins.\n\n"
                    f"💵 Wallet Balance: 🪙 **{new_balance:,}**"
                ),
                color=0xff0000
            )

        await ctx.send(embed=embed)

    except Exception as e:
        logger.exception("GAMBLE COMMAND ERROR")
        await ctx.send(f"Error: {e}")
@bot.hybrid_command(name="daily", description="Claim your daily free coins")
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily(ctx: commands.Context):
    reward = 1000
    update_wallet(str(ctx.author.id), reward)

    new_balance = get_wallet(str(ctx.author.id))
    
    embed = discord.Embed(
        title="🎁 Daily Reward",
        description=f"You claimed your daily 🪙 {reward} coins.\nCome back tomorrow for more! Your balance is now 🪙 {new_balance:,}.",
        color=0x00ff00
    )
    await ctx.send(embed=embed)

@daily.error
async def daily_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        hours = int(error.retry_after // 3600)
        minutes = int((error.retry_after % 3600) // 60)
        await ctx.send(f"⏳ You already claimed your daily reward. Try again in {hours}h {minutes}m.", ephemeral=True)

@bot.hybrid_command(name="pay", description="Send coins to another member")
@app_commands.describe(member="The member to send coins to", amount="Amount of coins")
async def pay(ctx: commands.Context, member: discord.Member, amount: int):

    sender_id = str(ctx.author.id)
    receiver_id = str(member.id)

    if member.bot:
        return await ctx.send("❌ You cannot send coins to bots.", ephemeral=True)

    if sender_id == receiver_id:
        return await ctx.send("❌ You cannot pay yourself.", ephemeral=True)

    if amount <= 0:
        return await ctx.send("❌ Amount must be greater than 0.", ephemeral=True)

    sender_wallet = get_wallet(sender_id)

    if sender_wallet < amount:
        return await ctx.send(
            f"❌ You only have 🪙 {sender_wallet:,} in your wallet.",
            ephemeral=True
        )

    # TRANSFER
    update_wallet(sender_id, -amount)
    update_wallet(receiver_id, amount)

    embed = discord.Embed(
        title="💸 Payment Sent",
        description=(
            f"{ctx.author.mention} sent 🪙 **{amount:,}** coins "
            f"to {member.mention}."
        ),
        color=0x00ff99
    )

    embed.add_field(
        name="📤 Sender Wallet",
        value=f"🪙 {get_wallet(sender_id):,}",
        inline=True
    )

    embed.add_field(
        name="📥 Receiver Wallet",
        value=f"🪙 {get_wallet(receiver_id):,}",
        inline=True
    )

    await ctx.send(embed=embed)

@bot.hybrid_command(name="rob", description="Attempt to rob another member")
@commands.cooldown(1, 7200, commands.BucketType.user)
async def rob(ctx: commands.Context, member: discord.Member):

    thief_id = str(ctx.author.id)
    target_id = str(member.id)

    if thief_id == target_id:
        return await ctx.send("❌ You cannot rob yourself.", ephemeral=True)

    target_wallet = get_wallet(target_id)

    if target_wallet < 300:
        return await ctx.send("❌ This user doesn't have enough wallet coins to rob.", ephemeral=True)

    success_messages = [
        "jumped through a window like a movie thief",
        "pickpocketed them during a crowded concert",
        "used fake security credentials to access their vault",
        "escaped through the rooftops after the robbery",
        "executed the perfect stealth mission",
        "used smoke grenades and escaped unseen",
        "hacked their crypto wallet remotely"
    ]

    fail_messages = [
        "tripped the alarm system",
        "got caught by security cameras",
        "accidentally robbed a police officer",
        "left fingerprints everywhere",
        "triggered laser security defenses",
        "was betrayed by your getaway driver",
        "got tackled by bodyguards"
    ]

    success = random.choice([True, False])

    if success:

        stolen = random.randint(150, int(target_wallet * 0.35))

        update_wallet(target_id, -stolen)
        update_wallet(thief_id, stolen)

        msg = random.choice(success_messages)

        embed = discord.Embed(
            title="🥷 Successful Robbery",
            description=(
                f"You {msg}.\n\n"
                f"You stole 🪙 **{stolen:,}** from {member.mention}."
            ),
            color=0x00ff00
        )

    else:

        fine = random.randint(150, 500)

        update_wallet(thief_id, -fine)

        msg = random.choice(fail_messages)

        embed = discord.Embed(
            title="🚨 Robbery Failed",
            description=(
                f"You {msg}.\n\n"
                f"You paid a fine of 🪙 **{fine:,}**."
            ),
            color=0xff0000
        )

    await ctx.send(embed=embed)

@rob.error
async def rob_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        minutes = int(error.retry_after // 60)
        await ctx.send(f"⏳ The cops are still looking for you! Lay low for {minutes}m.", ephemeral=True)
@bot.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="Shows the richest members")
async def leaderboard(ctx: commands.Context):

    users = list(eco_col.find())

    users.sort(
        key=lambda u: u.get("wallet", 0) + u.get("bank", 0),
        reverse=True
    )

    users = users[:10]

    embed = discord.Embed(
        title="🏆 Global Economy Leaderboard",
        color=0xffd700
    )

    description = ""

    for index, user_data in enumerate(users, start=1):

        user_id = int(user_data["_id"])

        total = user_data.get("wallet", 0) + user_data.get("bank", 0)

        member = ctx.guild.get_member(user_id)

        if member:
            name = member.display_name
        else:
            name = f"Unknown User ({user_id})"

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }

        medal = medals.get(index, f"`#{index}`")

        description += (
            f"{medal} **{name}** — 🪙 {total:,}\n"
        )

    embed.description = description

    await ctx.send(embed=embed)

@bot.hybrid_command(name="top_clans", description="View the top clans leaderboard")
async def top_clans(ctx: commands.Context):
    await ctx.defer()
    try:
        data = await bot.clan_client.get_top_clans()
        clans = data.get("results", [])
        if not clans:
            return await ctx.send("❌ No clan data found.")

        view = TopClansPagination(clans, 0, 10)
        image_path = generate_top_clans_image(clans, 0, 10)
        file = discord.File(image_path, filename="top_clans.png")
        await ctx.send(file=file, view=view)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


@bot.hybrid_command(name="flip", description="Flip a coin: Heads or Tails")
async def flip(ctx: commands.Context):
    # 1. Enviamos el mensaje inicial SIN el emoji
    msg = await ctx.send("Flipping the coin...")
    
    # 2. Recreamos la semilla de forma justa
    unique_id = str(ctx.interaction.id if ctx.interaction else ctx.message.id)
    seed_int = int(hashlib.sha256(unique_id.encode()).hexdigest(), 16)
    
    # 3. Calculamos el resultado
    local_random = random.Random(seed_int)
    result = local_random.choice(["Heads", "Tails"])
    
    # 4. Hacemos una micropausa de 1.5 segundos para la intriga
    await asyncio.sleep(1)
    
    # 5. Editamos el mensaje para que aparezca el emoji JUNTO al resultado
    await msg.edit(content=f"Flipping the coin... 🪙 **{result}**")
@bot.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="The question you want to ask")
async def eight_ball(ctx: commands.Context, question: str):
    responses = [
        "It is certain.", "It is decidedly so.", "Without a doubt.",
        "Yes - definitely.", "You may rely on it.", "As I see it, yes.",
        "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
        "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
        "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.",
        "Outlook not so good.", "Very doubtful."
    ]
    answer = random.choice(responses)
    
    # Creamos un Embed elegante (puedes cambiar el color si quieres)
    embed = discord.Embed(color=0x2b2d31)
    
    # Colocamos el nombre del usuario delante de la pregunta y la respuesta abajo
    embed.description = (
        f"🎱 **{ctx.author.display_name} asks:** {question}\n"
        f"💬 **Answer:** {answer}"
    )
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="item", description="Check skin details with strict search")
@app_commands.describe(name="Exact name of the skin (e.g., Nova)")
async def item_lookup(ctx: commands.Context, name: str):
    await ctx.defer()
    try:
        url = f"{KIRKA_API_BASE}/api/inventory/items"
        all_items = await bot.clan_client._request_json_with_retry("GET", url)

        # 1. BUSQUEDA ESTRICTA (Comparación exacta ignorando mayúsculas)
        found_item = next((i for i in all_items if i.get('name', '').lower() == name.lower()), None)

        # 2. SI NO HAY COINCIDENCIA EXACTA, BUSCAMOS PARECIDOS
        if not found_item:
            # Filtramos todos los que contengan la palabra para sugerirlos
            suggestions = [i.get('name') for i in all_items if name.lower() in i.get('name', '').lower()]
            # Limitamos a las primeras 10 sugerencias para no llenar el chat
            suggestions = suggestions[:10]

            error_msg = f"🔍 **Item not found:** `{name}`"
            if suggestions:
                list_str = "\n".join([f"• {s}" for s in suggestions])
                error_msg += f"\n\n**Did you mean one of these?**\n{list_str}"
            
            return await ctx.send(error_msg)

        # 3. SI LO ENCONTRÓ (Continúa el código normal)
        item_name = found_item.get('name', 'Unknown')
        rarity = found_item.get('rarity', 'COMMON').upper()
        item_type = found_item.get('type', 'ITEM').replace('_', ' ')
        total_owned = found_item.get('totalOwned', 0)
        image_url = found_item.get('renderUrl')

        colors = {
            "COMMON": 0xaaaaaa, "RARE": 0x5555ff, "EPIC": 0xaa00aa,
            "LEGENDARY": 0xffaa00, "MYTHICAL": 0xff5555, "EXOTIC": 0x55ffff
        }
        
        embed = discord.Embed(
            title=f"✨ {item_name}",
            description=f"**Category:** {item_type}",
            color=colors.get(rarity, 0xffffff)
        )

        embed.add_field(name="Tier", value=f"**{rarity}**", inline=True)
        embed.add_field(name="Global Supply", value=f"**{total_owned:,}** owned", inline=True)
        
        if total_owned < 500:
            market_tip = "💎 **High Value:** Extremely rare supply."
        elif total_owned < 2000:
            market_tip = "⚖️ **Medium Value:** Limited edition."
        else:
            market_tip = "🛒 **Common Item:** High supply, lower price."
        
        embed.add_field(name="Market Status", value=market_tip, inline=False)

        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(text="Data provided by Kirka.io")
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"⚠️ An error occurred: {e}")


@bot.hybrid_command(name="register_monday", description="Save Monday baseline snapshot")
async def register_monday(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    await ctx.defer()
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": extract_member_map(clan_data),
        }
        save_snapshot(MONDAY_SNAPSHOT_PATH, snapshot)
        await ctx.send(
            f"Monday snapshot saved in `{MONDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members."
        )
    except Exception as exc:
        await ctx.send(f"Failed to save Monday snapshot: {exc}")


@bot.hybrid_command(name="register_sunday", description="Save Sunday snapshot")
async def register_sunday(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    await ctx.defer()
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": extract_member_map(clan_data),
        }
        save_snapshot(SUNDAY_SNAPSHOT_PATH, snapshot)
        await ctx.send(
            f"Sunday snapshot saved in `{SUNDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members."
        )
    except Exception as exc:
        await ctx.send(f"Failed to save Sunday snapshot: {exc}")


@bot.hybrid_command(name="weekly_lb", description="Build weekly leaderboard from Monday/Sunday JSON files")
async def weekly_lb(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    await ctx.defer()

    try:
        monday_data = load_snapshot(MONDAY_SNAPSHOT_PATH)
        sunday_data = load_snapshot(SUNDAY_SNAPSHOT_PATH)

        if not monday_data or not sunday_data:
            return await ctx.send(
                "Need both files first. Run `/register_monday` and `/register_sunday` before `/weekly_lb`."
            )

        rows = build_weekly_rows(monday_data["members"], sunday_data["members"])

        lines = []
        header = f"{'Player':<18} {'Short ID':<10} {'XP':>10}   Status"
        lines.append(header)
        lines.append("-" * 60)

        for row in rows:
            player = str(row[0])[:18]
            short_id = str(row[1])[:10]
            role = str(row[2]).upper()
            xp = f"{row[3]:,}"
            status = row[4]

            if role == "LEADER":
                player_color = "\u001b[33;1m"
            elif role == "OFFICER":
                player_color = "\u001b[34;1m"
            elif role == "NEWBIE":
                player_color = "\u001b[36m"
            else:
                player_color = "\u001b[37m"

            if status == "OK":
                status_color = "\u001b[32m"
            elif status == "MISSING":
                status_color = "\u001b[31m"
            elif status == "REVIEW":
                status_color = "\u001b[33m"
            elif status == "JOINED":
                status_color = "\u001b[36m"
            elif status == "LEFT":
                status_color = "\u001b[35m"
            else:
                status_color = "\u001b[0m"

            reset = "\u001b[0m"

            line = (
                f"{player_color}{player:<18}{reset} "
                f"{short_id:<10} "
                f"{xp:>10}   "
                f"{status_color}{status}{reset}"
            )
            lines.append(line)

        report_header = (
            f"Clan: {sunday_data['clan_name']}\n"
            f"Requirement: {WEEKLY_XP_REQUIREMENT:,} XP\n"
            f"Monday: {monday_data['timestamp_utc']}\n"
            f"Sunday: {sunday_data['timestamp_utc']}\n\n"
        )

        chunks = []
        current_chunk = report_header + "```ansi\n"

        for line in lines:
            test_chunk = current_chunk + line + "\n```"
            if len(test_chunk) > 1900:
                current_chunk += "```"
                chunks.append(current_chunk)
                current_chunk = "```ansi\n" + line + "\n"
            else:
                current_chunk += line + "\n"

        current_chunk += "```"
        chunks.append(current_chunk)

        for i, chunk in enumerate(chunks):
            if i == 0:
                await ctx.send(chunk)
            else:
                await ctx.channel.send(chunk)

    except Exception as exc:
        await ctx.send(f"Failed to build leaderboard: {exc}")


@bot.hybrid_command(name="set_xp", description="Set weekly XP requirement (admin only)")
@app_commands.describe(xp="New weekly XP requirement")
async def set_xp(ctx: commands.Context, xp: int) -> None:
    global WEEKLY_XP_REQUIREMENT
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    if xp <= 0:
        return await ctx.send("XP requirement must be greater than 0.", ephemeral=True)

    WEEKLY_XP_REQUIREMENT = xp
    await ctx.send(f"Weekly XP requirement updated to {WEEKLY_XP_REQUIREMENT:,} XP.")
@bot.hybrid_command(name="sayembed", description="Send a custom embed message (Admin only)")
@app_commands.describe(
    title="Title of the embed",
    description="The main text of the embed",
    color="Hex color code (e.g. 2b2d31 or ff0000)"
)
@app_commands.default_permissions(administrator=True) 
async def sayembed(ctx: commands.Context, title: str, description: str, color: str = "2b2d31"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)


    try:
        color_int = int(color.lstrip('#'), 16)
    except ValueError:
        color_int = 0x2b2d31 

    embed = discord.Embed(title=title, description=description, color=color_int)

    if ctx.interaction is None: 
        try:
            await ctx.message.delete() 
        except discord.Forbidden:
            pass
        await ctx.send(embed=embed)
    else:
        await ctx.send("Embed sent!", ephemeral=True)
        await ctx.channel.send(embed=embed)


@bot.hybrid_command(name="clan_info", description="Detailed statistics for the current clan")
async def clan_info(ctx: commands.Context) -> None:
    await ctx.defer()
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        members = clan_data.get("members", [])
        all_scores = int(clan_data.get("allScores", clan_data.get("scores", 0)) or 0)
        month_scores = int(clan_data.get("monthScores", 0) or 0)
        
        desc = str(clan_data.get("description") or "No description provided.")
        if len(desc) > 250:
            desc = desc[:247] + "..."

        embed = discord.Embed(
            title=f"🏰 Clan Profile: {clan_data.get('name', CLAN_NAME)}",
            description=f"```\n{desc}\n```",
            color=0xffd700,
            timestamp=datetime.now(timezone.utc),
        )
        
        embed.add_field(name="👥 Total Members", value=f"**{len(members)}** / 100", inline=True)
        embed.add_field(name="⭐ Lifetime XP", value=f"**{all_scores:,}**", inline=True)
        embed.add_field(name="📅 Monthly XP", value=f"**{month_scores:,}**", inline=True)
        embed.add_field(name="👑 Clan Leader", value="`AIMTOME`", inline=False)
        embed.set_footer(text="Kirka.io API System • Updated")
        
        embed.set_author(name="Clan Intelligence Module", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)
    except Exception as exc:
        await ctx.send(f"❌ Error fetching clan info: {exc}")


@bot.hybrid_command(name="say", description="Make the bot say something (Admin only)")
@app_commands.describe(message="The message you want the bot to repeat")
@app_commands.default_permissions(administrator=True) 
async def say(ctx: commands.Context, message: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    # Si usaste el prefijo (!say)
    if ctx.interaction is None: 
        try:
            await ctx.message.delete() # Borra el mensaje donde escribiste el comando
        except discord.Forbidden:
            pass
        # No mandamos confirmación, solo enviamos tu mensaje directamente
        await ctx.send(message)
    
    # Si usaste el Slash Command (/say)
    else:
        # Aquí SÍ funciona el mensaje oculto
        await ctx.send("Message sent!", ephemeral=True)
        await ctx.channel.send(message)
class RPSView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=60)
        self.player = player

    async def handle_choice(self, interaction: discord.Interaction, user_choice: str):
        if interaction.user != self.player:
            return await interaction.response.send_message("❌ This is not your game! Start your own with /rps", ephemeral=True)
        
        choices = ["rock", "paper", "scissors"]
        bot_choice = random.choice(choices)
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        if user_choice == bot_choice:
            result = "It's a tie! 🤝"
            color = 0xffff00
        elif (user_choice == "rock" and bot_choice == "scissors") or \
             (user_choice == "paper" and bot_choice == "rock") or \
             (user_choice == "scissors" and bot_choice == "paper"):
            result = "You win! 🎉"
            color = 0x00ff00
        else:
            result = "I win! 🤖"
            color = 0xff0000

        embed = discord.Embed(title="Rock, Paper, Scissors", color=color)
        embed.add_field(name="You chose", value=f"{emojis[user_choice]} **{user_choice.capitalize()}**", inline=True)
        embed.add_field(name="I chose", value=f"{emojis[bot_choice]} **{bot_choice.capitalize()}**", inline=True)
        embed.add_field(name="Result", value=f"**{result}**", inline=False)
        
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.blurple)
    async def rock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.gray)
    async def paper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.red)
    async def scissors_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")

@bot.hybrid_command(name="rps", description="Play Rock, Paper, Scissors against the bot")
async def rps(ctx: commands.Context):
    embed = discord.Embed(
        title="Rock, Paper, Scissors", 
        description="Choose your weapon below! 👇", 
        color=0x2b2d31
    )
    view = RPSView(ctx.author)
    await ctx.send(embed=embed, view=view)
@bot.hybrid_command(name="help", description="Show all available commands")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="🏆 Kirka.io Bot | Command List",
        description="Here is a list of all available commands to manage the clan and have fun! 🎮",
        color=0x2b2d31 # Color oscuro elegante de Discord
    )

    # Comandos Públicos
    public_cmds = (
        "**`/top_clans`** - View the global Kirka.io top clans leaderboard.\n"
        "**`/clan_info`** - View detailed statistics and info for our clan.\n"
        "**`/item [name]`** - Check a skin's rarity, global supply, and market value.\n"
        "**`/flip`** - Flip a coin (Heads or Tails).\n"
        "**`/8ball [question]`** - Ask the magic 8-ball a question.\n"
        "**`/rps`** - Play Rock, Paper, Scissors against the bot."
    )
    embed.add_field(name="🌍 Public Commands", value=public_cmds, inline=False)

    # Comandos de Administrador
    admin_cmds = (
        "**`/register_monday / register_sunday`** - Manage snapshots.\n"
        "**`/weekly_lb / set_xp / delete_snaps`** - Leaderboard config.\n"
        "**`/purge [amount]`** - Delete messages from the channel.\n"
        "**`/ban / unban / kick`** - Severe user punishments.\n"
        "**`/timeout / untimeout`** - Mute or unmute members.\n"
        "**`/lock / unlock / slowmode`** - Control chat flows.\n"
        "**`/warn / warns / delwarn`** - Manage warning system.\n"
        "**`/role_add / role_remove / setnick`** - Quick member management.\n"
        "**`/say / sayembed`** - Make the bot talk."
    )
    embed.add_field(name="🛡️ Admin Commands", value=admin_cmds, inline=False)

    # Footer con el contacto de bugs
    embed.set_footer(
        text="🐛 Found a bug or have an issue? Contact: @clxzon_", 
        icon_url=ctx.author.display_avatar.url
    )

    await ctx.send(embed=embed)
@bot.hybrid_command(name="shop", description="View and buy animals for battle")
@app_commands.describe(action="Choose 'view' to see the shop or 'buy' to purchase", pet_name="Name of the pet to buy")
async def shop(ctx: commands.Context, action: str = "view", pet_name: str = None):
    user_id = str(ctx.author.id)

    if action.lower() == "view":
        embed = discord.Embed(title="🏪 Pet Shop", description="Welcome to the battle pet shop!", color=0x3498db)
        for name, stats in PET_SHOP.items():
            embed.add_field(
                name=f"{stats['emoji']} {name.capitalize()} - 🪙 {stats['price']} coins",
                value=f"HP: {stats['hp']} | Damage: {stats['damage']}",
                inline=False
            )
        return await ctx.send(embed=embed)

    elif action.lower() == "buy":
        if not pet_name or pet_name.lower() not in PET_SHOP:
            return await ctx.send("❌ Please specify a valid pet name from the shop.", ephemeral=True)

        pet_key = pet_name.lower()
        pet_data = PET_SHOP[pet_key]
        balance = get_wallet(user_id)

        if balance < pet_data["price"]:
            return await ctx.send("❌ You don't have enough coins for this pet.", ephemeral=True)

                pet_instance = {
            "pet_id": str(uuid.uuid4()),
            "type": pet_data["type"],
            "hp": pet_data["hp"],
            "damage": pet_data["damage"]
        }

        pets_col.update_one(
            {"_id": user_id},
            {
                "$push": {
                    "pets": pet_instance
                }
            },
            upsert=True
        )

        update_wallet(user_id, -pet_data["price"])

        embed = discord.Embed(
            title="🎉 Pet Adopted!",
            description=f"You successfully bought a {pet_data['emoji']} {pet_key.capitalize()}!\nUse `/battle` to fight other members.",
            color=0x00ff00
        )

        await ctx.send(embed=embed)
@bot.hybrid_command(name="battle", description="Challenge another player")
async def battle(ctx: commands.Context, opponent: discord.Member):

    if opponent.bot:
        return await ctx.send("❌ You cannot battle bots.")

    if opponent.id == ctx.author.id:
        return await ctx.send("❌ You cannot battle yourself.")

    challenger_data = pets_col.find_one({"_id": str(ctx.author.id)})
    opponent_data = pets_col.find_one({"_id": str(opponent.id)})

    if not challenger_data or not challenger_data.get("pets"):
        return await ctx.send("❌ You don't own any pets.")

    if not opponent_data or not opponent_data.get("pets"):
        return await ctx.send("❌ This user has no pets.")

    challenger_view = PetSelectionView(
        ctx.author,
        challenger_data["pets"]
    )

    opponent_view = PetSelectionView(
        opponent,
        opponent_data["pets"]
    )

    embed1 = discord.Embed(
        title="🐾 Choose Your Pet",
        description="Select the pet you'll send into battle.",
        color=0x00ff99
    )

    await ctx.send(
        content=ctx.author.mention,
        embed=embed1,
        view=challenger_view
    )

    embed2 = discord.Embed(
        title="⚔️ Battle Request",
        description=(
            f"{ctx.author.mention} challenged you.\n"
            f"Choose your fighter."
        ),
        color=0xff9900
    )

    await ctx.send(
        content=opponent.mention,
        embed=embed2,
        view=opponent_view
    )

    await asyncio.sleep(15)

    if not challenger_view.selected_pet:
        return await ctx.send("❌ Challenger didn't select a pet.")

    if not opponent_view.selected_pet:
        return await ctx.send("❌ Opponent didn't select a pet.")

    pet1 = challenger_view.selected_pet
    pet2 = opponent_view.selected_pet

    pet1_power = pet1["damage"] * random.uniform(0.8, 1.4)
    pet2_power = pet2["damage"] * random.uniform(0.8, 1.4)

    battle_events = [
        "🌩️ Thunder crashes across the arena.",
        "🔥 Lava erupts beneath the fighters.",
        "⚡ Electricity surges through the battlefield.",
        "☠️ Ancient spirits awaken nearby.",
        "🌪️ Violent winds shake the arena."
    ]

    event = random.choice(battle_events)

    if pet1_power > pet2_power:
        winner = ctx.author
        winning_pet = pet1
    else:
        winner = opponent
        winning_pet = pet2

    reward = random.randint(500, 1200)

    update_wallet(str(winner.id), reward)

    embed = discord.Embed(
        title="⚔️ EPIC PET BATTLE",
        description=(
            f"{event}\n\n"
            f"🐾 {ctx.author.display_name} used **{pet1['type'].capitalize()}**\n"
            f"🐾 {opponent.display_name} used **{pet2['type'].capitalize()}**\n\n"
            f"💥 The battle shakes the entire arena...\n\n"
            f"👑 Winner: {winner.mention}\n"
            f"🏆 Winning Pet: **{winning_pet['type'].capitalize()}**\n"
            f"💰 Prize: 🪙 {reward:,}"
        ),
        color=0xff4500
    )

    await ctx.send(embed=embed)

@battle.error
async def battle_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandOnCooldown):
        minutes = int(error.retry_after // 60)
        seconds = int(error.retry_after % 60)
        await ctx.send(f"⏳ Your pet is resting. Try again in {minutes}m {seconds}s.", ephemeral=True)
@bot.hybrid_command(name="pets", description="View your pet collection")
async def pets(ctx: commands.Context):

    data = pets_col.find_one({"_id": str(ctx.author.id)})

    if not data or not data.get("pets"):
        return await ctx.send("❌ You don't own any pets.")

    embed = discord.Embed(
        title=f"🐾 {ctx.author.display_name}'s Pets",
        color=0x00ff99
    )

    description = ""

    for index, pet in enumerate(data["pets"], start=1):

        description += (
            f"**{index}. {pet['type'].capitalize()}**\n"
            f"❤️ HP: {pet['hp']}\n"
            f"⚔️ Damage: {pet['damage']}\n\n"
        )

    embed.description = description

    await ctx.send(embed=embed)


@bot.hybrid_command(name="delete_snaps", description="Delete Monday and Sunday snapshots")
async def delete_snaps(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    try:
        snaps_col.delete_many({})
        await ctx.send("Deleted snapshots: Monday, Sunday")
    except Exception as exc:
        await ctx.send(f"Failed deleting snapshots: {exc}")


def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")
    if not KIRKA_API_KEY:
        raise RuntimeError("Missing required environment variable: KIRKA_API_KEY")


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    bot.run(DISCORD_TOKEN)
