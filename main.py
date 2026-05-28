import asyncio
import logging

import discord
from discord.ext import commands
from flask import Flask
from threading import Thread

import config
from config import DISCORD_TOKEN, KIRKA_API_KEY, KIRKA_API_BASE
from utils.kirka_api import ClanClient

logger = logging.getLogger("weekly-xp-bot")

app = Flask("")


@app.route("/")
def home():
    return "Bot activo"


def _run_flask():
    import os
    port = int(os.getenv("PORT", 10000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )


def keep_alive():
    t = Thread(target=_run_flask)
    t.daemon = True
    t.start()


COGS = [
    "cogs.admin",
    "cogs.economy",
    "cogs.pets",
    "cogs.games",
    "cogs.kirka",
    "cogs.utility",
    "cogs.events",
]


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
            help_command=None,
        )
        self.clan_client = clan_client

    async def setup_hook(self) -> None:
        await self.clan_client.start()
        for cog in COGS:
            await self.load_extension(cog)
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        logger.info(f"✅ Bot connected as {self.user}!")
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Game(name="Kirka.io 🏆"),
            async def on_ready(self):
            print(f"READY: {self.user} | {id(self)}")
        )

    async def close(self) -> None:
        await self.clan_client.close()
        await super().close()


def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")
    if not KIRKA_API_KEY:
        raise RuntimeError("Missing required environment variable: KIRKA_API_KEY")


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    clan_client = ClanClient(api_base=KIRKA_API_BASE, api_key=KIRKA_API_KEY)
    bot = WeeklyXPBot(clan_client=clan_client)
    bot.run(DISCORD_TOKEN)
