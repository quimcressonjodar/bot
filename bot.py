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

app = Flask('')

@app.route('/')
def home():
    return "Bot activo"

def run():
    app.run(host='0.0.0.0', port=10000)

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


def is_admin(interaction: discord.Interaction) -> bool:
    return bool(interaction.user.guild_permissions.administrator)


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
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.clan_client = clan_client

    async def setup_hook(self) -> None:
        await self.clan_client.start()
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def close(self) -> None:
        await self.clan_client.close()
        await super().close()


clan_client = ClanClient(api_base=KIRKA_API_BASE, api_key=KIRKA_API_KEY)
bot = WeeklyXPBot(clan_client=clan_client)


@bot.tree.command(name="register_monday", description="Save Monday baseline snapshot")
async def register_monday(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": extract_member_map(clan_data),
        }
        save_snapshot(MONDAY_SNAPSHOT_PATH, snapshot)
        await interaction.followup.send(
            f"Monday snapshot saved in `{MONDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members."
        )
    except Exception as exc:
        await interaction.followup.send(f"Failed to save Monday snapshot: {exc}")


@bot.tree.command(name="register_sunday", description="Save Sunday snapshot")
async def register_sunday(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": extract_member_map(clan_data),
        }
        save_snapshot(SUNDAY_SNAPSHOT_PATH, snapshot)
        await interaction.followup.send(
            f"Sunday snapshot saved in `{SUNDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members."
        )
    except Exception as exc:
        await interaction.followup.send(f"Failed to save Sunday snapshot: {exc}")

@bot.tree.command(name="weekly_lb", description="Build weekly leaderboard from Monday/Sunday JSON files")
async def weekly_lb(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return

    await interaction.response.defer(thinking=True)

    try:
        monday_data = load_snapshot(MONDAY_SNAPSHOT_PATH)
        sunday_data = load_snapshot(SUNDAY_SNAPSHOT_PATH)

        if not monday_data or not sunday_data:
            await interaction.followup.send(
                "Need both files first. Run /register_monday and /register_sunday before /weekly_lb."
            )
            return

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

            # =========================
            # PLAYER NAME COLORS BY ROLE
            # =========================
            if role == "LEADER":
                player_color = "\u001b[33;1m"   # Bright Yellow
            elif role == "OFFICER":
                player_color = "\u001b[34;1m"   # Bright Blue
            elif role == "NEWBIE":
                player_color = "\u001b[36m"     # Cyan
            else:
                player_color = "\u001b[37m"     # White

            # =========================
            # STATUS COLORS
            # =========================
            if status == "OK":
                status_color = "\u001b[32m"     # Green
            elif status == "MISSING":
                status_color = "\u001b[31m"     # Red
            elif status == "REVIEW":
                status_color = "\u001b[33m"     # Yellow
            elif status == "JOINED":
                status_color = "\u001b[36m"     # Cyan
            elif status == "LEFT":
                status_color = "\u001b[35m"     # Magenta
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

        # =========================
        # SPLIT INTO MULTIPLE MESSAGES
        # =========================
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

        # =========================
        # SEND MESSAGES
        # =========================
        for i, chunk in enumerate(chunks):
            if i == 0:
                await interaction.followup.send(chunk)
            else:
                await interaction.channel.send(chunk)

    except Exception as exc:
        await interaction.followup.send(f"Failed to build leaderboard: {exc}")
@bot.tree.command(name="set_xp", description="Set weekly XP requirement (admin only)")
@app_commands.describe(xp="New weekly XP requirement")
async def set_xp(interaction: discord.Interaction, xp: int) -> None:
    global WEEKLY_XP_REQUIREMENT
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return

    if xp <= 0:
        await interaction.response.send_message("XP requirement must be greater than 0.", ephemeral=True)
        return

    WEEKLY_XP_REQUIREMENT = xp
    await interaction.response.send_message(f"Weekly XP requirement updated to {WEEKLY_XP_REQUIREMENT:,} XP.")


@bot.tree.command(name="clan_info", description="Show current clan info from Kirka API")
async def clan_info(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        members = clan_data.get("members", [])
        all_scores = int(clan_data.get("allScores", clan_data.get("scores", 0)) or 0)
        month_scores = int(clan_data.get("monthScores", 0) or 0)
        owner = clan_data.get("owner", {}) if isinstance(clan_data.get("owner"), dict) else {}
        owner_name = owner.get("name") or "Unknown"
        owner_short = owner.get("shortId") or "-"
        desc = str(clan_data.get("description") or "No description")
        if len(desc) > 220:
            desc = desc[:217] + "..."

        embed = discord.Embed(
            title=f"🏰 {clan_data.get('name', CLAN_NAME)}",
            description=desc,
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="👥 Members", value=f"{len(members)}", inline=True)
        embed.add_field(name="⭐ All Scores", value=f"{all_scores:,}", inline=True)
        embed.add_field(name="📅 Month Scores", value=f"{month_scores:,}", inline=True)
        embed.add_field(name="👑 Owner", value=f"AIMTOME", inline=False)
        embed.set_footer(text="Source: api.kirka.io")
        await interaction.followup.send(embed=embed)
    except Exception as exc:
        await interaction.followup.send(f"Failed clan_info: {exc}")
@bot.tree.command(name="delete_snaps", description="Delete Monday and Sunday snapshots")
async def delete_snaps(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message(
            "Admin only command.",
            ephemeral=True
        )
        return

    deleted = []

    try:
        if MONDAY_SNAPSHOT_PATH.exists():
            MONDAY_SNAPSHOT_PATH.unlink()
            deleted.append("Monday")

        if SUNDAY_SNAPSHOT_PATH.exists():
            SUNDAY_SNAPSHOT_PATH.unlink()
            deleted.append("Sunday")

        if deleted:
            await interaction.response.send_message(
                f"Deleted snapshots: {', '.join(deleted)}"
            )
        else:
            await interaction.response.send_message(
                "No snapshot files found."
            )

    except Exception as exc:
        await interaction.response.send_message(
            f"Failed deleting snapshots: {exc}"
        )





def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")
    if not KIRKA_API_KEY:
        raise RuntimeError("Missing required environment variable: KIRKA_API_KEY")


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    bot.run(DISCORD_TOKEN)