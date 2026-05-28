import random
import time
from datetime import datetime, timezone, timedelta

import discord
from discord import app_commands
from discord.ext import commands

import state
from config import ROLE_SHOP
from database import eco_col
from utils.economy import (
    get_user_data,
    get_wallet,
    get_bank,
    update_wallet,
    update_bank,
    parse_economy_amount,
)
from views.economy_views import SellView


class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="balance", aliases=["bal"], description="Check your economy profile")
    async def balance(self, ctx: commands.Context, member: discord.Member = None):
        target = member or ctx.author
        wallet = get_wallet(str(target.id))
        bank = get_bank(str(target.id))
        total = wallet + bank
        embed = discord.Embed(title=f"💳 {target.display_name}'s Economy", color=0x2B2D31)
        embed.add_field(name="💵 Wallet", value=f"🪙 {wallet:,}", inline=True)
        embed.add_field(name="🏦 Bank", value=f"🪙 {bank:,}", inline=True)
        embed.add_field(name="📈 Total Net Worth", value=f"🪙 {total:,}", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="deposit", aliases=["dep"], description="Deposit coins into your bank")
    @app_commands.describe(amount="The amount to deposit ('all', 'half', or a number)")
    async def deposit(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        parsed_amount = parse_economy_amount(amount, wallet)
        if parsed_amount <= 0:
            return await ctx.send("❌ Invalid amount. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
        if parsed_amount > wallet:
            return await ctx.send(f"❌ You don't have enough coins. You only have 🪙 {wallet:,}.", ephemeral=True)
        update_wallet(user_id, -parsed_amount)
        update_bank(user_id, parsed_amount)
        embed = discord.Embed(
            title="🏦 Deposit Successful",
            description=f"You deposited 🪙 {parsed_amount:,} coins into your bank.",
            color=0x00FF00,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="withdraw", aliases=["with"], description="Withdraw coins from your bank")
    @app_commands.describe(amount="The amount to withdraw ('all', 'half', or a number)")
    async def withdraw(self, ctx: commands.Context, amount: str):
        user_id = str(ctx.author.id)
        bank = get_bank(user_id)
        parsed_amount = parse_economy_amount(amount, bank)
        if parsed_amount <= 0:
            return await ctx.send("❌ Invalid amount. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
        if parsed_amount > bank:
            return await ctx.send(f"❌ You don't have enough bank coins. You only have 🪙 {bank:,} in the bank.", ephemeral=True)
        update_bank(user_id, -parsed_amount)
        update_wallet(user_id, parsed_amount)
        embed = discord.Embed(
            title="💸 Withdrawal Successful",
            description=f"You withdrew 🪙 {parsed_amount:,} coins from your bank.",
            color=0x3498DB,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="daily", description="Claim your daily free coins")
    async def daily(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        last_daily = user_data.get("last_daily")
        already_claimed = False

        if isinstance(last_daily, str):
            already_claimed = last_daily == today_str
        elif isinstance(last_daily, (int, float)):
            last_date = datetime.fromtimestamp(last_daily, tz=timezone.utc)
            already_claimed = last_date.strftime("%Y-%m-%d") == today_str
        elif hasattr(last_daily, "strftime"):
            already_claimed = last_daily.strftime("%Y-%m-%d") == today_str

        if already_claimed:
            next_midnight = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=1)
            return await ctx.send(
                f"❌ You already claimed your daily! Wait until <t:{int(next_midnight.timestamp())}:R>.",
                ephemeral=True,
            )

        amount = 1000
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": amount}, "$set": {"last_daily": today_str}},
            upsert=True,
        )
        await ctx.send(f"📆 You claimed your daily reward of 🪙 {amount:,} coins!")

    @commands.hybrid_command(name="weekly", description="Claim your massive weekly reward")
    async def weekly(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        week_str = f"{now.year}-W{now.isocalendar()[1]}"
        last_weekly = user_data.get("last_weekly")
        already_claimed = False

        if isinstance(last_weekly, str):
            already_claimed = last_weekly == week_str
        elif isinstance(last_weekly, (int, float)):
            last_date = datetime.fromtimestamp(last_weekly, tz=timezone.utc)
            saved_week = f"{last_date.year}-W{last_date.isocalendar()[1]}"
            already_claimed = saved_week == week_str
        elif hasattr(last_weekly, "isocalendar"):
            saved_week = f"{last_weekly.year}-W{last_weekly.isocalendar()[1]}"
            already_claimed = saved_week == week_str

        if already_claimed:
            days_until_next_monday = 7 - now.weekday()
            next_monday = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) + timedelta(days=days_until_next_monday)
            return await ctx.send(
                f"❌ You already claimed your weekly! Wait until <t:{int(next_monday.timestamp())}:R>.",
                ephemeral=True,
            )

        amount = 25000
        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": amount}, "$set": {"last_weekly": week_str}},
            upsert=True,
        )
        await ctx.send(f"✨ You claimed your weekly reward of 🪙 {amount:,} coins!")

    @commands.hybrid_command(name="claim", description="Claim rewards from your roles")
    async def claim(self, ctx: commands.Context):
        await ctx.defer()
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        now = datetime.now(timezone.utc)
        last_claim = user_data.get("last_claim")

        if last_claim:
            if isinstance(last_claim, str):
                last_claim = datetime.fromisoformat(last_claim)
            elapsed = (now - last_claim).total_seconds()
            if elapsed < 3600:
                remaining = int(3600 - elapsed)
                next_claim_ts = int((now + timedelta(seconds=remaining)).timestamp())
                return await ctx.send(
                    f"❌ You already claimed your rewards. Try again <t:{next_claim_ts}:R>.",
                    ephemeral=True,
                )

        total = 0
        breakdown = []
        for key, data in ROLE_SHOP.items():
            role_id = data.get("role_id")
            if not role_id:
                continue
            role = ctx.guild.get_role(int(role_id))
            if role and role in ctx.author.roles:
                reward = data["claim"]
                total += reward
                breakdown.append(f"✨ **{role.name}** → 🪙 {reward:,}")

        if total == 0:
            return await ctx.send("❌ You don't own any claim roles.")

        eco_col.update_one(
            {"_id": user_id},
            {"$inc": {"wallet": total}, "$set": {"last_claim": now.isoformat()}},
            upsert=True,
        )
        embed = discord.Embed(title="💰 Claim Rewards", description="\n".join(breakdown), color=0x00FF99)
        embed.add_field(name="Total Claimed", value=f"🪙 {total:,}", inline=False)
        embed.set_footer(text="Come back in 1 hour for more rewards.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pay", description="Send coins to another member")
    @app_commands.describe(member="The member to send coins to", amount="Amount ('all', 'half', or number)")
    async def pay(self, ctx: commands.Context, member: discord.Member, amount: str):
        sender_id = str(ctx.author.id)
        receiver_id = str(member.id)
        if member.bot:
            return await ctx.send("❌ You cannot send coins to bots.", ephemeral=True)
        if sender_id == receiver_id:
            return await ctx.send("❌ You cannot pay yourself.", ephemeral=True)
        sender_wallet = get_wallet(sender_id)
        parsed_amount = parse_economy_amount(amount, sender_wallet)
        if parsed_amount <= 0:
            return await ctx.send("❌ Invalid amount. Please use a positive number, 'all', or 'half'.", ephemeral=True)
        if sender_wallet < parsed_amount:
            return await ctx.send(f"❌ You only have 🪙 {sender_wallet:,} in your wallet.", ephemeral=True)
        update_wallet(sender_id, -parsed_amount)
        update_wallet(receiver_id, parsed_amount)
        embed = discord.Embed(
            title="💸 Payment Sent",
            description=f"{ctx.author.mention} sent 🪙 **{parsed_amount:,}** coins to {member.mention}.",
            color=0x00FF99,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="Shows the richest members")
    async def leaderboard(self, ctx: commands.Context):
        users = sorted(
            eco_col.find(),
            key=lambda u: u.get("wallet", 0) + u.get("bank", 0),
            reverse=True,
        )[:10]

        embed = discord.Embed(title="🏆 Global Economy Leaderboard", color=0xFFD700)
        medals = {1: "🥇", 2: "🥈", 3: "🥉"}
        description = ""
        for index, user_data in enumerate(users, start=1):
            user_id = int(user_data["_id"])
            total = user_data.get("wallet", 0) + user_data.get("bank", 0)
            member = ctx.guild.get_member(user_id)
            name = member.display_name if member else f"Unknown User ({user_id})"
            medal = medals.get(index, f"`#{index}`")
            description += f"{medal} **{name}** — 🪙 {total:,}\n"
        embed.description = description
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="work", description="Work to earn coins")
    async def work(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        cooldown = 2700
        last_work = user_data.get("last_work", 0)
        now = time.time()
        if now - last_work < cooldown:
            time_left = int(cooldown - (now - last_work))
            minutes, seconds = divmod(time_left, 60)
            return await ctx.send(f"⏳ You are too tired! Come back to work in {minutes}m {seconds}s.", ephemeral=True)

        earnings = random.randint(250, 800)
        jobs = [
            "developed a futuristic Discord bot for a billionaire", "won a late-night poker tournament",
            "repaired a military drone for a secret agency", "hacked into an abandoned crypto vault",
            "worked overtime at a cyberpunk nightclub", "delivered illegal space tacos across the galaxy",
            "streamed games for 14 hours straight", "sold rare dragon eggs on the black market",
            "worked as a bodyguard for a mafia boss", "found ancient treasure hidden underground",
            "completed dangerous bounty hunter missions", "managed a shady underground casino",
            "worked at a futuristic AI laboratory", "helped a millionaire recover lost crypto",
            "participated in illegal street races", "sold enchanted weapons to traveling merchants",
            "worked as a mercenary during clan wars", "created viral memes that exploded online",
            "found money hidden behind a vending machine", "worked at a haunted hotel overnight",
            "hacked the mainframe of a rival megacorp", "smuggled rare alien artifacts past customs",
            "won a high-stakes underground racing tournament", "tamed a wild cyber-dragon for a wealthy eccentric",
            "fixed the hyperdrive on a stranded space cruiser", "defused a ticking time bomb in the city square",
            "won a legendary rap battle against an AI",
        ]
        reason = random.choice(jobs)
        eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_work": now}}, upsert=True)
        embed = discord.Embed(
            title="💼 Work Complete",
            description=f"You {reason} and earned 🪙 **{earnings:,}** coins.",
            color=0x00FF99,
        )
        embed.set_footer(text="Come back in 45 minutes for another shift.")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="crime", description="Commit a crime for big money, but risk getting caught!")
    async def crime(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        wallet = user_data.get("wallet", 0)
        cooldown = 7200
        last_crime = user_data.get("last_crime", 0)
        now = time.time()
        if now - last_crime < cooldown:
            time_left = int(cooldown - (now - last_crime))
            hours, minutes = divmod(time_left, 3600)
            return await ctx.send(
                f"⏳ The heat is too high! Lay low for {hours}h {minutes // 60}m before committing another crime.",
                ephemeral=True,
            )
        if wallet < 1000:
            return await ctx.send("❌ You need at least 🪙 1,000 in your wallet to commit a crime (to bribe the cops just in case).", ephemeral=True)

        success = random.choice([True, False])
        if success:
            earnings = random.randint(2000, 6500)
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_crime": now}}, upsert=True)
            msg = random.choice([
                "robbed an underground casino", "hacked a billionaire's bank account",
                "stole a cybernetic sports car", "smuggled rare alien artifacts",
                "sold counterfeit Kirka skins on the black market",
            ])
            embed = discord.Embed(title="🦹 Crime Successful", description=f"You {msg} and got away with 🪙 **{earnings:,}** coins!", color=0x2ECC71)
        else:
            fine = random.randint(1000, min(3500, wallet))
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": -fine}, "$set": {"last_crime": now}}, upsert=True)
            msg = random.choice([
                "tripped over a trash can while running from the cops", "left your ID at the crime scene",
                "tried to hack a government server but forgot to turn on your VPN",
                "got caught by a cybernetic guard dog", "were betrayed by your getaway driver",
            ])
            embed = discord.Embed(title="🚔 BUSTED!", description=f"You {msg}.\n\nYou were fined 🪙 **{fine:,}** coins.", color=0xE74C3C)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rob", description="Attempt to rob another member")
    async def rob(self, ctx: commands.Context, member: discord.Member):
        thief_id = str(ctx.author.id)
        target_id = str(member.id)
        user_data = get_user_data(thief_id)
        target_data = get_user_data(target_id)
        cooldown = 3600
        last_rob = user_data.get("last_rob", 0)
        now = time.time()
        if now - last_rob < cooldown:
            time_left = int(cooldown - (now - last_rob))
            return await ctx.send(f"⏳ The cops are still looking for you! Lay low for {time_left // 60}m.", ephemeral=True)
        if thief_id == target_id:
            return await ctx.send("❌ You cannot rob yourself.", ephemeral=True)
        if target_data.get("wallet", 0) < 300:
            return await ctx.send("❌ This user doesn't have enough wallet coins to rob.", ephemeral=True)

        success = random.choice([True, False])
        if success:
            stolen = random.randint(150, int(target_data.get("wallet", 0) * 0.30))
            eco_col.update_one({"_id": thief_id}, {"$inc": {"wallet": stolen}, "$set": {"last_rob": now}}, upsert=True)
            eco_col.update_one({"_id": target_id}, {"$inc": {"wallet": -stolen}}, upsert=True)
            msg = random.choice([
                "jumped through a window like a movie thief", "pickpocketed them during a crowded concert",
                "used fake security credentials to access their vault", "escaped through the rooftops after the robbery",
                "executed the perfect stealth mission", "used smoke grenades and escaped unseen",
                "hacked their crypto wallet remotely", "bribed the guards and walked out the front door",
                "used a teleporter to snatch their wallet", "distracted them with a hologram and grabbed the cash",
                "disguised yourself as a pizza delivery driver and looted the place",
            ])
            embed = discord.Embed(title="🥷 Successful Robbery", description=f"You {msg}.\n\nYou stole 🪙 **{stolen:,}** from {member.mention}.", color=0x00FF00)
        else:
            fine = random.randint(150, 500)
            eco_col.update_one({"_id": thief_id}, {"$inc": {"wallet": -fine}, "$set": {"last_rob": now}}, upsert=True)
            msg = random.choice([
                "tripped the alarm system", "got caught by security cameras",
                "accidentally robbed a police officer", "left fingerprints everywhere",
                "triggered laser security defenses", "was betrayed by your getaway driver",
                "got tackled by bodyguards", "got outsmarted by a decoy safe",
                "was chased down by a cybernetic guard dog", "dropped the loot while trying to escape over a fence",
                "sneezed loudly while hiding in the closet",
            ])
            embed = discord.Embed(title="🚨 Robbery Failed", description=f"You {msg}.\n\nYou paid a fine of 🪙 **{fine:,}**.", color=0xFF0000)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="sell", description="Sell an item from your inventory")
    async def sell(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        from utils.economy import get_user_data as _get
        user_data = _get(user_id)
        inventory = user_data.get("inventory", [])
        if not inventory:
            return await ctx.send("🎒 Your inventory is empty.")
        embed = discord.Embed(title="💰 Sell Item", description="Choose an item to sell.", color=0xE67E22)
        await ctx.send(embed=embed, view=SellView(ctx, inventory))

    @commands.hybrid_command(name="inventory", aliases=["inv"], description="View your inventory")
    async def inventory(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        from utils.economy import get_user_data as _get
        user_data = _get(user_id)
        inventory = user_data.get("inventory", [])
        if not inventory:
            return await ctx.send("🎒 Your inventory is empty.")
        rarity_emojis = {"common": "⚪", "rare": "🔵", "epic": "🟣", "legendary": "🟡"}
        embed = discord.Embed(title=f"🎒 {ctx.author.name}'s Inventory", color=0x2ECC71)
        total_value = 0
        text = ""
        for item in inventory[:25]:
            rarity = item["rarity"]
            emoji = rarity_emojis.get(rarity, "⚪")
            text += f"{emoji} {item['name']} • 🪙 {item['value']:,}\n"
            total_value += item["value"]
        embed.description = text
        embed.add_field(name="💰 Total Inventory Value", value=f"🪙 {total_value:,}", inline=False)
        embed.set_footer(text=f"{len(inventory)} items stored")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="claimdrop", description="Claim the active global drop")
    async def claimdrop(self, ctx: commands.Context):
        if not state.active_global_drop:
            return await ctx.send("❌ No active global drop.")
        user_id = str(ctx.author.id)
        if state.active_global_drop["type"] == "coins":
            reward = state.active_global_drop["reward"]
            eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": reward}}, upsert=True)
            await ctx.send(f"🌠 {ctx.author.mention} claimed the drop and received 🪙 {reward:,}!")
        else:
            item = state.active_global_drop["item"]
            eco_col.update_one({"_id": user_id}, {"$push": {"inventory": item}}, upsert=True)
            await ctx.send(
                f"🌠 {ctx.author.mention} claimed:\n\n{item['name']} • {item['rarity'].capitalize()}!"
            )
        state.active_global_drop = None


async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
