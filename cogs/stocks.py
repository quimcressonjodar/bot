import discord
from discord.ext import commands, tasks
from discord import app_commands
import time
import random
from config import STOCKS, STOCK_UPDATE_INTERVAL, STOCK_FEE
from utils.stocks import (
    update_stock_prices, generate_stock_chart, get_current_price,
    get_user_portfolio, buy_stock, sell_stock, process_dividends,
    load_ipo_stocks, add_ipo_stock,
    add_price_alert, get_user_alerts, remove_alert_by_id, check_price_alerts,
    stock_alerts_col,
)
from utils.stock_news import get_random_news
from utils.economy import get_wallet, update_wallet, get_bank, get_prestige_level
from utils.helpers import is_admin


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

                if profit > 0:
                    from utils.bounties import track_bounty_progress
                    bot = self.ctx.bot if hasattr(self.ctx, "bot") else self.ctx
                    await track_bounty_progress(bot, user_id, "TRADER", profit)

                if profit > 0:
                    result_line = f"📈 **+🪙 {profit:,}** de ganancia"
                    color = 0x2ECC71
                    title = "✅ Venta completada — Ganancia"
                elif profit < 0:
                    result_line = f"📉 **-🪙 {abs(profit):,}** de pérdida"
                    color = 0xE74C3C
                    title = "✅ Venta completada — Pérdida"
                else:
                    result_line = "➡️ Sin cambios (precio igual al de compra)"
                    color = 0x95A5A6
                    title = "✅ Venta completada"

                fee_paid = int(price * quantity * current_fee)
                embed = discord.Embed(title=title, color=color)
                embed.add_field(name="📦 Acciones vendidas", value=f"**{quantity}x {self.symbol}**", inline=True)
                embed.add_field(name="💰 Recibido", value=f"🪙 {total_gain:,}", inline=True)
                embed.add_field(
                    name="📊 Precio venta vs compra",
                    value=f"🪙 {price:,} → avg 🪙 {int(avg_price):,}",
                    inline=False,
                )
                embed.add_field(name="📈 Resultado", value=result_line, inline=False)
                if fee_paid > 0:
                    embed.set_footer(text=f"Comisión aplicada: 🪙 {fee_paid:,}")

                return await target.response.send_message(embed=embed, ephemeral=True) if is_interaction else await target.send(embed=embed)
            else:
                msg = "❌ No tienes suficientes acciones para vender."
                return await target.response.send_message(msg, ephemeral=True) if is_interaction else await target.send(msg)


class Stocks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.update_stocks.start()
        self.distribute_dividends.start()

    def cog_unload(self):
        self.update_stocks.cancel()
        self.distribute_dividends.cancel()

    # ------------------------------------------------------------------
    # Background tasks
    # ------------------------------------------------------------------

    @tasks.loop(minutes=STOCK_UPDATE_INTERVAL)
    async def update_stocks(self):
        try:
            news_impact = {}
            if random.random() < 0.20:
                symbol, message, multiplier = get_random_news()
                news_impact[symbol] = multiplier

                STOCK_NEWS_CHANNEL_ID = 1206197908399980575
                channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(title="🗞️ Market News Alert", description=message, color=0xF1C40F)
                    if symbol != "ALL":
                        embed.set_footer(text=f"Impact: {symbol}")
                    await channel.send(embed=embed)

            update_stock_prices(news_impact)

            # Check price alerts after every price update
            await check_price_alerts(self.bot)

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
                        color=0x2ECC71,
                    )
                    await channel.send(embed=embed)
        except Exception as e:
            print(f"DIVIDEND ERROR: {e}")

    @update_stocks.before_loop
    async def before_update_stocks(self):
        await self.bot.wait_until_ready()
        # Load any persisted IPO stocks into the live STOCKS dict
        load_ipo_stocks()
        # Ensure at least two data points for charts on first run
        from utils.stocks import stocks_col
        for symbol in STOCKS:
            history = stocks_col.find_one({"symbol": symbol})
            if not history or len(history.get("prices", [])) < 2:
                update_stock_prices()
                break

    # ------------------------------------------------------------------
    # Trading commands
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="sbuy", description="Buy stocks from the market")
    @app_commands.describe(symbol="Stock symbol (e.g. VRTX)", quantity="Amount to buy ('all', 'max', or number)")
    async def sbuy(self, ctx: commands.Context, symbol: str, quantity: str):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)

        user_id = str(ctx.author.id)
        wallet = get_wallet(user_id)
        price = get_current_price(symbol)

        level = get_prestige_level(wallet + get_bank(user_id))
        fee_multiplier = 1.0 + (STOCK_FEE * (1 - (level / 7.0)))
        cost_per_share = price * fee_multiplier

        if quantity.lower() in ["all", "max"]:
            if cost_per_share > wallet:
                return await ctx.send(
                    f"❌ You can't afford any shares of {symbol}. You need at least 🪙 {int(cost_per_share):,}.",
                    ephemeral=True,
                )
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

    @commands.hybrid_command(name="stocks", aliases=["socks", "stock", "st"], description="View the stock market")
    async def stocks(self, ctx: commands.Context, symbol: str = None):
        await ctx.defer()

        if not symbol:
            embed = discord.Embed(title="📈 Global Stock Market", color=0x2B2D31)
            description = "Use `!stocks <symbol>` to see detailed charts and trade.\n\n"
            for s, cfg in STOCKS.items():
                try:
                    price = get_current_price(s)
                    description += f"**{s}** - {cfg['name']}\nPrice: 🪙 {price:,}\n\n"
                except Exception:
                    description += f"**{s}** - {cfg['name']}\nPrice: *Calculating...*\n\n"
            embed.description = description
            return await ctx.send(embed=embed)

        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(f"❌ Stock symbol **{symbol}** not found.", ephemeral=True)

        try:
            price = get_current_price(symbol)
            embed = discord.Embed(
                title=f"📊 {STOCKS[symbol]['name']} ({symbol})",
                description=f"{STOCKS[symbol]['description']}\n\n**Current Price:** 🪙 {price:,}",
                color=0x3498DB,
            )

            chart = None
            try:
                chart = generate_stock_chart(symbol)
            except Exception as chart_err:
                print(f"CHART GENERATION ERROR for {symbol}: {chart_err}")

            if chart:
                embed.set_image(url=f"attachment://{symbol}_chart.png")
                view = StockView(ctx, symbol)
                await ctx.send(embed=embed, file=chart, view=view)
            else:
                view = StockView(ctx, symbol)
                await ctx.send(embed=embed, view=view)
        except Exception as e:
            print(f"STOCKS COMMAND ERROR: {e}")
            await ctx.send(f"❌ An error occurred while fetching data for {symbol}. Please try again later.")

    @commands.hybrid_command(name="portfolio", aliases=["pfol"], description="View your stock portfolio")
    async def portfolio(self, ctx: commands.Context):
        await ctx.defer()
        try:
            user_id = str(ctx.author.id)
            stocks_data = get_user_portfolio(user_id)

            if not stocks_data:
                return await ctx.send("💼 Your portfolio is empty. Start trading with `!stocks`!")

            embed = discord.Embed(title=f"💼 {ctx.author.display_name}'s Portfolio", color=0x2ECC71)
            total_value = 0
            total_profit = 0

            for symbol, data in stocks_data.items():
                try:
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
                        inline=True,
                    )
                except Exception as e:
                    print(f"ERROR processing stock {symbol} in portfolio: {e}")
                    continue

            embed.description = (
                f"**Total Portfolio Value:** 🪙 {total_value:,}\n"
                f"**Total Profit/Loss:** 🪙 {total_profit:,.0f}"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            print(f"PORTFOLIO COMMAND ERROR: {e}")
            await ctx.send("❌ An error occurred while fetching your portfolio. Please try again later.")

    # ------------------------------------------------------------------
    # Price Alert commands
    # ------------------------------------------------------------------

    @commands.hybrid_command(name="alert", description="Set a price alert — get a DM when a stock hits your target")
    @app_commands.describe(symbol="Stock symbol (e.g. CRPT)", price="Target price in coins")
    async def alert(self, ctx: commands.Context, symbol: str, price: int):
        symbol = symbol.upper()
        if symbol not in STOCKS:
            return await ctx.send(
                f"❌ Stock **{symbol}** not found. Check `!stocks` for available symbols.", ephemeral=True
            )
        if price <= 0:
            return await ctx.send("❌ El precio objetivo debe ser mayor que 0.", ephemeral=True)

        current_price = get_current_price(symbol)
        if current_price == price:
            return await ctx.send(
                "❌ El precio objetivo es igual al precio actual. Elige un valor diferente.", ephemeral=True
            )

        user_id = str(ctx.author.id)
        existing = get_user_alerts(user_id)
        if len(existing) >= 5:
            return await ctx.send(
                "❌ Ya tienes 5 alertas activas (máximo). Cancela alguna con `!cancelalert` antes de añadir otra.",
                ephemeral=True,
            )

        direction = "above" if price > current_price else "below"
        alert_id = add_price_alert(user_id, symbol, price)

        arrow = "📈" if direction == "above" else "📉"
        verb = "suba a" if direction == "above" else "baje a"

        embed = discord.Embed(
            title="🔔 Alerta de precio creada",
            description=(
                f"{arrow} Te avisaré por DM cuando **{symbol}** {verb} 🪙 **{price:,}**\n\n"
                f"💹 Precio actual: 🪙 **{current_price:,}**"
            ),
            color=0x3498DB,
        )
        embed.set_footer(text=f"ID: {alert_id} • Cancela con: !cancelalert {alert_id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="myalerts", description="View your active price alerts")
    async def myalerts(self, ctx: commands.Context):
        user_id = str(ctx.author.id)
        alerts = get_user_alerts(user_id)

        if not alerts:
            return await ctx.send(
                "📭 No tienes alertas activas. Crea una con `!alert <símbolo> <precio>`."
            )

        embed = discord.Embed(title="🔔 Tus alertas de precio activas", color=0x3498DB)
        for a in alerts:
            symbol = a["symbol"]
            target = a["target_price"]
            direction = a["direction"]
            arrow = "📈" if direction == "above" else "📉"
            verb = "≥" if direction == "above" else "≤"
            try:
                current = get_current_price(symbol)
                current_text = f"Precio actual: 🪙 {current:,}"
            except Exception:
                current_text = "Precio actual: desconocido"
            embed.add_field(
                name=f"{arrow} {symbol} {verb} 🪙 {target:,}",
                value=f"{current_text}\n`!cancelalert {a['_id']}`",
                inline=False,
            )

        embed.set_footer(text="Usa !cancelalert <id> para eliminar una alerta")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="cancelalert", description="Cancel an active price alert")
    @app_commands.describe(alert_id="Alert ID shown in !myalerts")
    async def cancelalert(self, ctx: commands.Context, alert_id: str):
        user_id = str(ctx.author.id)
        from bson import ObjectId
        try:
            oid = ObjectId(alert_id)
        except Exception:
            return await ctx.send("❌ ID de alerta inválido.", ephemeral=True)

        alert = stock_alerts_col.find_one({"_id": oid, "user_id": user_id})
        if not alert:
            return await ctx.send("❌ Alerta no encontrada o no te pertenece.", ephemeral=True)

        remove_alert_by_id(alert_id)
        embed = discord.Embed(
            title="✅ Alerta cancelada",
            description=f"La alerta de **{alert['symbol']}** a 🪙 {alert['target_price']:,} ha sido eliminada.",
            color=0x2ECC71,
        )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # IPO command (admin only)
    # ------------------------------------------------------------------

    @commands.hybrid_command(
        name="ipo",
        description="List a new company on the stock market, removing the worst performer (Admin only)",
    )
    @app_commands.describe(
        symbol="Ticker symbol for the new company (e.g. NOVA)",
        name="Full company name",
        volatility="Price volatility 0.01–0.50 (default 0.10)",
        initial_price="Starting price in coins (default 500)",
        description="Short company description",
    )
    @app_commands.default_permissions(administrator=True)
    async def ipo(
        self,
        ctx: commands.Context,
        symbol: str,
        name: str,
        volatility: float = 0.10,
        initial_price: int = 500,
        *,
        description: str = "A new company entering the market.",
    ):
        if not is_admin(ctx):
            return await ctx.send("❌ Admin only.", ephemeral=True)

        symbol = symbol.upper()

        if symbol in STOCKS:
            return await ctx.send(f"❌ **{symbol}** ya existe en el mercado.", ephemeral=True)

        if not (2 <= len(symbol) <= 6) or not symbol.isalpha():
            return await ctx.send("❌ El símbolo debe tener entre 2 y 6 letras.", ephemeral=True)

        volatility = max(0.01, min(0.50, volatility))
        initial_price = max(50, initial_price)

        data = {
            "name": name,
            "sector": "IPO",
            "volatility": volatility,
            "initial_price": initial_price,
            "description": description,
        }

        removed = add_ipo_stock(symbol, data)

        embed = discord.Embed(title="🏦 ¡Nueva empresa en el mercado!", color=0xF1C40F)
        embed.add_field(name="🆕 Nueva empresa", value=f"**{symbol}** — {name}", inline=False)
        embed.add_field(name="💹 Precio inicial", value=f"🪙 {initial_price:,}", inline=True)
        embed.add_field(name="📊 Volatilidad", value=f"{volatility:.0%}", inline=True)
        embed.add_field(name="📝 Descripción", value=description, inline=False)
        if removed:
            embed.add_field(
                name="📉 Empresa retirada (peor rendimiento)",
                value=f"**{removed}** ha salido del mercado.",
                inline=False,
            )
        embed.set_footer(text="Las noticias del mercado ya pueden afectar a la nueva empresa.")

        STOCK_NEWS_CHANNEL_ID = 1206197908399980575
        channel = self.bot.get_channel(STOCK_NEWS_CHANNEL_ID)
        if channel and channel.id != ctx.channel.id:
            await channel.send(embed=embed)

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Stocks(bot))
