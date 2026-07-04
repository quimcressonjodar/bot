import time
import platform
import discord
from discord import app_commands
from discord.ext import commands


# ---------------------------------------------------------------------------
# Interactive Tutorial – page definitions
# ---------------------------------------------------------------------------

def build_pages() -> list[discord.Embed]:
    """Return the ordered list of tutorial embeds."""

    pages: list[discord.Embed] = []

    # ── Page 1: Welcome ──────────────────────────────────────────────────
    e = discord.Embed(
        title="🎮 Welcome to the Economy!",
        description=(
            "This server has a **full economy system** — earn coins, gamble, "
            "raise pets, invest in the stock market and climb the leaderboard.\n\n"
            "Use the **buttons below** to go through the tutorial step by step. "
            "You can come back to any page any time with `!help`."
        ),
        color=0xF1C40F,
    )
    e.add_field(
        name="📖 What you'll learn",
        value=(
            "1️⃣ Getting your first coins\n"
            "2️⃣ Banking & sending money\n"
            "3️⃣ Work, crime & the WANTED system\n"
            "4️⃣ Casino games\n"
            "5️⃣ Bounty contracts\n"
            "6️⃣ Pets — buy, feed, breed\n"
            "7️⃣ Battles & adventures\n"
            "8️⃣ Shop & items\n"
            "9️⃣ Stock market\n"
            "🔟 Loans & debt\n"
            "⭐ Prestige system"
        ),
        inline=False,
    )
    e.set_footer(text="Page 1 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 2: Getting your first coins ────────────────────────────────
    e = discord.Embed(
        title="💰 Getting Your First Coins",
        description="Start here. Three free income sources refresh on a timer:",
        color=0x2ECC71,
    )
    e.add_field(
        name="📅 `!daily`",
        value="Claim **~1,000 🪙** once every 24 hours. Always do this first thing.",
        inline=False,
    )
    e.add_field(
        name="📆 `!weekly`",
        value="Claim **~25,000 🪙** once per week. Never miss it.",
        inline=False,
    )
    e.add_field(
        name="🎁 `!claim`",
        value=(
            "If you own special roles from the shop, you get an **hourly bonus** "
            "from each one. More roles = more passive income."
        ),
        inline=False,
    )
    e.add_field(
        name="📊 `!balance`",
        value="Check your wallet, bank, net worth and prestige level at any time.",
        inline=False,
    )
    e.add_field(
        name="💡 Tip",
        value="Keep coins in the **bank** — you can't be robbed there.",
        inline=False,
    )
    e.set_footer(text="Page 2 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 3: Banking & transfers ──────────────────────────────────────
    e = discord.Embed(
        title="🏦 Banking & Transfers",
        description="Manage your money safely and see how you stack up against others.",
        color=0x3498DB,
    )
    e.add_field(
        name="💳 `!deposit <amount>`",
        value='Move coins from your wallet to the bank. Use `all` to deposit everything.',
        inline=False,
    )
    e.add_field(
        name="💳 `!withdraw <amount>`",
        value="Take coins out of the bank when you need to spend.",
        inline=False,
    )
    e.add_field(
        name="💸 `!pay @user <amount>`",
        value="Send coins directly to another player's wallet.",
        inline=False,
    )
    e.add_field(
        name="🏆 `!leaderboard`",
        value="See the richest players ranked by total net worth (wallet + bank).",
        inline=False,
    )
    e.add_field(
        name="💡 Tip",
        value=(
            "Always `!deposit all` after a big win. "
            "If someone robs you, they can only take from your **wallet**."
        ),
        inline=False,
    )
    e.set_footer(text="Page 3 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 4: Work, crime & WANTED ────────────────────────────────────
    e = discord.Embed(
        title="💼 Work, Crime & the WANTED System",
        description="Earn coins the legal way — or take the risk.",
        color=0xE67E22,
    )
    e.add_field(
        name="🔨 `!work`",
        value=(
            "Work a random job and earn coins on a cooldown. "
            "Safe, consistent income. No risk."
        ),
        inline=False,
    )
    e.add_field(
        name="🕵️ `!crime`",
        value=(
            "Attempt a crime for **2,000–6,500 🪙**. "
            "If you fail you get fined and become **WANTED** 🚨."
        ),
        inline=False,
    )
    e.add_field(
        name="🔫 `!rob @user`",
        value=(
            "Steal coins from another player's wallet. "
            "If it fails, you pay a fine and go WANTED."
        ),
        inline=False,
    )
    e.add_field(
        name="🚔 `!catch @user`",
        value=(
            "If someone is WANTED, catch them for a **reward**. "
            "Bounty hunters can make serious money this way."
        ),
        inline=False,
    )
    e.add_field(
        name="⚠️ The WANTED system",
        value=(
            "Going WANTED means other players can catch you at any moment "
            "and take a reward from your wallet. Deposit fast!"
        ),
        inline=False,
    )
    e.set_footer(text="Page 4 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 5: Casino ───────────────────────────────────────────────────
    e = discord.Embed(
        title="🎰 Casino Games",
        description="Gamble your coins — high risk, high reward. Always bet responsibly.",
        color=0x9B59B6,
    )
    e.add_field(
        name="🃏 `!blackjack <bet>`",
        value=(
            "Classic blackjack vs the house. Get closer to 21 without busting. "
            "Win 2× your bet."
        ),
        inline=False,
    )
    e.add_field(
        name="🎡 `!roulette <bet> <choice>`",
        value=(
            "Bet on **red/black** (2×), **even/odd** (2×), a **specific number** (36×) "
            "or **1st/2nd/3rd 12** (3×). Higher risk = higher payout."
        ),
        inline=False,
    )
    e.add_field(
        name="🎲 `!dice <bet>`",
        value="Roll two dice against the house. Win or lose your bet.",
        inline=False,
    )
    e.add_field(
        name="🎁 `!claimdrop`",
        value=(
            "Admins can trigger global coin or item drops in any channel. "
            "Type `!claimdrop` fast to grab it before anyone else!"
        ),
        inline=False,
    )
    e.add_field(
        name="💡 Tip",
        value="Never gamble coins you can't afford to lose. The house always has an edge.",
        inline=False,
    )
    e.set_footer(text="Page 5 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 6: Bounties ─────────────────────────────────────────────────
    e = discord.Embed(
        title="🎯 Bounty Contracts",
        description=(
            "Bounties are **long-term challenges** that reward you for playing "
            "the economy naturally. Complete them to earn big bonuses."
        ),
        color=0xE74C3C,
    )
    e.add_field(
        name="📋 `!bounties`",
        value=(
            "View all active bounty contracts and your personal progress on each one. "
            "Examples:\n"
            "• **The Hard Worker** — work a certain number of times\n"
            "• **The Trader** — make profit selling stocks\n"
            "• **The Gambler** — win in the casino\n"
            "• **The Hunter** — catch WANTED players"
        ),
        inline=False,
    )
    e.add_field(
        name="⚙️ How it works",
        value=(
            "Progress is tracked automatically as you play. "
            "When you complete a contract you receive a coin reward. "
            "New contracts rotate in over time."
        ),
        inline=False,
    )
    e.add_field(
        name="💡 Tip",
        value=(
            "Check `!bounties` regularly — some contracts have a time limit "
            "and expire if you don't complete them in time."
        ),
        inline=False,
    )
    e.set_footer(text="Page 6 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 7: Pets ─────────────────────────────────────────────────────
    e = discord.Embed(
        title="🐾 Pets",
        description=(
            "Pets are companions that fight for you, go on adventures, "
            "and can be bred into stronger versions."
        ),
        color=0x1ABC9C,
    )
    e.add_field(
        name="🛒 `!shop`",
        value="Browse available pets and their stats (HP, Damage, Price).",
        inline=False,
    )
    e.add_field(
        name="🛍️ `!buy <pet name>`",
        value="Purchase a pet from the shop. Coins are taken from your wallet.",
        inline=False,
    )
    e.add_field(
        name="📋 `!pets`",
        value="View all your pets — their HP, damage, hunger level and current status.",
        inline=False,
    )
    e.add_field(
        name="🍖 `!feed <pet name> <food>`",
        value=(
            "Feed your pet to restore hunger. Food items come from adventures and drops. "
            "A hungry pet performs worse in battles."
        ),
        inline=False,
    )
    e.add_field(
        name="🧬 `!breed <pet1> <pet2>`",
        value=(
            "Combine two pets to produce a stronger offspring. "
            "Costs 25% of their combined value. "
            "The offspring inherits stats from both parents."
        ),
        inline=False,
    )
    e.add_field(
        name="💰 `!sell_pet <pet name>`",
        value="Sell a pet for 50% of its original shop price.",
        inline=False,
    )
    e.set_footer(text="Page 7 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 8: Battles & Adventures ────────────────────────────────────
    e = discord.Embed(
        title="⚔️ Battles & Adventures",
        description="Put your pets to work — fight other players or explore the world.",
        color=0xE74C3C,
    )
    e.add_field(
        name="⚔️ `!battle @user`",
        value=(
            "Challenge another player's pet to a duel. "
            "Your strongest pet fights automatically. "
            "The winner earns coins; the loser's pet loses HP. "
            "Dead pets can't fight — keep them fed!"
        ),
        inline=False,
    )
    e.add_field(
        name="🗺️ `!adventures <pet name>`",
        value=(
            "Send a pet on an adventure. While away it can find:\n"
            "• 🪙 Coins\n"
            "• 🍖 Food items\n"
            "• 🎁 Rare loot\n\n"
            "Adventures take time — collect the reward when it returns."
        ),
        inline=False,
    )
    e.add_field(
        name="💡 Tips",
        value=(
            "• A hungry pet has lower stats in battle — always feed before fighting.\n"
            "• You can have multiple pets: one on adventure, one battling.\n"
            "• Bred pets are stronger — invest in breeding for competitive battles."
        ),
        inline=False,
    )
    e.set_footer(text="Page 8 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 9: Shop & Items ─────────────────────────────────────────────
    e = discord.Embed(
        title="🛍️ Shop & Items",
        description="Spend your coins on roles that generate passive income and useful items.",
        color=0xF39C12,
    )
    e.add_field(
        name="🏪 `!shop`",
        value=(
            "Browse everything for sale:\n"
            "• **Roles** — grant hourly coin income via `!claim`\n"
            "• **Pets** — companions for battles and adventures\n"
            "• **Food** — feed items to keep pets healthy"
        ),
        inline=False,
    )
    e.add_field(
        name="🎒 `!inventory`",
        value="View all items you own — food, loot drops, and their total resale value.",
        inline=False,
    )
    e.add_field(
        name="💸 `!sell <item>`",
        value="Sell items from your inventory for coins.",
        inline=False,
    )
    e.add_field(
        name="🎁 `!claimdrop`",
        value=(
            "When an admin triggers a global drop, everyone races to type `!claimdrop`. "
            "First to claim gets the coins or item."
        ),
        inline=False,
    )
    e.add_field(
        name="💡 Tip",
        value=(
            "Roles are the best long-term investment — every hour you earn "
            "passive coins just by typing `!claim`. Stack as many as you can afford."
        ),
        inline=False,
    )
    e.set_footer(text="Page 9 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 10: Stock Market ────────────────────────────────────────────
    e = discord.Embed(
        title="📈 Stock Market",
        description=(
            "The stock market lets you **invest** your coins and earn returns "
            "through price changes and daily dividends. Prices update every few minutes "
            "and can be affected by market news events."
        ),
        color=0x2ECC71,
    )
    e.add_field(
        name="📊 `!stocks` / `!stocks <SYMBOL>`",
        value=(
            "View all listed companies and their prices, "
            "or check a specific stock's chart and current price."
        ),
        inline=False,
    )
    e.add_field(
        name="🛒 `!sbuy <SYMBOL> <amount>`",
        value="Buy shares. Use `all` or `max` to spend your entire wallet.",
        inline=False,
    )
    e.add_field(
        name="💰 `!ssell <SYMBOL> <amount>`",
        value="Sell shares. Use `all` to sell your entire position.",
        inline=False,
    )
    e.add_field(
        name="💼 `!portfolio`",
        value="View all your holdings, current value, and total profit/loss.",
        inline=False,
    )
    e.add_field(
        name="🔔 Price Alerts",
        value=(
            "`!alert <SYMBOL> <price>` — get a DM when a stock hits your target.\n"
            "`!myalerts` — see your active alerts.\n"
            "`!cancelalert <id>` — remove an alert."
        ),
        inline=False,
    )
    e.add_field(
        name="💡 Dividends",
        value=(
            "Every 24 hours you automatically receive dividends on shares you hold. "
            "The rate (0.05%–2%) depends on how well each company performed that day."
        ),
        inline=False,
    )
    e.set_footer(text="Page 10 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 11: Loans & Debt ────────────────────────────────────────────
    e = discord.Embed(
        title="💳 Loans & Debt",
        description=(
            "Need coins fast? The bot offers loans — but interest accrues "
            "over time, so pay them back quickly."
        ),
        color=0xE74C3C,
    )
    e.add_field(
        name="🏦 `!loan <amount>`",
        value=(
            "Take out a loan. The coins go straight to your wallet. "
            "Interest is added automatically over time."
        ),
        inline=False,
    )
    e.add_field(
        name="💸 `!repay <amount>`",
        value="Pay back part or all of your loan. Reduces your debt and stops interest on that amount.",
        inline=False,
    )
    e.add_field(
        name="📋 `!debt`",
        value="Check your current outstanding debt and how much interest has built up.",
        inline=False,
    )
    e.add_field(
        name="⚠️ Warning",
        value=(
            "Debt compounds over time. If you take a loan to gamble and lose, "
            "you'll owe more than you borrowed. "
            "Only take loans if you have a clear plan to repay."
        ),
        inline=False,
    )
    e.set_footer(text="Page 11 / 12 • Use the buttons to navigate")
    pages.append(e)

    # ── Page 12: Prestige ────────────────────────────────────────────────
    e = discord.Embed(
        title="⭐ Prestige System",
        description=(
            "Prestige is a rank based on your **total net worth** (wallet + bank). "
            "The richer you are, the higher your prestige — and the better your perks."
        ),
        color=0xF1C40F,
    )
    e.add_field(
        name="📊 How prestige works",
        value=(
            "Your prestige level is calculated automatically from your net worth. "
            "It is visible in `!balance` and `!leaderboard`."
        ),
        inline=False,
    )
    e.add_field(
        name="⚡ Prestige perks",
        value=(
            "Higher prestige levels reduce the **trading fee** on stocks. "
            "At max prestige, stock fees drop by up to **90%** — "
            "making the stock market far more profitable for top players."
        ),
        inline=False,
    )
    e.add_field(
        name="🏆 How to climb",
        value=(
            "1. Never miss `!daily` and `!weekly`\n"
            "2. Buy income roles and `!claim` every hour\n"
            "3. Invest in stocks and collect dividends\n"
            "4. Complete bounty contracts\n"
            "5. Win pet battles and adventures\n"
            "6. Gamble carefully — or not at all"
        ),
        inline=False,
    )
    e.add_field(
        name="📋 Full command reference",
        value=(
            "Type `!help` at any time to reopen this tutorial. "
            "All commands also work as slash commands (e.g. `/balance`)."
        ),
        inline=False,
    )
    e.set_footer(text="Page 12 / 12 • You've reached the end — good luck! 🍀")
    pages.append(e)

    return pages


# ---------------------------------------------------------------------------
# Tutorial View – navigation buttons
# ---------------------------------------------------------------------------

class TutorialView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], author_id: int):
        super().__init__(timeout=180)
        self.pages = pages
        self.author_id = author_id
        self.current = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current == 0
        self.next_btn.disabled = self.current == len(self.pages) - 1
        self.counter_btn.label = f"{self.current + 1} / {len(self.pages)}"

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "❌ This tutorial was opened by someone else. Use `!help` to open your own.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, disabled=True)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.current -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    @discord.ui.button(label="1 / 12", style=discord.ButtonStyle.primary, disabled=True)
    async def counter_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass  # display-only

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.current += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current], view=self)

    async def on_timeout(self):
        # Disable all buttons when the view expires
        for item in self.children:
            item.disabled = True


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class UtilityCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.start_time = time.time()

    @commands.hybrid_command(name="botstats", description="Show bot performance stats: ping, uptime and more")
    async def botstats(self, ctx: commands.Context):
        before = time.perf_counter()
        msg = await ctx.send("📡 Measuring latency...")
        after = time.perf_counter()
        rest_ping = round((after - before) * 1000)
        ws_ping = round(self.bot.latency * 1000)

        uptime_seconds = int(time.time() - self.start_time)
        days, rem = divmod(uptime_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"

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

    @commands.hybrid_command(name="help", description="Interactive economy tutorial — learn how to play from scratch")
    async def help_command(self, ctx: commands.Context):
        pages = build_pages()
        view = TutorialView(pages, author_id=ctx.author.id)
        await ctx.send(embed=pages[0], view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(UtilityCog(bot))
