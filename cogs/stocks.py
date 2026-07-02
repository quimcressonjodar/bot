import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import random
from config import STOCKS, STOCK_UPDATE_INTERVAL, STOCK_FEE
from utils.stocks import (
    update_stock_prices, generate_stock_chart, get_current_price,
    get_user_portfolio, buy_stock, sell_stock, process_dividends
)
from utils.stock_news import get_random_news
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
        if str(interaction.user.id) != str(self.ctx.author.id):
            return await interaction.response.send_message("❌ This is not your menu.", ephemeral=True)
        await self.process_trade_direct(interaction, quantity, side)

    async def process_trade_direct(self, target, quantity, side):
        # target can be an interaction or a context
        is_interaction = isinstance(target, discord.Interaction)
        user = target.user if is_interaction else target.author
        user_id = str(user.id)
        
        price = get_current_price(self.symbol)
        wallet = get_wallet(user_id)
        bank = get_bank(user_id)
        level = get_prestige_level(wallet + bank)
        
        fee_multiplier = max(0, 1 - (level * 0.15))
        current_fee = STOCK_FEE * fee_multiplier
        
        if side == "buy":
            total_cost = int(price * quantity * (1 + current_fee))
            if wallet < total_cost:
                msg = f"❌ You need 🪙 {total_cost:,} to buy {quantity} shares (including fees)."
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)
            
            update_wallet(user_id, -total_cost)
            buy_stock(user_id, self.symbol, quantity, price)
            msg = f"✅ Bought {quantity} shares of **{self.symbol}** for 🪙 {total_cost:,}!"
            return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)
        else:
            total_gain = int(price * quantity * (1 - current_fee))
            portfolio = get_user_portfolio(user_id)
            avg_price = portfolio.get(self.symbol, {}).get("avg_price", 0)
            profit = int((price - avg_price) * quantity)
            
            if sell_stock(user_id, self.symbol, quantity):
                update_wallet(user_id, total_gain)
                
                # Bounty Tracking
                if profit > 0:
                    from utils.bounties import track_bounty_progress
                    bot = self.ctx.bot if hasattr(self.ctx, "bot") else self.ctx
                    await track_bounty_progress(bot, user_id, "TRADER", profit)
                
                msg = f"✅ Sold {quantity} shares of **{self.symbol}** for 🪙 {total_gain:,}!"
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)
            else:
                msg = "❌ You don't have enough shares to sell."
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)

class Stocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stocks.start()
        self.distribute_dividends.start()

    def cog_unload(self):
        self.update_stocks.cancel()
        self.distribute_dividends.cancel()

    @tasks.loop(minutes=STOCK_UPDATE_INTERVAL)
    async def update_stocks(self):
        try:
            # 20% chance of a news event during update
            news_impact = {}
            if random.random() < 0.20:
                symbol, message, multiplier = get_random_news()
                news_impact[symbol] = multiplier
                
                # Announce news in a channel
                STOCK_NEWS_CHANNEL_ID = 1206197908399980575
                channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(title="🗞️ Market News Alert", description=message, color=0xF1C40F)
                    if symbol != "ALL":
                        embed.set_footer(text=f"Impact: {symbol}")
                    await channel.send(embed=embed)

            update_stock_prices(news_impact)
        except Exception as e:
            print(f"STOCK UPDATE ERROR: {e}")

    @tasks.loop(hours=24)
    async def distribute_dividends(self):
        try:
            users, total = process_dividends()
            if users > 0:
                STOCK_NEWS_CHANNEL_ID = 1206197908399980575
                channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="💰 Daily Dividends Distributed",
                        description=f"A total of 🪙 {total:,} coins were paid out to {users} shareholders!",
                        color=0x2ECC71
                    )
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"DIVIDEND ERROR: {e}")

    @update_stocks.before_loop
    async def before_update_stocks(self):
        await self.bot.wait_until_ready()
        # Ensure at least two data points for charts on first run
        from utils.stocks import stocks_col
        for symbol in STOCKS:
            history = stocks_col.find_one({"symbol": symbol})
            if not history or len(history.get("prices", [])) < 2:
                update_stock_prices()
                break

    @commands.hybrid_command(name="sbuy", description="Buy stocks from the market")
    @app_commands.describe(symbol="Stock symbol (e.g. VRTX)", quantity="Amount to buy ('all', 'max', or number)")
    async def sbuy(self, ctx: commands.Context, symbol: str, quantity: str):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)
        
        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        price = get_current_price(symbol)
        
        # Calculate max possible shares
        from utils.economy import get_prestige_level
        from config import STOCK_FEE
        level = get_prestige_level(wallet + get_bank(user_id))
        fee_multiplier = 1.0 + (STOCK_FEE * (1 - (level / 7.0)))
        cost_per_share = price * fee_multiplier
        
        if quantity.lower() in ["all", "max"]:
            if cost_per_share > wallet:
                return await ctx.send(f"❌ You can't afford any shares of {symbol}. You need at least 🪙 {int(cost_per_share):,}.", ephemeral=True)
            parsed_quantity = int(wallet // cost_per_share)
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Invalid quantity. Use a number or 'all'.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ Quantity must be positive.", ephemeral=True)
        
        view = StockView(ctx, symbol)
        await view.process_trade_direct(ctx, parsed_quantity, "buy")

    @commands.hybrid_command(name="ssell", description="Sell stocks to the market")
    @app_commands.describe(symbol="Stock symbol (e.g. VRTX)", quantity="Amount to sell ('all', 'max', or number)")
    async def ssell(self, ctx: commands.Context, symbol: str, quantity: str):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)
        
        user_id = str(ctx.author.id)
        portfolio = get_user_portfolio(user_id)
        user_shares = portfolio.get(symbol, {}).get("quantity", 0)
        
        if quantity.lower() in ["all", "max"]:
            parsed_quantity = user_shares
        else:
            try:
                parsed_quantity = int(quantity.replace(",", ""))
            except ValueError:
                return await ctx.send("❌ Invalid quantity. Use a number or 'all'.", ephemeral=True)

        if parsed_quantity <= 0:
            return await ctx.send("❌ Quantity must be positive.", ephemeral=True)
        
        if parsed_quantity > user_shares:
            return await ctx.send(f"❌ You only have {user_shares} shares of {symbol}.", ephemeral=True)
            
        view = StockView(ctx, symbol)
        await view.process_trade_direct(ctx, parsed_quantity, "sell")

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

    @commands.hybrid_command(name="portfolio", aliases=["pfol"], description="View your stock portfolio")
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
