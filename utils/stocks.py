import random
import time
import os
import matplotlib
# Use Agg backend for headless environments like Render
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import io
import discord
from config import STOCKS, STOCK_HISTORY_LIMIT, WELCOME_CHANNEL_ID
from pymongo import MongoClient
from utils.stock_news import get_random_news

# MongoDB setup
MONGO_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGO_URI)
# Explicitly specify the database name from the URI or a default one
db = client.get_database("test") # Use "test" or your actual DB name if not in URI
stocks_col = db["stocks_history"]
user_stocks_col = db["user_stocks"]

def get_current_price(symbol):
    """Get the latest price for a stock symbol."""
    history = stocks_col.find_one({"symbol": symbol})
    if not history or not history.get("prices"):
        return STOCKS[symbol]["initial_price"]
    return history["prices"][-1]["price"]

def update_stock_prices(news_impact=None):
    """Update prices for all stocks using Geometric Brownian Motion logic."""
    # news_impact is a dict {symbol: multiplier}
    if news_impact is None:
        news_impact = {}

    for symbol, config in STOCKS.items():
        # Apply news multiplier if exists for this symbol or "ALL"
        multiplier = news_impact.get(symbol, 1.0) * news_impact.get("ALL", 1.0)
        history = stocks_col.find_one({"symbol": symbol})
        if not history:
            prices = [{"price": config["initial_price"], "timestamp": time.time()}]
            stocks_col.insert_one({"symbol": symbol, "prices": prices})
            continue
        
        current_prices = history.get("prices", [])
        last_price = current_prices[-1]["price"]
        
        # Simple GBM-like fluctuation
        # price_t = price_{t-1} * (1 + drift + volatility * random_normal)
        # Drift is slightly positive to encourage long-term growth
        drift = 0.001 
        volatility = config["volatility"]
        change = random.normalvariate(drift, volatility)
        new_price = max(10, int(last_price * (1 + change) * multiplier)) # Minimum price 10
        
        new_entry = {"price": new_price, "timestamp": time.time()}
        current_prices.append(new_entry)
        
        # Keep only the last N points
        if len(current_prices) > STOCK_HISTORY_LIMIT:
            current_prices = current_prices[-STOCK_HISTORY_LIMIT:]
            
        stocks_col.update_one({"symbol": symbol}, {"$set": {"prices": current_prices}})

def generate_stock_chart(symbol):
    """Generate a PNG chart for a stock symbol and return as discord.File."""
    history = stocks_col.find_one({"symbol": symbol})
    if not history or len(history.get("prices", [])) < 2:
        return None
        
    prices = [p["price"] for p in history["prices"]]
    timestamps = [pd.to_datetime(p["timestamp"], unit='s') for p in history["prices"]]
    
    df = pd.DataFrame({"timestamp": timestamps, "price": prices})
    
    # Plotting
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))
    
    color = '#2ecc71' if prices[-1] >= prices[0] else '#e74c3c'
    ax.plot(df['timestamp'], df['price'], color=color, linewidth=2)
    ax.fill_between(df['timestamp'], df['price'], alpha=0.1, color=color)
    
    # Customizing
    ax.set_title(f"{STOCKS[symbol]['name']} ({symbol})", fontsize=16, color='white', pad=20)
    ax.set_ylabel("Price (Coins)", color='white')
    ax.grid(True, alpha=0.2)
    
    # Format x-axis
    fig.autofmt_xdate()
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    plt.close(fig)
    
    return discord.File(fp=buf, filename=f"{symbol}_chart.png")

def get_user_portfolio(user_id):
    """Get a user's stock portfolio."""
    portfolio = user_stocks_col.find_one({"_id": user_id})
    return portfolio.get("stocks", {}) if portfolio else {}

def buy_stock(user_id, symbol, quantity, price):
    """Record a stock purchase for a user."""
    portfolio = user_stocks_col.find_one({"_id": user_id})
    if not portfolio:
        user_stocks_col.insert_one({"_id": user_id, "stocks": {}})
        portfolio = {"stocks": {}}
        
    stocks = portfolio.get("stocks", {})
    if symbol not in stocks:
        stocks[symbol] = {"quantity": 0, "avg_price": 0}
        
    current = stocks[symbol]
    new_total_cost = (current["quantity"] * current["avg_price"]) + (quantity * price)
    new_quantity = current["quantity"] + quantity
    
    stocks[symbol] = {
        "quantity": new_quantity,
        "avg_price": new_total_cost / new_quantity
    }
    
    user_stocks_col.update_one({"_id": user_id}, {"$set": {"stocks": stocks}})

def sell_stock(user_id, symbol, quantity):
    """Record a stock sale for a user."""
    portfolio = user_stocks_col.find_one({"_id": user_id})
    if not portfolio or symbol not in portfolio.get("stocks", {}):
        return False
        
    stocks = portfolio["stocks"]
    if stocks[symbol]["quantity"] < quantity:
        return False
        
    stocks[symbol]["quantity"] -= quantity
    if stocks[symbol]["quantity"] == 0:
        del stocks[symbol]
        
    user_stocks_col.update_one({"_id": user_id}, {"$set": {"stocks": stocks}})
    return True

def process_dividends():
    """Distribute dividends to all stock holders (0.5% of current value)."""
    dividend_rate = 0.005
    all_portfolios = user_stocks_col.find()
    
    total_distributed = 0
    users_paid = 0
    
    from utils.economy import update_wallet
    
    for portfolio in all_portfolios:
        user_id = portfolio["_id"]
        stocks = portfolio.get("stocks", {})
        user_total_dividend = 0
        
        for symbol, data in stocks.items():
            current_price = get_current_price(symbol)
            dividend = int(current_price * data["quantity"] * dividend_rate)
            user_total_dividend += dividend
            
        if user_total_dividend > 0:
            update_wallet(user_id, user_total_dividend)
            total_distributed += user_total_dividend
            users_paid += 1
            
    return users_paid, total_distributed
