import time
import platform
import discord
from discord import app_commands
from discord.ext import commands


class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @commands.hybrid_command(name="botstats", description="Show bot performance stats: ping, uptime and more")
    async def botstats(self, ctx: commands.Context):
        # Measure REST API latency
        before = time.perf_counter()
        msg = await ctx.send("📡 Measuring latency...")
        after = time.perf_counter()
        rest_ping = round((after - before) * 1000)
        ws_ping = round(self.bot.latency * 1000)

        # Uptime
        uptime_seconds = int(time.time() - self.start_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

        # Counts
        total_members = sum(g.member_count or 0 for g in self.bot.guilds)
        total_commands = len([c for c in self.bot.commands if not c.hidden])

        def ping_emoji(ms):
            if ms < 80:
                return "🟢"
            elif ms < 200:
                return "🟡"
            else:
                return "🔴"

        embed = discord.Embed(title="🤖 Bot Stats", color=0x2B2D31)
        embed.add_field(
            name="📡 Latency",
            value=(
                f"{ping_emoji(ws_ping)} **WebSocket:** `{ws_ping} ms`\n"
                f"{ping_emoji(rest_ping)} **REST API:** `{rest_ping} ms`"
            ),
            inline=False,
        )
        embed.add_field(name="⏱️ Uptime", value=f"`{uptime_str}`", inline=True)
        embed.add_field(name="🏰 Servers", value=f"`{len(self.bot.guilds)}`", inline=True)
        embed.add_field(name="👥 Members", value=f"`{total_members:,}`", inline=True)
        embed.add_field(name="⚙️ Commands", value=f"`{total_commands}`", inline=True)
        embed.add_field(name="🐍 Python", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="📦 discord.py", value=f"`{discord.__version__}`", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await msg.edit(content=None, embed=embed)

    @commands.hybrid_command(name="help", description="Show all available commands")
    async def help_command(self, ctx: commands.Context):
        embed = discord.Embed(
            title="🛡️ Moderation & Economy Bot | Command List",
            description="Complete list of all bot commands.",
            color=0x2B2D31,
        )

        public_cmds = (
            "**`/botstats`** - Bot ping, uptime & stats.\n"
            "**`/8ball`** - Ask the magic 8ball.\n"
            "**`/help`** - Show all commands."
        )
        embed.add_field(name="🌍 Public Commands", value=public_cmds, inline=False)

        eco_cmds = (
            "**`/balance`** - View your balance.\n"
            "**`/deposit`** - Deposit money.\n"
            "**`/withdraw`** - Withdraw money.\n"
            "**`/daily`** - Claim daily reward.\n"
            "**`/weekly`** - Claim weekly reward.\n"
            "**`/claim`** - Claim role rewards.\n"
            "**`/pay`** - Send coins to users.\n"
            "**`/leaderboard`** - Richest players leaderboard.\n"
            "**`/work`** - Work for coins.\n"
            "**`/crime`** - Risk stealing coins.\n"
            "**`/rob`** - Rob another player.\n"
            "**`/blackjack`** - Play blackjack.\n"
            "**`/roulette`** - Play roulette.\n"
            "**`/claimdrop`** - Claim global drops.\n"
            "**`/loan`** - Request a loan.\n"
            "**`/repay`** - Repay your loan.\n"
            "**`/debt`** - Check your debt status."
        )
        embed.add_field(name="💰 Economy Commands", value=eco_cmds, inline=False)

        pet_cmds = (
            "**`/shop`** - View pet shop.\n"
            "**`/buy [pet]`** - Buy a pet.\n"
            "**`/pets`** - View your pets.\n"
            "**`/feed`** - Feed your pets.\n"
            "**`/battle`** - Battle another player.\n"
            "**`/adventures`** - Send pets on adventures.\n"
            "**`/sell_pet`** - Sell your pets.\n"
            "**`/inventory`** - View your loot inventory.\n"
            "**`/sell`** - Sell inventory items."
        )
        embed.add_field(name="🐾 Pet Commands", value=pet_cmds, inline=False)

        admin_cmds = (
            "**`/ban`** - Ban users.\n"
            "**`/unban`** - Unban users.\n"
            "**`/kick`** - Kick users.\n"
            "**`/timeout`** - Timeout users.\n"
            "**`/untimeout`** - Remove timeout.\n"
            "**`/warn`** - Warn users.\n"
            "**`/warns`** - View warnings.\n"
            "**`/delwarn`** - Delete warning.\n"
            "**`/clearwarns`** - Clear all warnings.\n"
            "**`/purge`** - Delete messages.\n"
            "**`/say`** - Make bot say text.\n"
            "**`/sayembed`** - Send custom embeds.\n"
            "**`/add`** - Add coins to users.\n"
            "**`/set_xp`** - Set weekly XP requirement.\n"
            "**`/register monday`** - 🔥 FIRST (START OF WEEK): Run on Mondays.\n"
            "**`/register sunday`** - ✅ SECOND (END OF WEEK): Run after monday snapshot.\n"
            "**`/weekly_lb`** - Weekly XP leaderboard.\n"
            "**`/delete_snaps`** - Delete snapshot data.\n"
            "**`/reset_economy`** - Reset all economy data."
        )
        embed.add_field(name="🛡️ Admin Commands", value=admin_cmds, inline=False)

        embed.set_footer(text="Found a bug? Contact clxzon_")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
