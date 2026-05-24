import json
import os
import logging
import asyncio
import random
import hashlib
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


def load_snapshot(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_snapshot(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


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
            activity=discord.Game(name="Kirka.io 🏆 - !help"),
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


# ==============================================================
# AQUÍ COMIENZAN LOS COMANDOS HÍBRIDOS (Prefijo y Slash)
# ==============================================================

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
    description="The main text of the embed (Use \\n for new lines)",
    color="Hex color code (e.g. 2b2d31 or ff0000)"
)
@app_commands.default_permissions(administrator=True) 
async def sayembed(ctx: commands.Context, title: str, description: str, color: str = "2b2d31"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    # ---> ESTA ES LA LÍNEA NUEVA QUE ARREGLA LOS SALTOS <---
    description = description.replace("\\n", "\n")

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
        "**`/register_monday`** - Save the clan's XP baseline (Monday).\n"
        "**`/register_sunday`** - Save the clan's XP snapshot (Sunday).\n"
        "**`/weekly_lb`** - Generate the weekly XP leaderboard.\n"
        "**`/set_xp [xp]`** - Update the weekly XP requirement.\n"
        "**`/delete_snaps`** - Clear the saved weekly snapshots.\n"
        "**`/say [msg]`** - Make the bot repeat your message."
    )
    embed.add_field(name="🛡️ Admin Commands", value=admin_cmds, inline=False)

    # Footer con el contacto de bugs
    embed.set_footer(
        text="🐛 Found a bug or have an issue? Contact: @clxzon_", 
        icon_url=ctx.author.display_avatar.url
    )

    await ctx.send(embed=embed)


@bot.hybrid_command(name="delete_snaps", description="Delete Monday and Sunday snapshots")
async def delete_snaps(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    deleted = []
    try:
        if MONDAY_SNAPSHOT_PATH.exists():
            MONDAY_SNAPSHOT_PATH.unlink()
            deleted.append("Monday")

        if SUNDAY_SNAPSHOT_PATH.exists():
            SUNDAY_SNAPSHOT_PATH.unlink()
            deleted.append("Sunday")

        if deleted:
            await ctx.send(f"Deleted snapshots: {', '.join(deleted)}")
        else:
            await ctx.send("No snapshot files found.")

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
