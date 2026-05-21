import os
import logging
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv
from tabulate import tabulate

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("weekly-xp-bot")

WEEKLY_XP_REQUIREMENT = 30_000
KIRKA_API_BASE_URL = os.getenv("KIRKA_API_BASE_URL", "https://api2.kirka.io")
KIRKA_API_KEY = os.getenv("KIRKA_API_KEY", "")
KIRKA_CLAN_TAG = os.getenv("KIRKA_CLAN_TAG", "UsAsOne")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")


class KirkaClient:
    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        timeout = aiohttp.ClientTimeout(total=20)
        self.session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def get_clan_members(self, clan_tag: str) -> list[dict[str, Any]]:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        sanitized_tag = clan_tag.strip().strip("!")
        encoded_tag = quote(sanitized_tag, safe="")
        headers = {"Authorization": self.api_key}

        candidate_urls = [
            f"{self.base_url}/api/clan/{encoded_tag}",
            f"{self.base_url}/api/clans/{encoded_tag}",
            f"{self.base_url}/clan/{encoded_tag}",
            f"{self.base_url}/clans/{encoded_tag}",
        ]

        errors: list[str] = []
        for url in candidate_urls:
            async with self.session.get(url, headers=headers) as response:
                body = await response.text()
                if response.status == 404:
                    errors.append(f"{response.status} at {url}")
                    continue
                if response.status != 200:
                    raise RuntimeError(f"Kirka API error {response.status} at {url}: {body[:300]}")

                payload = await response.json(content_type=None)
                members = payload.get("members") if isinstance(payload, dict) else None
                if isinstance(members, list):
                    return members
                raise RuntimeError("Unexpected API response: missing 'members' list")

        raise RuntimeError(
            "No clan endpoint worked (404). Verifica KIRKA_API_BASE_URL y KIRKA_CLAN_TAG (sin !). "
            f"Intentos: {', '.join(errors)}"
        )


def build_weekly_table(members: list[dict[str, Any]]) -> str:
    rows: list[list[Any]] = []

    for member in members:
        username = member.get("name") or member.get("username") or "Unknown"
        weekly_xp = int(member.get("weeklyXP", 0) or 0)
        status = "OK" if weekly_xp >= WEEKLY_XP_REQUIREMENT else "FALTA"
        rows.append([username, weekly_xp, status])

    rows.sort(key=lambda row: row[1], reverse=True)

    total = len(rows)
    compliant = sum(1 for row in rows if row[2] == "OK")
    missing = total - compliant

    table = tabulate(rows, headers=["Jugador", "XP Semanal", "Estado"], tablefmt="github")
    summary = (
        f"Clan: {KIRKA_CLAN_TAG}\n"
        f"Requisito semanal: {WEEKLY_XP_REQUIREMENT:,} XP\n"
        f"Cumplen: {compliant}/{total} | No cumplen: {missing}\n"
        f"Actualizado (UTC): {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
    )

    return f"{summary}\n\n{table}"


class WeeklyXPBot(commands.Bot):
    def __init__(self, kirka_client: KirkaClient):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.kirka_client = kirka_client

    async def setup_hook(self) -> None:
        await self.kirka_client.start()
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def close(self) -> None:
        await self.kirka_client.close()
        await super().close()


kirka_client = KirkaClient(api_key=KIRKA_API_KEY, base_url=KIRKA_API_BASE_URL)
bot = WeeklyXPBot(kirka_client=kirka_client)


@bot.tree.command(name="weeklyxp", description="Muestra el progreso semanal de XP del clan")
async def weeklyxp(interaction: discord.Interaction) -> None:
    await interaction.response.defer(thinking=True)

    try:
        members = await bot.kirka_client.get_clan_members(KIRKA_CLAN_TAG)
        report = build_weekly_table(members)
    except Exception as exc:
        logger.exception("Error building weekly XP report")
        await interaction.followup.send(f"No se pudo obtener el reporte semanal: {exc}")
        return

    for chunk_start in range(0, len(report), 1800):
        chunk = report[chunk_start : chunk_start + 1800]
        if chunk_start == 0:
            await interaction.followup.send(f"```\n{chunk}\n```")
        else:
            await interaction.channel.send(f"```\n{chunk}\n```")


def validate_environment() -> None:
    required = {
        "DISCORD_TOKEN": DISCORD_TOKEN,
        "KIRKA_API_KEY": KIRKA_API_KEY,
        "KIRKA_CLAN_TAG": KIRKA_CLAN_TAG,
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


if __name__ == "__main__":
    validate_environment()
    bot.run(DISCORD_TOKEN)