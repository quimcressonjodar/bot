import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
from config import STOCKS, STOCK_UPDATE_INTERVAL, STOCK_FEE
from utils.stocks import (
    update_stock_prices, generate_stock_chart, get_current_price,
    get_user_portfolio, buy_stock, sell_stock
)
from utils.economy import get_wallet, update_wallet, get_bank, get_prestige_level

class StockView(discord.ui.View):
    def __init__(self, ctx, symbol):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.symbol = symbol

    @discord.ui.button(label="Buy 1", style=discord.ButtonStyle.green)
    async def buy_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 1, "buy")

    @discord.ui.button(label="Buy 10", style=discord.ButtonStyle.green)
    async def buy_ten(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 10, "buy")

    @discord.ui.button(label="Sell 1", style=discord.ButtonStyle.red)
    async def sell_one(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.process_trade(interaction, 1, "sell")

    @discord.ui.button(label="Sell All", style=discord.ButtonStyle.red)
    async def sell_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        portfolio = get_user_portfolio(str(interaction.user.id))
        quantity = portfolio.get(self.symbol, {}).get("quantity", 0)
        if quantity <= 0:
            return await interaction.response.send_message("❌ You don't own any shares of this stock.", ephemeral=True)
        await self.process_trade(interaction, quantity, "sell")

    async def process_trade(self, interaction, quantity, side):
        user_id = str(interaction.user.id)
        if user_id != str(self.ctx.author.id):
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)

        price = get_current_price(self.symbol)
        
        # Calculate fee with prestige discount
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        level = get_prestige_level(wallet + bank)
        
        # Fee discount: Master gets 0% fee, others get reduced fees
        fee_multiplier = max(0, 1 - (level * 0.15)) # Simple scaling for fee reduction
        current_fee = STOCK_FEE * fee_multiplier
        
        if side == "buy":
            total_cost = int(price * quantity * (1 + current_fee))
            if wallet < total_cost:
                return await interaction.response.send_message(f"❌ You need 🪙 {total_cost:,} to buy {quantity} shares (including fees).", ephemeral=True)
            
            update_wallet(user_id, -total_cost)
            buy_stock(user_id, self.symbol, quantity, price)
            await interaction.response.send_message(f"✅ Bought {quantity} shares of **{self.symbol}** for 🪙 {total_cost:,}!", ephemeral=True)
        else:
            total_gain = int(price * quantity * (1 - current_fee))
            if sell_stock(user_id, self.symbol, quantity):
                update_wallet(user_id, total_gain)
                await interaction.response.send_message(f"✅ Sold {quantity} shares of **{self.symbol}** for 🪙 {total_gain:,}!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ You don't have enough shares to sell.", ephemeral=True)

class Stocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stocks.start()

    def cog_unload(self):
        self.update_stocks.cancel()

    @tasks.loop(minutes=STOCK_UPDATE_INTERVAL)
    async def update_stocks(self):
        try:
            update_stock_prices()
        except Exception as e:
            print(f"STOCK UPDATE ERROR: {e}")

    @update_stocks.before_loop
    async def before_update_stocks(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="stocks", description="View the stock market")
    async def stocks(self, ctx: commands.Context, symbol: str = None):
        if not symbol:
            embed = discord.Embed(title="📈 Global Stock Market", color=0x2B2D31)
            description = "Use `!stocks <symbol>` to see detailed charts and trade.\n\n"
            for s, config in STOCKS.items():
                price = get_current_price(s)
                description += f"**{s}** - {config['name']}\nPrice: 🪙 {price:,}\n\n"
            embed.description = description
            return await ctx.send(embed=embed)

        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)

        await ctx.defer()
        chart = generate_stock_chart(symbol)
        price = get_current_price(symbol)
        
        embed = discord.Embed(
            title=f"📊 {STOCKS[symbol]['name']} ({symbol})",
            description=f"{STOCKS[symbol]['description']}\n\n**Current Price:** 🪙 {price:,}",
            color=0x3498DB
        )
        
        if chart:
            embed.set_image(url=f"attachment://{symbol}_chart.png")
            view = StockView(ctx, symbol)
            await ctx.send(embed=embed, file=chart, view=view)
        else:
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="portfolio", description="View your stock portfolio")
    async def portfolio(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        stocks = get_user_portfolio(user_id)
        
        if not stocks:
            return await ctx.send("💼 Your portfolio is empty. Start trading with `!stocks`!")

        embed = discord.Embed(title=f"💼 {ctx.author.display_name}'s Portfolio", color=0x2ECC71)
        total_value = 0
        total_profit = 0
        
        for symbol, data in stocks.items():
            current_price = get_current_price(symbol)
            qty = data["quantity"]
            avg = data["avg_price"]
            
            value = qty * current_price
            profit = (current_price - avg) * qty
            total_value += value
            total_profit += profit
            
            p_text = f"+🪙 {profit:,.0f}" if profit >= 0 else f"-🪙 {abs(profit):,.0f}"
            embed.add_field(
                name=f"{symbol} ({qty} shares)",
                value=f"Value: 🪙 {value:,}\nProfit: **{p_text}**\nAvg Cost: 🪙 {avg:,.0f}",
                inline=True
            )
            
        embed.description = f"**Total Portfolio Value:** 🪙 {total_value:,}\n**Total Profit/Loss:** 🪙 {total_profit:,.0f}"
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Stocks(bot))
