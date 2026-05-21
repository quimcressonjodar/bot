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
from tabulate import tabulate

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("weekly-xp-bot")

DEFAULT_WEEKLY_XP_REQUIREMENT = 30_000
WEEKLY_XP_REQUIREMENT = int(os.getenv("WEEKLY_XP_REQUIREMENT", str(DEFAULT_WEEKLY_XP_REQUIREMENT)))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
CLAN_NAME = os.getenv("KIRKA_CLAN_TAG", "UsAsOne!")
SMUDGY_CLAN_URL = os.getenv("SMUDGY_CLAN_URL", "https://www.smudgy.store/api/getclanname?name=")
SMUDGY_PROFILE_URL = os.getenv("SMUDGY_PROFILE_URL", "https://www.smudgy.store/api/getprofile?name=")
SMUDGY_PLAYER_COUNT_URL = os.getenv("SMUDGY_PLAYER_COUNT_URL", "https://www.smudgy.store/api/kirka/playerCount")
SMUDGY_PRICECALC_URL = os.getenv("SMUDGY_PRICECALC_URL", "https://www.smudgy.store/api/pricecalc?price=")
SNAPSHOT_PATH = Path(os.getenv("XP_SNAPSHOT_FILE", "xp_snapshots.json"))
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_RETRY_BASE_DELAY = float(os.getenv("HTTP_RETRY_BASE_DELAY", "0.8"))


class ClanClient:
    def __init__(self, clan_url_prefix: str):
        self.clan_url_prefix = clan_url_prefix
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS))

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def get_clan_data(self, clan_name: str) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        encoded_name = quote(clan_name.strip(), safe="")
        url = f"{self.clan_url_prefix}{encoded_name}"
        payload = await self._get_json_with_retry(url)

        if not isinstance(payload, dict) or not payload.get("success"):
            raise RuntimeError("Unexpected clan API response")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected clan API response: missing data")
        members = data.get("members")
        if not isinstance(members, list):
            raise RuntimeError("Unexpected clan API response: missing members")
        return data

    async def _get_json_with_retry(self, url: str) -> dict[str, Any]:
        return await self._request_json_with_retry("GET", url)

    async def _request_json_with_retry(self, method: str, url: str, json_payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        last_error: Exception | None = None
        for attempt in range(1, HTTP_MAX_RETRIES + 1):
            try:
                request_fn = self.session.get if method.upper() == "GET" else self.session.post
                async with request_fn(url, json=json_payload) as response:
                    body = await response.text()
                    if response.status == 429:
                        retry_after = float(response.headers.get("Retry-After", "0") or 0)
                        delay = retry_after if retry_after > 0 else HTTP_RETRY_BASE_DELAY * attempt
                        await asyncio.sleep(delay)
                        continue
                    if response.status >= 500:
                        raise RuntimeError(f"API temporary error {response.status}: {body[:200]}")
                    if response.status != 200:
                        raise RuntimeError(f"API error {response.status}: {body[:300]}")
                    return await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt < HTTP_MAX_RETRIES:
                    await asyncio.sleep(HTTP_RETRY_BASE_DELAY * attempt)
                else:
                    break

        raise RuntimeError(f"Failed request after {HTTP_MAX_RETRIES} attempts: {last_error}")




    async def get_price_check(self, skins_csv: str) -> dict[str, Any]:
        encoded = quote(skins_csv.strip(), safe=",")
        return await self._get_json_with_retry(f"{SMUDGY_PRICECALC_URL}{encoded}")

def load_snapshots() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        return {}
    with SNAPSHOT_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_snapshots(data: dict[str, Any]) -> None:
    with SNAPSHOT_PATH.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)




def is_admin(interaction: discord.Interaction) -> bool:
    return bool(interaction.user.guild_permissions.administrator)


def extract_member_map(clan_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in clan_data.get("members", []):
        user = item.get("user") or {}
        user_id = str(user.get("id", "")).strip()
        if not user_id:
            continue
        result[user_id] = {
            "id": user_id,
            "name": str(user.get("name") or "Unknown"),
            "shortId": str(user.get("shortId") or "-"),
            "role": str(item.get("role") or "UNKNOWN"),
            "allScores": int(item.get("allScores", 0) or 0),
            "monthScores": int(item.get("monthScores", 0) or 0),
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

    rows.sort(key=lambda row: (row[4] not in {"OK", "MISSING", "REVIEW"}, -row[3] if isinstance(row[3], int) else 0, row[0]))
    return rows


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


clan_client = ClanClient(clan_url_prefix=SMUDGY_CLAN_URL)
bot = WeeklyXPBot(clan_client=clan_client)




@bot.tree.command(name="set_requirement", description="Set weekly XP requirement (admin only)")
@app_commands.describe(xp="New weekly XP requirement")
async def set_requirement(interaction: discord.Interaction, xp: int) -> None:
    global WEEKLY_XP_REQUIREMENT
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return
    if xp <= 0:
        await interaction.response.send_message("XP requirement must be greater than 0.", ephemeral=True)
        return
    WEEKLY_XP_REQUIREMENT = xp
    await interaction.response.send_message(f"Weekly requirement updated to {WEEKLY_XP_REQUIREMENT:,} XP.")


@bot.tree.command(name="set_clan", description="Set clan name for tracking (admin only)")
@app_commands.describe(name="Clan name exactly as shown")
async def set_clan(interaction: discord.Interaction, name: str) -> None:
    global CLAN_NAME
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return
    CLAN_NAME = name.strip()
    await interaction.response.send_message(f"Clan name updated to: {CLAN_NAME}")


@bot.tree.command(name="clan_info", description="Show current clan configuration and live clan info")
async def clan_info(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        members = clan_data.get("members", [])

        description = str(clan_data.get("description") or "No description.")
        if len(description) > 300:
            description = description[:297] + "..."

        embed = discord.Embed(
            title=f"{clan_data.get('name', CLAN_NAME)} • Clan Info",
            description=description,
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Members", value=str(len(members)), inline=True)
        embed.add_field(name="All Scores", value=f"{int(clan_data.get('allScores', 0)):,}", inline=True)
        embed.add_field(name="Month Scores", value=f"{int(clan_data.get('monthScores', 0)):,}", inline=True)
        embed.add_field(name="Weekly Requirement", value=f"{WEEKLY_XP_REQUIREMENT:,} XP", inline=True)

        discord_link = str(clan_data.get("discordLink") or "-")
        if discord_link != "-":
            embed.add_field(name="Discord", value=f"[Join server]({discord_link})", inline=False)
        else:
            embed.add_field(name="Discord", value="-", inline=False)

        embed.set_footer(text="Data source: smudgy clan endpoint")
        await interaction.followup.send(embed=embed)
    except Exception as exc:
        await interaction.followup.send(f"Failed to fetch clan info: {exc}")


@bot.tree.command(name="register_monday", description="Save Monday baseline snapshot")
async def register_monday(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        members = extract_member_map(clan_data)
        snapshots = load_snapshots()
        snapshots["monday"] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": members,
        }
        save_snapshots(snapshots)
    except Exception as exc:
        await interaction.followup.send(f"Failed to save Monday snapshot: {exc}")
        return

    await interaction.followup.send(
        f"Monday snapshot saved for {snapshots['monday']['clan_name']} with {len(members)} members."
    )


@bot.tree.command(name="register_sunday", description="Save Sunday snapshot and compute weekly xp table")
async def register_sunday(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        sunday_members = extract_member_map(clan_data)
        snapshots = load_snapshots()
        monday_data = snapshots.get("monday")
        if not monday_data or not isinstance(monday_data.get("members"), dict):
            await interaction.followup.send("No Monday snapshot found. Run /register_monday first.")
            return

        snapshots["sunday"] = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": sunday_members,
        }
        save_snapshots(snapshots)

        monday_members = monday_data["members"]
        rows = build_weekly_rows(monday_members, sunday_members)

        compliant = sum(1 for row in rows if row[4] == "OK")
        missing = sum(1 for row in rows if row[4] == "MISSING")
        joined = sum(1 for row in rows if row[4] == "JOINED")
        left = sum(1 for row in rows if row[4] == "LEFT")
        review = sum(1 for row in rows if row[4] == "REVIEW")

        table = tabulate(rows, headers=["Player", "Short ID", "Role", "Weekly XP", "Status"], tablefmt="github")
        header = (
            f"Clan: {snapshots['sunday']['clan_name']}\n"
            f"Requirement: {WEEKLY_XP_REQUIREMENT:,} XP\n"
            f"OK: {compliant} | Missing: {missing} | Joined: {joined} | Left: {left} | Review: {review}\n"
            f"Monday: {monday_data['timestamp_utc']}\n"
            f"Sunday: {snapshots['sunday']['timestamp_utc']}"
        )
        report = f"{header}\n\n{table}"
    except Exception as exc:
        logger.exception("Failed to compute weekly table")
        await interaction.followup.send(f"Failed to compute weekly table: {exc}")
        return

    chunks = [report[i:i + 1800] for i in range(0, len(report), 1800)]
    for i, chunk in enumerate(chunks):
        if i == 0:
            await interaction.followup.send(f"```\n{chunk}\n```")
        else:
            await interaction.channel.send(f"```\n{chunk}\n```")


@bot.tree.command(name="weekly_table", description="Generate weekly table from saved Monday/Sunday snapshots")
async def weekly_table(interaction: discord.Interaction) -> None:
    if not is_admin(interaction):
        await interaction.response.send_message("Admin only command.", ephemeral=True)
        return
    await interaction.response.defer(thinking=True)
    try:
        snapshots = load_snapshots()
        monday_data = snapshots.get("monday")
        sunday_data = snapshots.get("sunday")
        if not monday_data or not sunday_data:
            await interaction.followup.send("Need both snapshots. Run /register_monday and /register_sunday first.")
            return

        rows = build_weekly_rows(monday_data["members"], sunday_data["members"])
        table = tabulate(rows, headers=["Player", "Short ID", "Role", "Weekly XP", "Status"], tablefmt="github")
        report = f"Clan: {sunday_data['clan_name']}\n\n{table}"
    except Exception as exc:
        await interaction.followup.send(f"Failed to generate table: {exc}")
        return

    chunks = [report[i:i + 1800] for i in range(0, len(report), 1800)]
    for i, chunk in enumerate(chunks):
        if i == 0:
            await interaction.followup.send(f"```\n{chunk}\n```")
        else:
            await interaction.channel.send(f"```\n{chunk}\n```")




@bot.tree.command(name="joined_left", description="Show players who joined or left between Monday and Sunday snapshots")
async def joined_left(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)
    try:
        snapshots = load_snapshots()
        monday_data = snapshots.get("monday")
        sunday_data = snapshots.get("sunday")
        if not monday_data or not sunday_data:
            await interaction.followup.send("Need both snapshots. Run /register_monday and /register_sunday first.")
            return

        rows = build_weekly_rows(monday_data["members"], sunday_data["members"])
        filtered = [r for r in rows if r[4] in {"JOINED", "LEFT"}]
        if not filtered:
            await interaction.followup.send("No joined/left changes detected between Monday and Sunday snapshots.")
            return

        table = tabulate(filtered, headers=["Player", "Short ID", "Role", "Weekly XP", "Status"], tablefmt="github")
        report = (
            f"Clan: {sunday_data['clan_name']}\n"
            f"Monday: {monday_data['timestamp_utc']}\n"
            f"Sunday: {sunday_data['timestamp_utc']}\n\n"
            f"{table}"
        )
    except Exception as exc:
        await interaction.followup.send(f"Failed to generate joined/left report: {exc}")
        return

    for i in range(0, len(report), 1800):
        chunk = report[i:i + 1800]
        if i == 0:
            await interaction.followup.send(f"```\n{chunk}\n```")
        else:
            await interaction.channel.send(f"```\n{chunk}\n```")







@bot.tree.command(name="price_check", description="Check prices for one or multiple skins")
@app_commands.describe(items="Comma-separated skins, example: Shroud, Goblin, Legend")
async def price_check(interaction: discord.Interaction, items: str) -> None:
    await interaction.response.defer(thinking=True)
    try:
        payload = await bot.clan_client.get_price_check(items)
        data = payload.get("breakdown") if isinstance(payload, dict) else None
        total_value = payload.get("value") if isinstance(payload, dict) else None

        embed = discord.Embed(
            title="Price Check",
            description=f"Items: {items}",
            color=discord.Color.purple(),
            timestamp=datetime.now(timezone.utc),
        )
        if total_value is not None:
            embed.add_field(name="Total Value", value=f"{int(total_value):,}", inline=False)

        if isinstance(data, dict) and data:
            rows = [[name, f"{int(value):,}"] for name, value in data.items()]
            rows.sort(key=lambda r: int(r[1].replace(',', '')), reverse=True)
            table = tabulate(rows, headers=["Item", "Price"], tablefmt="github")
            text = f"```\n{table}\n```"
            if len(text) <= 4000:
                embed.add_field(name="Breakdown", value=text, inline=False)
                await interaction.followup.send(embed=embed)
            else:
                await interaction.followup.send(embed=embed)
                for i in range(0, len(table), 1800):
                    chunk = table[i:i+1800]
                    await interaction.channel.send(f"```\n{chunk}\n```")
        else:
            raw_json = json.dumps(payload, ensure_ascii=False, indent=2)
            embed.add_field(name="Raw", value=f"```json\n{raw_json[:3500]}\n```", inline=False)
            await interaction.followup.send(embed=embed)
    except Exception as exc:
        await interaction.followup.send(f"Failed to fetch price data: {exc}")


def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")


if __name__ == "__main__":
    validate_environment()
    bot.run(DISCORD_TOKEN)
