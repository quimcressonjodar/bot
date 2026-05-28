import random
import asyncio
import time

import discord
from discord.ext import commands, tasks
from datetime import timedelta

import state
from config import WELCOME_CHANNEL_ID, ADVENTURE_LOOT
from database import eco_col


GLOBAL_DROP_CHANNEL_ID = 1206197908399980575
GLOBAL_DROP_COIN_REWARDS = [50000, 75000, 100000, 125000, 150000, 200000]


class EventsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spawn_global_drop.start()
        self._recent_member_events = {}

    def cog_unload(self):
        self.spawn_global_drop.cancel()

    def _should_process_member_event(self, event_name: str, member_id: int, cooldown: float = 5.0) -> bool:
        key = (event_name, member_id)
        now = time.monotonic()
        last = self._recent_member_events.get(key)
        if last and now - last < cooldown:
            return False
        self._recent_member_events[key] = now
        return True

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot or not self._should_process_member_event("join", member.id):
            return
        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
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
            color=0x2B2D31,
        )
        embed.set_image(url="https://i.ibb.co/d4r7Z6f8/248-AB2-AF-21-F0-4384-A53-D-404328353301.png")
        await channel.send(content=f"Welcome {member.mention}!", embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot or not self._should_process_member_event("leave", member.id):
            return

        channel = self.bot.get_channel(WELCOME_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            title="Goodbye! 👋",
            description=f"**{member.name}** has left the server. We will miss you!",
            color=0xFF2A2A,
        )
        await channel.send(embed=embed)

    @tasks.loop(hours=5)
    async def spawn_global_drop(self):
        channel = self.bot.get_channel(GLOBAL_DROP_CHANNEL_ID)

        drop_type = random.choice(["coins", "coins", "coins", "item", "item"])

        if drop_type == "coins":
            reward = random.choice(GLOBAL_DROP_COIN_REWARDS)
            state.active_global_drop = {"type": "coins", "reward": reward}

            embed = discord.Embed(
                title="🌠 GLOBAL DROP",
                description=(
                    "💸 A MASSIVE treasure drop appeared!\nFirst person to claim it wins!\n"
                    "Use `!claimdrop` first!"
                ),
                color=0xF1C40F,
            )
            embed.add_field(name="💰 Coin Reward", value=f"🪙 {reward:,}")
        else:
            rarity_roll = random.randint(1, 100)
            if rarity_roll <= 35:
                rarity = "common"
            elif rarity_roll <= 65:
                rarity = "rare"
            elif rarity_roll <= 92:
                rarity = "epic"
            else:
                rarity = "legendary"

            item_name, item_value = random.choice(ADVENTURE_LOOT[rarity])

            if rarity == "legendary" and channel:
                await channel.send("🌌 A LEGENDARY item has appeared!!!")

            state.active_global_drop = {
                "type": "item",
                "item": {"name": item_name, "value": item_value, "rarity": rarity},
            }

            rarity_colors = {
                "common": 0x95A5A6, "rare": 0x3498DB, "epic": 0x9B59B6, "legendary": 0xF1C40F,
            }
            embed = discord.Embed(
                title="🌠 GLOBAL ITEM DROP",
                description="A mysterious item appeared from the skies!\n\nUse `!claimdrop` first!",
                color=rarity_colors[rarity],
            )
            embed.add_field(name="🎁 Item", value=item_name)
            embed.add_field(name="✨ Rarity", value=rarity.capitalize())

        if channel:
            await channel.send(embed=embed)

    @spawn_global_drop.before_loop
    async def before_spawn_global_drop(self):
        await self.bot.wait_until_ready()
        await asyncio.sleep(300 * 60)


async def setup(bot: commands.Bot):
    await bot.add_cog(EventsCog(bot))
