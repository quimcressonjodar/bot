import asyncio
import random
import secrets

import discord
from discord import app_commands
from discord.ext import commands

from config import ROULETTE_RED, VALID_BETS
from utils.economy import get_user_data, get_wallet, update_wallet, parse_economy_amount
from views.game_views import BlackjackView, RPSView


class GamesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="flip", description="Flip a coin: Heads or Tails")
    async def flip(self, ctx: commands.Context):
        msg = await ctx.send("Flipping the coin...")
        result = secrets.choice(["Heads", "Tails"])
        await asyncio.sleep(1)
        await msg.edit(content=f"Flipping the coin... 🪙 **{result}**")

    @commands.hybrid_command(name="roulette", aliases=["r"], description="Bet on the casino roulette wheel")
    @app_commands.describe(
        bet_amount="Amount ('all', 'half', or number)",
        bet_on="What are you betting on?",
        number="Number to bet on (if you chose specific_number)",
    )
    @app_commands.choices(bet_on=[
        app_commands.Choice(name="🔴 Red (x2)", value="red"),
        app_commands.Choice(name="⚫ Black (x2)", value="black"),
        app_commands.Choice(name="🔢 Even (x2)", value="even"),
        app_commands.Choice(name="🔢 Odd (x2)", value="odd"),
        app_commands.Choice(name="🥇 1st 12 (1-12) (x3)", value="1st"),
        app_commands.Choice(name="🥈 2nd 12 (13-24) (x3)", value="2nd"),
        app_commands.Choice(name="🥉 3rd 12 (25-36) (x3)", value="3rd"),
        app_commands.Choice(name="🎯 Specific Number (x36)", value="specific_number"),
    ])
    async def roulette(self, ctx: commands.Context, bet_amount: str, bet_on: str, number: int = None):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        bet = parse_economy_amount(bet_amount, user_data["wallet"])

        if bet <= 0:
            return await ctx.send("❌ Invalid bet. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
        if user_data["wallet"] < bet:
            return await ctx.send(f"❌ You don't have enough coins. Your balance is 🪙 {user_data['wallet']:,}.", ephemeral=True)

        bet_aliases = {
            "number": "specific_number", "num": "specific_number", "n": "specific_number",
            "red": "red", "black": "black", "even": "even", "odd": "odd",
        }
        bet_on = bet_aliases.get(bet_on.lower(), bet_on.lower())

        if bet_on not in VALID_BETS:
            return await ctx.send(
                "❌ Invalid bet type.\nValid bets: red, black, even, odd, number, 1st, 2nd, 3rd",
                ephemeral=True,
            )

        if bet_on == "specific_number" and (number is None or not (0 <= number <= 36)):
            return await ctx.send("❌ Please provide a valid number between 0 and 36.", ephemeral=True)

        spin_msg = await ctx.send("🎰 **Throwing the ball...** 🔄\n`[          ] 0%`")
        animation_frames = [
            "🎰 **Spinning...** 🔴 14\n`[▬▬        ] 25%`",
            "🎰 **Spinning...** ⬛ 22\n`[▬▬▬▬▬     ] 50%`",
            "🎰 **Slowing down...** 🟢 0\n`[▬▬▬▬▬▬▬   ] 75%`",
            "🎰 **Almost there...** 🔴 7\n`[▬▬▬▬▬▬▬▬▬ ] 99%`",
        ]
        for frame in animation_frames:
            await asyncio.sleep(0.8)
            await spin_msg.edit(content=frame)

        winning_number = secrets.randbelow(37)

        is_red = winning_number in ROULETTE_RED
        is_black = winning_number != 0 and not is_red
        color_emoji = "🟩" if winning_number == 0 else ("🟥" if is_red else "⬛")
        color_text = "Green" if winning_number == 0 else ("Red" if is_red else "Black")

        win = False
        multiplier = 0
        if bet_on == "red" and is_red:
            win, multiplier = True, 2
        elif bet_on == "black" and is_black:
            win, multiplier = True, 2
        elif bet_on == "even" and winning_number != 0 and winning_number % 2 == 0:
            win, multiplier = True, 2
        elif bet_on == "odd" and winning_number % 2 != 0:
            win, multiplier = True, 2
        elif bet_on == "specific_number" and number == winning_number:
            win, multiplier = True, 36
        elif bet_on == "1st" and 1 <= winning_number <= 12:
            win, multiplier = True, 3
        elif bet_on == "2nd" and 13 <= winning_number <= 24:
            win, multiplier = True, 3
        elif bet_on == "3rd" and 25 <= winning_number <= 36:
            win, multiplier = True, 3

        bet_target_display = {
            "red": "Red", "black": "Black", "even": "Even", "odd": "Odd",
            "1st": "1st 12 (1-12)", "2nd": "2nd 12 (13-24)", "3rd": "3rd 12 (25-36)",
        }.get(bet_on, bet_on.capitalize())
        if bet_on == "specific_number":
            bet_target_display = f"Number {number}"

        embed = discord.Embed(title="🎰 Casino Roulette", color=0x00FF00 if win else 0xFF0000)
        embed.set_author(name=f"{ctx.author.display_name}'s Spin", icon_url=ctx.author.display_avatar.url)
        embed.add_field(name="📝 Bet Details", value=f"**Amount:** 🪙 {bet:,}\n**Bet On:** {bet_target_display}", inline=True)
        embed.add_field(name="🎯 The Spin", value=f"**Landed On:**\n{color_emoji} **{color_text} {winning_number}**", inline=True)

        if win:
            winnings = bet * multiplier
            profit = winnings - bet
            update_wallet(user_id, profit)
            embed.add_field(name="🎉 Outcome", value=f"**WIN!** (x{multiplier} multiplier)\nYou won 🪙 **{winnings:,}**!", inline=False)
        else:
            update_wallet(user_id, -bet)
            embed.add_field(name="💀 Outcome", value=f"**LOSS!**\nYou lost 🪙 **{bet:,}**.", inline=False)

        embed.set_footer(text=f"New Wallet Balance: 🪙 {get_wallet(user_id):,}")
        await asyncio.sleep(0.8)
        await spin_msg.edit(content="🛑 **The wheel stopped!**", embed=embed)

    @commands.hybrid_command(name="blackjack", aliases=["bj"], description="Play a realistic hand of blackjack")
    @app_commands.describe(bet_amount="Amount ('all', 'half', or number)")
    async def blackjack(self, ctx: commands.Context, bet_amount: str):
        user_id = str(ctx.author.id)
        user_data = get_user_data(user_id)
        bet = parse_economy_amount(bet_amount, user_data["wallet"])
        if bet <= 0:
            return await ctx.send("❌ Invalid bet. Please specify a positive number, 'all', or 'half'.")
        if user_data["wallet"] < bet:
            return await ctx.send(f"❌ You don't have enough coins. Your balance is 🪙 {user_data['wallet']:,}.")
        view = BlackjackView(ctx, bet)
        await ctx.send(embed=view.create_embed(), view=view)

    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
    @app_commands.describe(question="The question you want to ask")
    async def eight_ball(self, ctx: commands.Context, question: str):
        responses = [
            "It is certain.", "It is decidedly so.", "Without a doubt.",
            "Yes - definitely.", "You may rely on it.", "As I see it, yes.",
            "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
            "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
            "Cannot predict now.", "Concentrate and ask again.",
            "Don't count on it.", "My reply is no.", "My sources say no.",
            "Outlook not so good.", "Very doubtful.",
        ]
        embed = discord.Embed(color=0x2B2D31)
        embed.description = (
            f"🎱 **{ctx.author.display_name} asks:** {question}\n"
            f"💬 **Answer:** {random.choice(responses)}"
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="rps", description="Play Rock, Paper, Scissors against the bot")
    async def rps(self, ctx: commands.Context):
        embed = discord.Embed(title="Rock, Paper, Scissors", description="Choose your weapon below! 👇", color=0x2B2D31)
        await ctx.send(embed=embed, view=RPSView(ctx.author))


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesCog(bot))
