import os
import logging
import asyncio
import random
import pymongo
import uuid
import secrets
import time
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Any
from urllib.parse import quote

import aiohttp
import discord
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv

client = pymongo.MongoClient(os.getenv("MONGO_URI"))
db = client["kirka_bot"]
pets_col = db["pets"]
warns_col = db["warns"]
snaps_col = db["snapshots"]
eco_col = db["economy"]
active_battles = {}
active_global_drop = None

def get_user_data(user_id: str):
    user = eco_col.find_one({"_id": user_id})

    if not user:
        user = {
            "_id": user_id,
            "wallet": 0,
            "bank": 0
        }
        eco_col.insert_one(user)

    if "balance" in user:
        wallet_amount = user.get("balance", 0)

        eco_col.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "wallet": wallet_amount,
                    "bank": 0
                },
                "$unset": {
                    "balance": ""
                }
            }
        )

        user["wallet"] = wallet_amount
        user["bank"] = 0

    return user
def parse_economy_amount(amount_input: str, max_balance: int) -> int:
    """Parses user input for economy commands supporting 'all', 'half', or integer."""
    amount_input = str(amount_input).lower().strip()
    
    if amount_input == "all":
        return max_balance
    elif amount_input == "half":
        return max(1, max_balance // 2) # Ensure it returns at least 1 if they have 1 coin
    else:
        try:
            amount = int(amount_input)
            return amount
        except ValueError:
            return -1 # Returns -1 to trigger the invalid amount error


def get_wallet(user_id: str) -> int:
    return get_user_data(user_id)["wallet"]


def get_bank(user_id: str) -> int:
    return get_user_data(user_id)["bank"]


def update_wallet(user_id: str, amount: int):
    eco_col.update_one(
        {"_id": user_id},
        {"$inc": {"wallet": amount}},
        upsert=True
    )


def update_bank(user_id: str, amount: int):
    eco_col.update_one(
        {"_id": user_id},
        {"$inc": {"bank": amount}},
        upsert=True
    )

try:
    from tabulate import tabulate
except ImportError:
    tabulate = None

from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot activo"

def run():
    port = int(os.getenv("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("weekly-xp-bot")

DEFAULT_WEEKLY_XP_REQUIREMENT = 30_000
WEEKLY_XP_REQUIREMENT = int(os.getenv("WEEKLY_XP_REQUIREMENT", str(DEFAULT_WEEKLY_XP_REQUIREMENT)))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
KIRKA_API_KEY = os.getenv("KIRKA_API_KEY", "")
CLAN_NAME = os.getenv("KIRKA_CLAN_TAG", "UsAsOne!")
KIRKA_API_BASE = os.getenv("KIRKA_API_BASE", "https://api.kirka.io")
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
HTTP_MAX_RETRIES = int(os.getenv("HTTP_MAX_RETRIES", "3"))
HTTP_RETRY_BASE_DELAY = float(os.getenv("HTTP_RETRY_BASE_DELAY", "0.8"))
WELCOME_CHANNEL_ID = 1206229312743809054
ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
CARD_EMOJIS = {
    '♠️': {'2': '🂢', '3': '🂣', '4': '🂤', '5': '🂥', '6': '🂦', '7': '🂧', '8': '🂨', '9': '🂩', '10': '🂪', 'J': '🂫', 'Q': '🂭', 'K': '🂮', 'A': '🂡'},
    '♥️': {'2': '🂲', '3': '🂳', '4': '🂴', '5': '🂵', '6': '🂶', '7': '🂷', '8': '🂸', '9': '🂹', '10': '🂺', 'J': '🂻', 'Q': '🂽', 'K': '🂾', 'A': '🂱'},
    '♦️': {'2': '🃂', '3': '🃃', '4': '🃄', '5': '🃅', '6': '🃆', '7': '🃇', '8': '🃈', '9': '🃉', '10': '🃊', 'J': '🃋', 'Q': '🃍', 'K': '🃎', 'A': '🃁'},
    '♣️': {'2': '🃒', '3': '🃓', '4': '🃔', '5': '🃕', '6': '🃖', '7': '🃗', '8': '🃘', '9': '🃙', '10': '🃚', 'J': '🃛', 'Q': '🃝', 'K': '🃞', 'A': '🃑'}
}
CARD_BACK = "🂠"

PET_SHOP = {
    # Basic Pets - Starting higher to value early grinding
    "slime":    {"price": 5000,     "hp": 50,   "damage": 10,  "emoji": "🧪"},
    "dog":      {"price": 12000,    "hp": 100,  "damage": 20,  "emoji": "🐕"},
    "cat":      {"price": 15000,    "hp": 80,   "damage": 25,  "emoji": "🐈"},
    "owl":      {"price": 25000,    "hp": 90,   "damage": 30,  "emoji": "🦉"},
    "fox":      {"price": 40000,    "hp": 110,  "damage": 35,  "emoji": "🦊"},
    
    # Rare Pets - Significant jump in price
    "wolf":     {"price": 85000,    "hp": 150,  "damage": 40,  "emoji": "🐺"},
    "tiger":    {"price": 150000,   "hp": 180,  "damage": 50,  "emoji": "🐯"},
    "bear":     {"price": 225000,   "hp": 250,  "damage": 35,  "emoji": "🐻"},
    "griffin":  {"price": 500000,   "hp": 300,  "damage": 60,  "emoji": "🦅"},
    
    # Epic Pets - Reaching the millions
    "dragon":   {"price": 1200000,  "hp": 350,  "damage": 70,  "emoji": "🐉"},
    "golem":    {"price": 2500000,  "hp": 550,  "damage": 50,  "emoji": "🗿"},
    "hydra":    {"price": 5000000,  "hp": 450,  "damage": 90,  "emoji": "🐍"},
    "pegasus":  {"price": 8500000,  "hp": 400,  "damage": 85,  "emoji": "🦄"},
    
    # Legendary Pets - End-game content
    "phoenix":  {"price": 15000000, "hp": 400,  "damage": 120, "emoji": "🐦‍🔥"},
    "chimera":  {"price": 25000000, "hp": 500,  "damage": 130, "emoji": "🦁"},
    "kraken":   {"price": 50000000, "hp": 600,  "damage": 150, "emoji": "🦑"},
    "leviathan":{"price": 100000000,"hp": 800,  "damage": 180, "emoji": "🌊"},
    "titan":    {"price": 250000000,"hp": 1000, "damage": 200, "emoji": "👑"},
    "bahamut":  {"price": 500000000,"hp": 1500, "damage": 300, "emoji": "🌌"}
}
PET_RARITIES = {
    "slime": "basic",
    "dog": "basic",
    "cat": "basic",
    "owl": "basic",
    "fox": "basic",

    "wolf": "rare",
    "tiger": "rare",
    "bear": "rare",
    "griffin": "rare",

    "dragon": "epic",
    "golem": "epic",
    "hydra": "epic",
    "pegasus": "epic",

    "phoenix": "legendary",
    "chimera": "legendary",
    "kraken": "legendary",
    "leviathan": "legendary",
    "titan": "legendary",
    "bahamut": "legendary"
}

ADVENTURE_LOOT = {

    "common": [

        ("🪵 Stick", 15),
        ("🪨 Rock", 20),
        ("🔩 Screw", 25),
        ("🧻 Old Cloth", 18),
        ("🥫 Rusty Can", 22),
        ("🪢 Rope", 30),
        ("🧴 Plastic Bottle", 12),
        ("📎 Metal Scrap", 35),
        ("🪛 Broken Tool", 40),
        ("🪙 Small Coin", 50),
        ("🔋 Dead Battery", 28),
        ("📦 Wooden Crate", 45),
        ("🕯️ Candle", 20),
        ("🧱 Brick", 26),
        ("⚙️ Gear", 55),
        ("🪓 Rusty Axe", 60),
        ("🪤 Bear Trap", 75),
        ("📜 Torn Map", 80),
        ("🥄 Silver Spoon", 95),
        ("🧲 Magnet", 40),
        ("🧃 Juice Box", 15),
        ("🪙 Copper Coin", 35),
        ("🎣 Fishing Hook", 45),
        ("📻 Broken Radio", 90),
        ("⌚ Old Watch", 110),
        ("🧤 Leather Glove", 50),
        ("🪖 Cracked Helmet", 120),
        ("🗝️ Tiny Key", 140),
        ("🪞 Shattered Mirror", 75)
    ],

    "rare": [

        ("💍 Silver Ring", 500),
        ("🪙 Gold Coin", 750),
        ("💎 Sapphire", 1200),
        ("🔮 Magic Orb", 1500),
        ("📿 Ancient Necklace", 1800),
        ("⚔️ Knight Dagger", 2200),
        ("🏺 Ancient Vase", 2500),
        ("💠 Emerald", 3000),
        ("🧪 Rare Potion", 3500),
        ("📦 Treasure Chest", 4000),
        ("🗡️ Assassin Blade", 4200),
        ("🛡️ Golden Shield", 5000),
        ("💰 Hidden Stash", 5500),
        ("📜 Enchanted Scroll", 6000),
        ("🪬 Lucky Charm", 6500),
        ("🧿 Mystic Eye", 7000),
        ("🐚 Pearl Shell", 7500),
        ("💎 Ruby Crystal", 8000),
        ("⚡ Charged Core", 8500),
        ("🔑 Ancient Key", 9000)
    ],

    "epic": [

        ("👑 Royal Crown", 12000),
        ("💜 Amethyst Crystal", 15000),
        ("🐉 Dragon Scale", 18000),
        ("🔥 Phoenix Feather", 22000),
        ("⚡ Energy Core", 26000),
        ("🌌 Cosmic Fragment", 30000),
        ("💠 Mythic Gem", 35000),
        ("🗿 Titan Relic", 40000),
        ("🧬 Ancient DNA", 45000),
        ("🪐 Void Stone", 50000),
        ("📖 Forbidden Tome", 55000),
        ("🩸 Blood Ruby", 60000),
        ("🧊 Frozen Heart", 70000),
        ("☄️ Meteor Fragment", 80000),
        ("👁️ Cursed Eye", 90000)
    ],

    "legendary": [

        ("🌟 Celestial Artifact", 120000),
        ("👁️ Eye of Eternity", 150000),
        ("💫 Divine Crystal", 200000),
        ("🐲 Ancient Dragon Egg", 300000),
        ("🌌 Universe Shard", 500000),
        ("👑 Crown of Gods", 750000),
        ("⚔️ Blade of Chaos", 1000000),
        ("🪐 Core of the Void", 1500000),
        ("🌠 Fallen Star", 2000000),
        ("🧿 Orb of Infinity", 5000000)
    ]
}
ADVENTURE_EVENTS = {
    "common": [
        "searched through trash piles",
        "explored an abandoned alley",
        "wandered through old ruins",
        "dug near a broken wagon",
        "searched a forgotten campsite"
    ],

    "rare": [
        "explored an ancient cave",
        "snuck into a merchant caravan",
        "searched a hidden temple",
        "raided a bandit stash",
        "explored underground tunnels"
    ],

    "epic": [
        "explored volcanic ruins",
        "crossed forbidden lands",
        "searched a cursed fortress",
        "flew above ancient kingdoms",
        "ventured into magical forests"
    ],

    "legendary": [
        "vanished into the void itself",
        "crossed dimensions",
        "explored celestial ruins",
        "entered a forgotten realm",
        "traveled beyond mortal lands"
    ]
}
class SellSelect(discord.ui.Select):

    def __init__(self, ctx, inventory):

        self.ctx = ctx
        self.inventory = inventory

        options = []

        rarity_emojis = {
            "common": "⚪",
            "rare": "🔵",
            "epic": "🟣",
            "legendary": "🟡"
        }

        for index, item in enumerate(inventory[:25]):

            rarity = item.get("rarity", "common")

            options.append(
                discord.SelectOption(
                    label=item["name"][:100],
                    description=f"{rarity.capitalize()} • 🪙 {item['value']:,}",
                    emoji=rarity_emojis.get(rarity, "⚪"),
                    value=str(index)
                )
            )

        super().__init__(
            placeholder="Choose an item to sell...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        user_id = str(self.ctx.author.id)

        selected_index = int(self.values[0])

        user_data = get_user_data(user_id)

        inventory = user_data.get("inventory", [])

        if selected_index >= len(inventory):

            return await interaction.response.send_message(
                "❌ Item no longer exists.",
                ephemeral=True
            )

        item = inventory[selected_index]

        eco_col.update_one(
            {"_id": user_id},
            {
                "$inc": {"wallet": item["value"]},
                "$pull": {"inventory": item}
            }
        )

        embed = discord.Embed(
            title="💰 Item Sold",
            color=0x2ecc71
        )

        embed.description = (
            f"Sold {item['name']}\n\n"
            f"Received: 🪙 **{item['value']:,}**"
        )

        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=None
        )
class SellView(discord.ui.View):

    def __init__(self, ctx, inventory):

        super().__init__(timeout=60)

        self.add_item(
            SellSelect(ctx, inventory)
        )
class AdventureView(discord.ui.View):

    def __init__(self, ctx, pets):

        super().__init__(timeout=60)

        self.add_item(
            AdventurePetSelect(ctx, pets)
        )
class AdventurePetSelect(discord.ui.Select):

    def __init__(self, ctx, pets):

        self.ctx = ctx
        self.pets = pets

        options = []

        for pet in pets:

            pet_type = pet["type"]

            emoji = PET_SHOP[pet_type]["emoji"]

            rarity = PET_RARITIES.get(pet_type, "basic").capitalize()

            options.append(
                discord.SelectOption(
                    label=pet_type.capitalize(),
                    description=f"{rarity} Pet",
                    emoji=emoji,
                    value=pet_type
                )
            )

        super().__init__(
            placeholder="Choose a pet for the adventure...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        selected_pet_type = self.values[0]

        selected_pet = next(
            p for p in self.pets
            if p["type"] == selected_pet_type.lower()
        )

        await run_adventure(
            interaction,
            self.ctx,
            selected_pet
        )
class BlackjackView(discord.ui.View):
    def __init__(self, ctx, bet, user_wallet):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.bet = bet
        self.deck = self.create_deck()
        self.player_hand = [self.draw_card(), self.draw_card()]
        self.dealer_hand = [self.draw_card(), self.draw_card()]
        self.finished = False

    def create_deck(self):
        suits = ['♠️', '♥️', '♦️', '♣️']
        values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        deck = [{'val': v, 'suit': s} for v in values for s in suits]
        random.shuffle(deck)
        return deck

    def draw_card(self):
        return self.deck.pop()

    def calculate_score(self, hand):
        score = 0
        aces = 0
        values_map = {'J': 10, 'Q': 10, 'K': 10, 'A': 11}
        for card in hand:
            if card['val'].isdigit():
                score += int(card['val'])
            else:
                score += values_map[card['val']]
                if card['val'] == 'A': aces += 1
        
        while score > 21 and aces > 0:
            score -= 10
            aces -= 1
        return score

    def format_hand(self, hand, hide_first=False):
        if hide_first:
            return f"❓, {hand[1]['val']}{hand[1]['suit']}"
        return ", ".join([f"{c['val']}{c['suit']}" for c in hand])

    async def check_winner(self, interaction, stand=False):
        p_score = self.calculate_score(self.player_hand)
        d_score = self.calculate_score(self.dealer_hand)

        if p_score > 21:
            return await self.end_game(interaction, "You busted! Dealer wins.", -self.bet)
        
        if stand:
            while self.calculate_score(self.dealer_hand) < 17:
                self.dealer_hand.append(self.draw_card())
            
            d_score = self.calculate_score(self.dealer_hand)
            if d_score > 21:
                return await self.end_game(interaction, "Dealer busted! You win!", self.bet)
            elif p_score > d_score:
                return await self.end_game(interaction, "You win!", self.bet)
            elif p_score < d_score:
                return await self.end_game(interaction, "Dealer wins.", -self.bet)
            else:
                return await self.end_game(interaction, "It's a draw!", 0)

    async def end_game(self, interaction, result_text, win_amount):
        self.finished = True
        self.hit_button.disabled = True
        self.stand_button.disabled = True
        
        if win_amount != 0:
            update_wallet(str(self.ctx.author.id), win_amount)

        embed = self.create_embed(result_text)
        await interaction.response.edit_message(embed=embed, view=self)

    def create_embed(self, status="Playing..."):
        p_score = self.calculate_score(self.player_hand)
        d_score = self.calculate_score(self.dealer_hand) if self.finished else "?"
        
        embed = discord.Embed(title="🃏 Blackjack Table", color=0x2b2d31)
        embed.add_field(name=f"Your Hand ({p_score})", value=self.format_hand(self.player_hand), inline=True)
        embed.add_field(name=f"Dealer Hand ({d_score})", value=self.format_hand(self.dealer_hand, not self.finished), inline=True)
        embed.set_footer(text=f"Bet: 🪙 {self.bet} | Status: {status}")
        return embed

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player_hand.append(self.draw_card())
        if self.calculate_score(self.player_hand) >= 21:
            await self.check_winner(interaction, stand=True)
        else:
            await interaction.response.edit_message(embed=self.create_embed())

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.check_winner(interaction, stand=True)
class BattleRequestView(discord.ui.View):

    def __init__(self, ctx, opponent):

        super().__init__(timeout=60)

        self.ctx = ctx
        self.opponent = opponent

    @discord.ui.button(
        label="Accept",
        style=discord.ButtonStyle.green
    )
    async def accept(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.opponent.id:

            return await interaction.response.send_message(
                "❌ This battle request isn't for you.",
                ephemeral=True
            )

        challenger_pets = pets_col.find_one({
            "_id": str(self.ctx.author.id)
        })["pets"]

        opponent_pets = pets_col.find_one({
            "_id": str(self.opponent.id)
        })["pets"]

        battle_id = f"{self.ctx.author.id}-{self.opponent.id}"

        active_battles[battle_id] = {
            "challenger": self.ctx.author,
            "opponent": self.opponent,
            "challenger_pet": None,
            "opponent_pet": None
        }

        view = PetBattleSelectView(
            self.ctx,
            self.opponent,
            challenger_pets,
            opponent_pets,
            battle_id
        )

        embed = discord.Embed(
            title="🐾 Choose Your Battle Pets",
            description=(
                f"{self.ctx.author.mention} and "
                f"{self.opponent.mention}\n\n"
                f"Both players must choose a pet."
            ),
            color=0x3498db
        )

        await interaction.response.edit_message(
            embed=embed,
            view=view
        )

    @discord.ui.button(
        label="Decline",
        style=discord.ButtonStyle.red
    )
    async def decline(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if interaction.user.id != self.opponent.id:

            return await interaction.response.send_message(
                "❌ This battle request isn't for you.",
                ephemeral=True
            )

        await interaction.response.edit_message(
            content="❌ Battle declined.",
            embed=None,
            view=None
        )
class PetBattleSelect(discord.ui.Select):

    def __init__(self, user, pets, battle_id, role):

        self.user = user
        self.pets = pets
        self.battle_id = battle_id
        self.role = role

        options = []

        for pet in pets:

            pet_type = pet["type"]

            emoji = PET_SHOP[pet_type]["emoji"]

            options.append(
                discord.SelectOption(
                    label=pet_type.capitalize(),
                    emoji=emoji,
                    value=pet_type
                )
            )

        super().__init__(
            placeholder="Choose your pet...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction):

        if interaction.user.id != self.user.id:

            return await interaction.response.send_message(
                "❌ This selection isn't for you.",
                ephemeral=True
            )

        selected_pet = next(
            p for p in self.pets
            if p["type"] == self.values[0]
        )

        battle = active_battles[self.battle_id]

        battle[self.role] = selected_pet

        await interaction.response.send_message(
            f"✅ Selected {selected_pet['type'].capitalize()}!",
            ephemeral=True
        )

        if (
            battle["challenger_pet"]
            and battle["opponent_pet"]
        ):

            await start_pet_battle(
                interaction.channel,
                self.battle_id
            )
class PetBattleSelectView(discord.ui.View):

    def __init__(
        self,
        ctx,
        opponent,
        challenger_pets,
        opponent_pets,
        battle_id
    ):

        super().__init__(timeout=60)

        self.add_item(
            PetBattleSelect(
                ctx.author,
                challenger_pets,
                battle_id,
                "challenger_pet"
            )
        )

        self.add_item(
            PetBattleSelect(
                opponent,
                opponent_pets,
                battle_id,
                "opponent_pet"
            )
        )

class ClanClient:
    async def get_top_clans(self):
        url = f"{self.api_base}/api/leaderboard/clan"
        headers = {
            "ApiKey": self.api_key,
            "accept": "application/json"
        }

        async with self.session.get(url, headers=headers) as r:
            return await r.json()

    def __init__(self, api_base: str, api_key: str):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.session: aiohttp.ClientSession | None = None

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT_SECONDS))

    async def close(self) -> None:
        if self.session:
            await self.session.close()

    async def get_clan_data(self, clan_name: str) -> dict[str, Any]:
        encoded_name = quote(clan_name.strip(), safe="")
        url = f"{self.api_base}/api/clan/{encoded_name}"
        payload = await self._request_json_with_retry("GET", url)

        clan_data = self._normalize_clan_payload(payload)
        members = self._extract_members_list(clan_data)
        clan_data["members"] = members
        return clan_data

    def _normalize_clan_payload(self, payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            if any(k in payload for k in ("members", "clanUsers", "users", "players")):
                return payload
            nested = payload.get("data")
            if isinstance(nested, dict):
                return nested
            nested = payload.get("clan")
            if isinstance(nested, dict):
                return nested

        raise RuntimeError(f"Unexpected Kirka API format. Raw type: {type(payload).__name__}")

    def _extract_members_list(self, clan_data: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("members", "clanUsers", "users", "players"):
            members = clan_data.get(key)
            if isinstance(members, list):
                return members
        raise RuntimeError("Unexpected Kirka response: members list not found")


    async def get_clan_leaderboard(self) -> Any:
        url = f"{self.api_base}/api/leaderboard/clan"
        return await self._request_json_with_retry("GET", url)

    async def get_inventory_user(self, player_id: str, is_short_id: bool = True) -> Any:
        url = f"{self.api_base}/api/inventory/user"
        payload = {"id": player_id, "isShortId": is_short_id}
        return await self._request_json_with_retry("POST", url, json_payload=payload)

    async def _request_json_with_retry(self, method: str, url: str, json_payload: dict[str, Any] | None = None) -> Any:
        if not self.session:
            raise RuntimeError("HTTP session not initialized")

        headers = {
            "accept": "application/json",
            "ApiKey": self.api_key,
        }

        last_error: Exception | None = None
        for attempt in range(1, HTTP_MAX_RETRIES + 1):
            try:
                async with self.session.request(method.upper(), url, headers=headers, json=json_payload) as response:
                    body = await response.text()
                    if response.status == 429:
                        retry_after = float(response.headers.get("Retry-After", "0") or 0)
                        delay = retry_after if retry_after > 0 else HTTP_RETRY_BASE_DELAY * attempt
                        await asyncio.sleep(delay)
                        continue
                    if response.status >= 500:
                        raise RuntimeError(f"Kirka temporary error {response.status}: {body[:200]}")
                    if response.status in {401, 403}:
                        raise RuntimeError("Kirka API rejected the key (401/403). Check KIRKA_API_KEY in .env")
                    if response.status < 200 or response.status >= 300:
                        raise RuntimeError(f"Kirka API error {response.status}: {body[:300]}")
                    return await response.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, RuntimeError) as exc:
                last_error = exc
                if attempt < HTTP_MAX_RETRIES:
                    await asyncio.sleep(HTTP_RETRY_BASE_DELAY * attempt)

        raise RuntimeError(f"Failed request after {HTTP_MAX_RETRIES} attempts: {last_error}")


def load_snapshot(path) -> dict | None:
    snap_id = str(path)
    doc = snaps_col.find_one({"_id": snap_id})
    return doc["data"] if doc else None

def save_snapshot(path, data: dict) -> None:
    snap_id = str(path)
    snaps_col.update_one({"_id": snap_id}, {"$set": {"data": data}}, upsert=True)


def is_admin(ctx: commands.Context) -> bool:
    if isinstance(ctx.author, discord.Member):
        return bool(ctx.author.guild_permissions.administrator)
    return False


def extract_member_map(clan_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in clan_data.get("members", []):
        if not isinstance(item, dict):
            continue
        user = item.get("user") if isinstance(item.get("user"), dict) else item

        user_id = str(user.get("id") or item.get("id") or user.get("userId") or "").strip()
        if not user_id:
            continue

        score_raw = item.get("allScores", item.get("scores", item.get("xp", 0)))
        try:
            all_scores = int(score_raw or 0)
        except (TypeError, ValueError):
            all_scores = 0

        result[user_id] = {
            "id": user_id,
            "name": str(user.get("name") or item.get("name") or "Unknown"),
            "shortId": str(user.get("shortId") or item.get("shortId") or "-"),
            "role": str(item.get("role") or "UNKNOWN"),
            "allScores": all_scores,
        }
    return result


def build_weekly_rows(monday: dict[str, dict[str, Any]], sunday: dict[str, dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    all_ids = set(monday.keys()) | set(sunday.keys())

    for user_id in all_ids:
        mon = monday.get(user_id)
        sun = sunday.get(user_id)

        if mon and sun:
            weekly_xp = sun["allScores"] - mon["allScores"]
            if weekly_xp < 0:
                status = "REVIEW"
            elif weekly_xp >= WEEKLY_XP_REQUIREMENT:
                status = "OK"
            else:
                status = "MISSING"
            rows.append([sun["name"], sun["shortId"], sun["role"], weekly_xp, status])
        elif sun and not mon:
            rows.append([sun["name"], sun["shortId"], sun["role"], 0, "JOINED"])
        elif mon and not sun:
            rows.append([mon["name"], mon["shortId"], mon["role"], 0, "LEFT"])

    rows.sort(key=lambda row: (row[4] not in {"OK", "MISSING", "REVIEW"}, -row[3], row[0]))
    return rows


def format_table(rows: list[list[Any]], headers: list[str]) -> str:
    if tabulate:
        return tabulate(rows, headers=headers, tablefmt="github")

    widths = [len(h) for h in headers]
    for row in rows:
        for i, col in enumerate(row):
            widths[i] = max(widths[i], len(str(col)))

    def fmt_line(values: list[Any]) -> str:
        cells = [str(v).ljust(widths[i]) for i, v in enumerate(values)]
        return "| " + " | ".join(cells) + " |"

    sep = "| " + " | ".join("-" * w for w in widths) + " |"
    lines = [fmt_line(headers), sep]
    lines.extend(fmt_line(row) for row in rows)
    return "\n".join(lines)


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
            help_command=None
        )
        self.clan_client = clan_client

    async def setup_hook(self) -> None:
        await self.clan_client.start()
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        spawn_global_drop.start()
        logger.info(f"✅ ¡Bot conectado y listo como {self.user}!")
        await self.change_presence(
            status=discord.Status.online, 
            activity=discord.Game(name="Kirka.io 🏆")
        )

    async def close(self) -> None:
        await self.clan_client.close()
        await super().close()


class TopClansPagination(discord.ui.View):
    def __init__(self, clans: list, page: int, per_page: int):
        super().__init__(timeout=120)
        self.clans = clans
        self.page = page
        self.per_page = per_page
        self.max_page = max(0, (len(clans) - 1) // per_page)
        self.update_buttons()

    def update_buttons(self):
        self.btn_prev.disabled = self.page == 0
        self.btn_next.disabled = self.page >= self.max_page

    async def update_message(self, interaction: discord.Interaction):
        image_path = generate_top_clans_image(self.clans, self.page, self.per_page)
        file = discord.File(image_path, filename="top_clans.png")
        self.update_buttons()
        await interaction.response.edit_message(attachments=[file], view=self)

    @discord.ui.button(label="⬅️ Previous", style=discord.ButtonStyle.gray)
    async def btn_prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = max(0, self.page - 1)
        await self.update_message(interaction)

    @discord.ui.button(label="Next ➡️", style=discord.ButtonStyle.gray)
    async def btn_next(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page = min(self.max_page, self.page + 1)
        await self.update_message(interaction)


def generate_top_clans_image(clans: list[dict], page: int = 0, per_page: int = 10):
    width, height = 1000, 850 
    img = Image.new("RGB", (width, height), (30, 31, 34)) 
    draw = ImageDraw.Draw(img)

    try:
        font_normal = ImageFont.truetype("arial.ttf", 32)
        font_bold = ImageFont.truetype("arialbd.ttf", 32)
        font_title = ImageFont.truetype("arialbd.ttf", 52)
        font_header = ImageFont.truetype("arialbd.ttf", 34)
    except:
        font_normal = ImageFont.load_default()
        font_bold = font_normal
        font_title = font_normal
        font_header = font_normal

    start = page * per_page
    end = start + per_page
    sliced = clans[start:end]

    draw.text((40, 40), "🏆 GLOBAL LEADERBOARD", fill=(255, 255, 255), font=font_title)
    
    page_text = f"PAGE {page+1} / {max(1, (len(clans)//per_page)+1)}"
    draw.text((width - 250, 55), page_text, fill=(150, 150, 150), font=font_bold)

    y_offset = 140
    cols = [40, 150, 540, 800] 
    headers = ["RANK", "CLAN", "EXPERIENCE", "USERS"]
    
    draw.rectangle([(20, y_offset), (width - 20, y_offset + 70)], fill=(43, 45, 49))
    
    for x, text in zip(cols, headers):
        draw.text((x, y_offset + 15), text, fill=(88, 101, 242), font=font_header)

    y_offset += 100 
    rank = start + 1

    for c in sliced:
        name = c.get("name", "Unknown")
        scores = c.get("scores", 0)
        members = c.get("membersCount", 0)

        is_my_clan = name.lower() == "usasone!"
        
        if is_my_clan:
            text_color = (255, 215, 0) 
            draw.rectangle([(20, y_offset - 10), (width - 20, y_offset + 55)], fill=(49, 51, 56), outline=(255, 215, 0), width=3)
            current_font = font_bold
        else:
            text_color = (220, 221, 222) 
            current_font = font_normal

        draw.text((cols[0], y_offset), f"#{rank}", fill=text_color, font=current_font)
        draw.text((cols[1], y_offset), name, fill=text_color, font=current_font)
        draw.text((cols[2], y_offset), f"{scores:,} XP", fill=text_color, font=current_font)
        draw.text((cols[3], y_offset), f"{members}", fill=text_color, font=current_font)

        y_offset += 65 
        rank += 1

    draw.rectangle([(20, height - 20), (width - 20, height - 15)], fill=(88, 101, 242))

    path = f"top_clans_page_{page}.png"
    img.save(path)
    return path



clan_client = ClanClient(api_base=KIRKA_API_BASE, api_key=KIRKA_API_KEY)
bot = WeeklyXPBot(clan_client=clan_client)






@bot.event
async def on_member_join(member: discord.Member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
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
        color=0x2b2d31
    )
    
    embed.set_image(url="https://i.ibb.co/d4r7Z6f8/248-AB2-AF-21-F0-4384-A53-D-404328353301.png")
    
    await channel.send(content=f"Welcome {member.mention}!", embed=embed)

@bot.event
async def on_member_remove(member: discord.Member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    if not channel:
        return

    embed = discord.Embed(
        title="Goodbye! 👋",
        description=f"**{member.name}** has left the server. We will miss you!",
        color=0xff2a2a
    )
    await channel.send(embed=embed)

def load_warns() -> dict:
    doc = warns_col.find_one({"_id": "all_warns"})
    return doc["data"] if doc else {}

def save_warns(data: dict):
    warns_col.update_one({"_id": "all_warns"}, {"$set": {"data": data}}, upsert=True)

def parse_duration(duration_str: str):
    from datetime import timedelta
    try:
        if duration_str.endswith("m"):
            return timedelta(minutes=int(duration_str[:-1]))
        elif duration_str.endswith("h"):
            return timedelta(hours=int(duration_str[:-1]))
        elif duration_str.endswith("d"):
            return timedelta(days=int(duration_str[:-1]))
        else:
            return timedelta(minutes=int(duration_str))
    except ValueError:
        return None


@bot.hybrid_command(name="ban", description="Ban a member from the server (Admin only)")
@app_commands.describe(member="The member to ban", reason="The reason for the ban")
@app_commands.default_permissions(administrator=True)
async def ban(ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    try:
        await member.send(f"🔨 You have been **banned** from **{ctx.guild.name}**.\n**Reason:** {reason}")
    except discord.Forbidden:
        pass
        
    try:
        await member.ban(reason=reason)
        await ctx.send(f"🔨 **{member.name}** has been permanently banned. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to ban user: {e}", ephemeral=True)

@bot.hybrid_command(name="unban", description="Unban a user by their Discord ID (Admin only)")
@app_commands.describe(user_id="The unique ID of the user to unban")
@app_commands.default_permissions(administrator=True)
async def unban(ctx: commands.Context, user_id: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        user = await bot.fetch_user(int(user_id))
        await ctx.guild.unban(user)
        await ctx.send(f"✅ Successfully unbanned **{user.name}** from the server.")
    except Exception as e:
        await ctx.send(f"❌ Failed to unban user. Make sure the ID is correct: {e}", ephemeral=True)

@bot.hybrid_command(name="kick", description="Kick a member from the server (Admin only)")
@app_commands.describe(member="The member to kick", reason="The reason for the kick")
@app_commands.default_permissions(administrator=True)
async def kick(ctx: commands.Context, member: discord.Member, reason: str = "No reason provided"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    try:
        await member.send(f"👢 You have been **kicked** from **{ctx.guild.name}**.\n**Reason:** {reason}")
    except discord.Forbidden:
        pass
        
    try:
        await member.kick(reason=reason)
        await ctx.send(f"👢 **{member.name}** has been kicked from the server. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to kick user: {e}", ephemeral=True)

@bot.hybrid_command(name="timeout", description="Timeout/Mute a member temporarily (Admin only)")
@app_commands.describe(member="The member", duration="Duration (e.g. 10m, 2h, 1d)", reason="Reason for timeout")
@app_commands.default_permissions(administrator=True)
async def timeout(ctx: commands.Context, member: discord.Member, duration: str, reason: str = "No reason provided"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    time_delta = parse_duration(duration)
    if not time_delta:
        return await ctx.send("❌ Invalid duration format! Use formats like `10m` (minutes), `2h` (hours), or `1d` (days).", ephemeral=True)
    
    try:
        await member.send(f"🔇 You have been **timed out** in **{ctx.guild.name}** for `{duration}`.\n**Reason:** {reason}")
    except discord.Forbidden:
        pass
    
    try:
        await member.timeout(time_delta, reason=reason)
        await ctx.send(f"🔇 **{member.name}** has been timed out for `{duration}`. Reason: {reason}")
    except Exception as e:
        await ctx.send(f"❌ Failed to apply timeout: {e}", ephemeral=True)

@bot.hybrid_command(name="untimeout", description="Remove timeout from a member (Admin only)")
@app_commands.describe(member="The member to untimeout")
@app_commands.default_permissions(administrator=True)
async def untimeout(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.timeout(None)
        await ctx.send(f"🔊 Timeout removed. **{member.name}** can now talk again.")
    except Exception as e:
        await ctx.send(f"❌ Failed to remove timeout: {e}", ephemeral=True)


@bot.hybrid_command(name="purge", description="Purge a specified amount of messages (Admin only)")
@app_commands.describe(amount="Amount of messages to delete")
@app_commands.default_permissions(administrator=True)
async def purge(ctx: commands.Context, amount: int):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    if amount <= 0:
        return await ctx.send("Please specify a number greater than 0.", ephemeral=True)
    
    await ctx.defer(ephemeral=True)
    try:
        deleted = await ctx.channel.purge(limit=amount)
        await ctx.send(f"🧹 Successfully deleted **{len(deleted)}** messages.", ephemeral=True)
    except Exception as e:
        await ctx.send(f"❌ Failed to purge messages: {e}", ephemeral=True)

@bot.hybrid_command(name="lock", description="Lock a text channel (Admin only)")
@app_commands.describe(channel="The channel to lock (Defaults to current)")
@app_commands.default_permissions(administrator=True)
async def lock(ctx: commands.Context, channel: discord.TextChannel = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    target_channel = channel or ctx.channel
    try:
        await target_channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"🔒 **{target_channel.mention}** has been locked down.")
    except Exception as e:
        await ctx.send(f"❌ Failed to lock channel: {e}", ephemeral=True)

@bot.hybrid_command(name="unlock", description="Unlock a previously locked channel (Admin only)")
@app_commands.describe(channel="The channel to unlock (Defaults to current)")
@app_commands.default_permissions(administrator=True)
async def unlock(ctx: commands.Context, channel: discord.TextChannel = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    target_channel = channel or ctx.channel
    try:
        await target_channel.set_permissions(ctx.guild.default_role, send_messages=None)
        await ctx.send(f"🔓 **{target_channel.mention}** is now unlocked.")
    except Exception as e:
        await ctx.send(f"❌ Failed to unlock channel: {e}", ephemeral=True)

@bot.hybrid_command(name="slowmode", description="Set slowmode delay for a channel (Admin only)")
@app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)", channel="The channel")
@app_commands.default_permissions(administrator=True)
async def slowmode(ctx: commands.Context, seconds: int, channel: discord.TextChannel = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    target_channel = channel or ctx.channel
    try:
        await target_channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send(f"⏱️ Slowmode has been disabled in {target_channel.mention}.")
        else:
            await ctx.send(f"⏱️ Slowmode set to **{seconds}** seconds in {target_channel.mention}.")
    except Exception as e:
        await ctx.send(f"❌ Failed to set slowmode: {e}", ephemeral=True)


@bot.hybrid_command(name="warn", description="Issue a warning to a member (Admin only)")
@app_commands.describe(member="The member to warn", reason="The reason for the warning")
@app_commands.default_permissions(administrator=True)
async def warn(ctx: commands.Context, member: discord.Member, reason: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    
    if user_id not in warns_data:
        warns_data[user_id] = []
        
    warn_id = str(len(warns_data[user_id]) + 1)
    new_warn = {
        "id": warn_id,
        "reason": reason,
        "moderator": ctx.author.name,
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    }
    warns_data[user_id].append(new_warn)
    save_warns(warns_data)
    
    try:
        await member.send(f"⚠️ You received a **warning** in **{ctx.guild.name}**.\n**Reason:** {reason}\n*You now have {len(warns_data[user_id])} warnings.*")
    except discord.Forbidden:
        pass
    
    embed = discord.Embed(
        title="⚠️ Member Warned",
        description=f"**User:** {member.mention}\n**Reason:** {reason}\n**Total Warns:** {len(warns_data[user_id])}",
        color=0xffaa00
    )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="warns", description="Check a member's warning history (Admin only)")
@app_commands.describe(member="The member to check")
@app_commands.default_permissions(administrator=True)
async def check_warns(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    user_warns = warns_data.get(user_id, [])
    
    if not user_warns:
        return await ctx.send(f"✅ **{member.name}** has a clean record (0 warnings).")
        
    embed = discord.Embed(title=f"⚠️ Warning Record: {member.name}", color=0xffaa00)
    for w in user_warns:
        embed.add_field(
            name=f"ID: {w['id']} | {w['date']}",
            value=f"**Reason:** {w['reason']}\n**Staff:** {w['moderator']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="delwarn", description="Delete a specific warning from a member (Admin only)")
@app_commands.describe(member="The member", warn_id="The ID of the warning to remove")
@app_commands.default_permissions(administrator=True)
async def delwarn(ctx: commands.Context, member: discord.Member, warn_id: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    user_warns = warns_data.get(user_id, [])
    
    updated_warns = [w for w in user_warns if w['id'] != warn_id]
    
    if len(updated_warns) == len(user_warns):
        return await ctx.send("❌ Warning ID not found for this user.", ephemeral=True)
    
    for idx, w in enumerate(updated_warns):
        w['id'] = str(idx + 1)
        
    warns_data[user_id] = updated_warns
    save_warns(warns_data)
    await ctx.send(f"✅ Successfully removed warning ID `{warn_id}` from **{member.name}**.")

@bot.hybrid_command(name="clearwarns", description="Clear all warnings from a member (Admin only)")
@app_commands.describe(member="The member to clear")
@app_commands.default_permissions(administrator=True)
async def clearwarns(ctx: commands.Context, member: discord.Member):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    
    warns_data = load_warns()
    user_id = str(member.id)
    if user_id in warns_data:
        del warns_data[user_id]
        save_warns(warns_data)
    await ctx.send(f"✅ Cleared all warnings for **{member.name}**.")


@bot.hybrid_command(name="setnick", description="Quickly change a member's nickname (Admin only)")
@app_commands.describe(member="The member", nickname="New nickname (Leave empty to reset)")
@app_commands.default_permissions(administrator=True)
async def setnick(ctx: commands.Context, member: discord.Member, nickname: str = None):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.edit(nick=nickname)
        await ctx.send(f"✅ Changed nickname for **{member.name}** to `{nickname or member.name}`.")
    except Exception as e:
        await ctx.send(f"❌ Failed to change nickname: {e}", ephemeral=True)

@bot.hybrid_command(name="role_add", description="Assign a role to a member (Admin only)")
@app_commands.describe(member="The member", role="The role to assign")
@app_commands.default_permissions(administrator=True)
async def role_add(ctx: commands.Context, member: discord.Member, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.add_roles(role)
        await ctx.send(f"✅ Assigned the role **{role.name}** to **{member.name}**.")
    except Exception as e:
        await ctx.send(f"❌ Failed to add role: {e}", ephemeral=True)

@bot.hybrid_command(name="role_remove", description="Remove a role from a member (Admin only)")
@app_commands.describe(member="The member", role="The role to remove")
@app_commands.default_permissions(administrator=True)
async def role_remove(ctx: commands.Context, member: discord.Member, role: discord.Role):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)
    try:
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed the role **{role.name}** from **{member.name}**.")
    except Exception as e:
        await ctx.send(f"❌ Failed to remove role: {e}", ephemeral=True)
@bot.hybrid_command(
    name="battle",
    description="Battle your pet against another member's pet!"
)
async def battle(ctx: commands.Context, opponent: discord.Member):

    if opponent.bot:

        return await ctx.send(
            "❌ You can't battle a bot!",
            ephemeral=True
        )

    if opponent.id == ctx.author.id:

        return await ctx.send(
            "❌ You can't battle yourself!",
            ephemeral=True
        )

    user_id = str(ctx.author.id)

    opp_id = str(opponent.id)

    user_pets_data = pets_col.find_one(
        {"_id": user_id}
    )

    opp_pets_data = pets_col.find_one(
        {"_id": opp_id}
    )

    if not user_pets_data or not user_pets_data.get("pets"):

        return await ctx.send(
            "❌ You don't have any pets!"
        )

    if not opp_pets_data or not opp_pets_data.get("pets"):

        return await ctx.send(
            f"❌ {opponent.display_name} has no pets!"
        )

    embed = discord.Embed(
        title="⚔️ Pet Battle Challenge",
        description=(
            f"{ctx.author.mention} has challenged "
            f"{opponent.mention} to a pet battle!\n\n"
            f"Waiting for response..."
        ),
        color=0xe74c3c
    )

    view = BattleRequestView(
        ctx,
        opponent
    )

    await ctx.send(
        content=opponent.mention,
        embed=embed,
        view=view
    )
async def start_pet_battle(channel, battle_id):

    battle = active_battles[battle_id]

    challenger = battle["challenger"]
    opponent = battle["opponent"]

    user_id = str(challenger.id)
    opp_id = str(opponent.id)

    user_pet = battle["challenger_pet"]
    opp_pet = battle["opponent_pet"]

    battle_msg = await channel.send(
        f"⚔️ **BATTLE INITIATED!**\n"
        f"{challenger.mention} "
        f"({user_pet['type']}) "
        f"VS "
        f"{opponent.mention} "
        f"({opp_pet['type']})"
    )

    animation_frames = [

        f"⚔️ **FIGHTING!**\n"
        f"{user_pet['type'].capitalize()} lunges forward...\n"
        f"`[▬▬▬       ] 30%`",

        f"⚔️ **FIGHTING!**\n"
        f"{opp_pet['type'].capitalize()} strikes back hard!\n"
        f"`[▬▬▬▬▬▬    ] 60%`",

        f"⚔️ **CLASHING!**\n"
        f"Dust is everywhere...\n"
        f"`[▬▬▬▬▬▬▬▬▬ ] 99%`"
    ]

    for frame in animation_frames:

        await asyncio.sleep(1.2)

        await battle_msg.edit(content=frame)

    user_power = (
        user_pet['hp']
        + user_pet['damage']
        + random.randint(1, 50)
    )

    opp_power = (
        opp_pet['hp']
        + opp_pet['damage']
        + random.randint(1, 50)
    )

    bet_amount = random.randint(15000, 30000)

    if user_power >= opp_power:

        winner = challenger
        loser = opponent

        winner_id = user_id
        loser_id = opp_id

        winner_pet = user_pet
        loser_pet = opp_pet

    else:

        winner = opponent
        loser = challenger

        winner_id = opp_id
        loser_id = user_id

        winner_pet = opp_pet
        loser_pet = user_pet

    eco_col.update_one(
        {"_id": winner_id},
        {"$inc": {"wallet": bet_amount}},
        upsert=True
    )

    eco_col.update_one(
        {"_id": loser_id},
        {"$inc": {"wallet": -bet_amount}},
        upsert=True
    )

    winner_data = get_user_data(winner_id)

    loser_data = get_user_data(loser_id)

    embed = discord.Embed(
        title="🏆 BATTLE RESULTS",
        description="The dust settles, and a victor emerges...",
        color=0xffd700
    )

    embed.add_field(
        name=f"👑 WINNER: {winner.display_name}",
        value=(
            f"**Pet:** {winner_pet['type'].capitalize()}\n"
            f"**Earned:** 🪙 {bet_amount:,}\n"
            f"**New Balance:** 🪙 {winner_data['wallet']:,}"
        ),
        inline=False
    )

    embed.add_field(
        name=f"💀 LOSER: {loser.display_name}",
        value=(
            f"**Pet:** {loser_pet['type'].capitalize()}\n"
            f"**Lost:** 🪙 {bet_amount:,}\n"
            f"**New Balance:** 🪙 {loser_data['wallet']:,}"
        ),
        inline=False
    )

    if loser_data['wallet'] < 0:

        embed.set_footer(
            text="📉 Bankrupt! The loser is now in crippling debt."
        )

    await asyncio.sleep(1)

    await battle_msg.edit(
        content="🛑 **The battle is over!**",
        embed=embed
    )

    del active_battles[battle_id]


@bot.hybrid_command(name="userinfo", description="Display detailed information about a member")
@app_commands.describe(member="The member to view (Defaults to yourself)")
async def userinfo(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    roles = [role.mention for role in target.roles[1:]] 
    
    embed = discord.Embed(title=f"👤 User Profile: {target.name}", color=0x2b2d31)
    embed.set_thumbnail(url=target.display_avatar.url)
    
    embed.add_field(name="User ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Server Nickname", value=target.nick or "None", inline=True)
    embed.add_field(name="Account Created", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Joined Server", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "Unknown", inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "No roles assigned", inline=False)
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="serverinfo", description="Display general information about this server")
async def serverinfo(ctx: commands.Context):
    guild = ctx.guild
    embed = discord.Embed(title=f"🏰 Server Information: {guild.name}", color=0x2b2d31)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
        
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
    embed.add_field(name="Total Members", value=f"👥 {guild.member_count}", inline=True)
    embed.add_field(name="Channels", value=f"📝 {len(guild.text_channels)} Text | 🔊 {len(guild.voice_channels)} Voice", inline=True)
    embed.add_field(name="Created Date", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
    embed.add_field(name="Boost Status", value=f"✨ Tier {guild.premium_tier} ({guild.premium_subscription_count} boosts)", inline=True)
    embed.set_footer(text=f"Server ID: {guild.id}")
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="avatar", description="Get a member's avatar in high resolution")
@app_commands.describe(member="The member (Defaults to yourself)")
async def avatar(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author
    embed = discord.Embed(title=f"🖼️ Avatar of {target.name}", color=0x2b2d31)
    embed.set_image(url=target.display_avatar.url)
    await ctx.send(embed=embed)

@bot.hybrid_command(name="balance", aliases=["bal"], description="Check your economy profile")
async def balance(ctx: commands.Context, member: discord.Member = None):
    target = member or ctx.author

    wallet = get_wallet(str(target.id))
    bank = get_bank(str(target.id))

    total = wallet + bank

    embed = discord.Embed(
        title=f"💳 {target.display_name}'s Economy",
        color=0x2b2d31
    )

    embed.add_field(
        name="💵 Wallet",
        value=f"🪙 {wallet:,}",
        inline=True
    )

    embed.add_field(
        name="🏦 Bank",
        value=f"🪙 {bank:,}",
        inline=True
    )

    embed.add_field(
        name="📈 Total Net Worth",
        value=f"🪙 {total:,}",
        inline=False
    )

    embed.set_thumbnail(url=target.display_avatar.url)

    await ctx.send(embed=embed)

@bot.hybrid_command(name="deposit", aliases=["dep"], description="Deposit coins into your bank")
@app_commands.describe(amount="The amount to deposit ('all', 'half', or a number)")
async def deposit(ctx: commands.Context, amount: str):
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
        color=0x00ff00
    )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="withdraw", aliases=["with"], description="Withdraw coins from your bank")
@app_commands.describe(amount="The amount to withdraw ('all', 'half', or a number)")
async def withdraw(ctx: commands.Context, amount: str):
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
        color=0x3498db
    )
    await ctx.send(embed=embed)

@bot.hybrid_command(name="daily", description="Claim your daily free coins")
async def daily(ctx: commands.Context):
    user_id = str(ctx.author.id)
    user_data = get_user_data(user_id)

    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    last_daily = user_data.get("last_daily")
    already_claimed = False

    if isinstance(last_daily, str):
        already_claimed = (last_daily == today_str)

    elif isinstance(last_daily, (int, float)):
        last_date = datetime.fromtimestamp(last_daily, tz=timezone.utc)
        already_claimed = (last_date.strftime("%Y-%m-%d") == today_str)

    elif hasattr(last_daily, "strftime"):
        already_claimed = (last_daily.strftime("%Y-%m-%d") == today_str)

    if already_claimed:
        next_midnight = datetime(
            now.year,
            now.month,
            now.day,
            tzinfo=timezone.utc
        ) + timedelta(days=1)

        next_claim_timestamp = int(next_midnight.timestamp())

        return await ctx.send(
            f"❌ You already claimed your daily! Wait until <t:{next_claim_timestamp}:R>.",
            ephemeral=True
        )

    amount = 1000

    eco_col.update_one(
        {"_id": user_id},
        {
            "$inc": {"wallet": amount},
            "$set": {"last_daily": today_str}
        },
        upsert=True
    )

    await ctx.send(
        f"📆 You claimed your daily reward of 🪙 {amount:,} coins!"
    )
@bot.hybrid_command(name="weekly", description="Claim your massive weekly reward")
async def weekly(ctx: commands.Context):
    user_id = str(ctx.author.id)
    user_data = get_user_data(user_id)

    now = datetime.now(timezone.utc)
    week_str = f"{now.year}-W{now.isocalendar()[1]}"

    last_weekly = user_data.get("last_weekly")
    already_claimed_weekly = False

    if isinstance(last_weekly, str):
        already_claimed_weekly = (last_weekly == week_str)

    elif isinstance(last_weekly, (int, float)):
        last_date = datetime.fromtimestamp(last_weekly, tz=timezone.utc)
        saved_week = f"{last_date.year}-W{last_date.isocalendar()[1]}"
        already_claimed_weekly = (saved_week == week_str)

    elif hasattr(last_weekly, "isocalendar"):
        saved_week = f"{last_weekly.year}-W{last_weekly.isocalendar()[1]}"
        already_claimed_weekly = (saved_week == week_str)

    if already_claimed_weekly:
        days_until_next_monday = 7 - now.weekday()

        next_monday = datetime(
            now.year,
            now.month,
            now.day,
            tzinfo=timezone.utc
        ) + timedelta(days=days_until_next_monday)

        next_claim_timestamp = int(next_monday.timestamp())

        return await ctx.send(
            f"❌ You already claimed your weekly! Wait until <t:{next_claim_timestamp}:R>.",
            ephemeral=True
        )

    amount = 25000

    eco_col.update_one(
        {"_id": user_id},
        {
            "$inc": {"wallet": amount},
            "$set": {"last_weekly": week_str}
        },
        upsert=True
    )

    await ctx.send(
        f"✨ You claimed your weekly reward of 🪙 {amount:,} coins!"
    )

@bot.hybrid_command(name="pay", description="Send coins to another member")
@app_commands.describe(member="The member to send coins to", amount="Amount ('all', 'half', or number)")
async def pay(ctx: commands.Context, member: discord.Member, amount: str):
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
        color=0x00ff99
    )
    await ctx.send(embed=embed)



@bot.hybrid_command(name="leaderboard", aliases=["lb", "top"], description="Shows the richest members")
async def leaderboard(ctx: commands.Context):

    users = list(eco_col.find())

    users.sort(
        key=lambda u: u.get("wallet", 0) + u.get("bank", 0),
        reverse=True
    )

    users = users[:10]

    embed = discord.Embed(
        title="🏆 Global Economy Leaderboard",
        color=0xffd700
    )

    description = ""

    for index, user_data in enumerate(users, start=1):

        user_id = int(user_data["_id"])

        total = user_data.get("wallet", 0) + user_data.get("bank", 0)

        member = ctx.guild.get_member(user_id)

        if member:
            name = member.display_name
        else:
            name = f"Unknown User ({user_id})"

        medals = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }

        medal = medals.get(index, f"`#{index}`")

        description += (
            f"{medal} **{name}** — 🪙 {total:,}\n"
        )

    embed.description = description

    await ctx.send(embed=embed)

@bot.hybrid_command(name="top_clans", description="View the top clans leaderboard")
async def top_clans(ctx: commands.Context):
    await ctx.defer()
    try:
        data = await bot.clan_client.get_top_clans()
        clans = data.get("results", [])
        if not clans:
            return await ctx.send("❌ No clan data found.")

        view = TopClansPagination(clans, 0, 10)
        image_path = generate_top_clans_image(clans, 0, 10)
        file = discord.File(image_path, filename="top_clans.png")
        await ctx.send(file=file, view=view)
    except Exception as e:
        await ctx.send(f"⚠️ Error: {e}")


@bot.hybrid_command(name="flip", description="Flip a coin: Heads or Tails")
async def flip(ctx: commands.Context):
    msg = await ctx.send("Flipping the coin...")
    
    # 50/50 real usando secrets, sin semillas manuales que rompan la probabilidad
    result = secrets.choice(["Heads", "Tails"])
    
    await asyncio.sleep(1)
    
    await msg.edit(content=f"Flipping the coin... 🪙 **{result}**")

@bot.hybrid_command(name="roulette", description="Bet on the casino roulette wheel")
@app_commands.describe(
    bet_amount="Amount ('all', 'half', or number)", 
    bet_on="What are you betting on?", 
    number="Number to bet on (if you chose specific_number)"
)
@app_commands.choices(bet_on=[
    app_commands.Choice(name="🔴 Red (x2)", value="red"),
    app_commands.Choice(name="⚫ Black (x2)", value="black"),
    app_commands.Choice(name="🔢 Even (x2)", value="even"),
    app_commands.Choice(name="🔢 Odd (x2)", value="odd"),
    app_commands.Choice(name="🎯 Specific Number (x36)", value="specific_number")
])
async def roulette(ctx: commands.Context, bet_amount: str, bet_on: str, number: int = None):
    user_id = str(ctx.author.id)
    user_data = get_user_data(user_id)
    
    bet = parse_economy_amount(bet_amount, user_data["wallet"])

    # Validation checks
    if bet <= 0:
        return await ctx.send("❌ Invalid bet. Please specify a positive number, 'all', or 'half'.", ephemeral=True)
    if user_data["wallet"] < bet:
        return await ctx.send(f"❌ You don't have enough coins. Your balance is 🪙 {user_data['wallet']:,}.", ephemeral=True)
    
    if bet_on == "specific_number":
        if number is None or not (0 <= number <= 36):
            return await ctx.send("❌ Please provide a valid number between 0 and 36.", ephemeral=True)

    # --- 1. Start Visual Animation ---
    spin_msg = await ctx.send("🎰 **Throwing the ball...** 🔄\n`[          ] 0%`")

    # Safe frames to avoid Discord rate limits
    animation_frames = [
        "🎰 **Spinning...** 🔴 14\n`[▬▬        ] 25%`",
        "🎰 **Spinning...** ⬛ 22\n`[▬▬▬▬▬     ] 50%`",
        "🎰 **Slowing down...** 🟢 0\n`[▬▬▬▬▬▬▬   ] 75%`",
        "🎰 **Almost there...** 🔴 7\n`[▬▬▬▬▬▬▬▬▬ ] 99%`"
    ]

    for frame in animation_frames:
        await asyncio.sleep(0.8)  # Pause to simulate the spin
        await spin_msg.edit(content=frame)

    # --- 2. Game Logic ---
    winning_number = random.randint(0, 36)
    is_red = winning_number in ROULETTE_RED
    is_black = winning_number != 0 and not is_red

    # Determine visual text and emoji for final result
    color_emoji = "🟩" if winning_number == 0 else ("🟥" if is_red else "⬛")
    color_text = "Green" if winning_number == 0 else ("Red" if is_red else "Black")

    win = False
    multiplier = 0

    # Win conditions
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

    # Clean up what the user bet on for the display
    bet_target_display = bet_on.capitalize()
    if bet_on == "specific_number":
        bet_target_display = f"Number {number}"

    # --- 3. Apply Results & Build The Detailed Embed ---
    embed = discord.Embed(
        title="🎰 Casino Roulette",
        color=0x00ff00 if win else 0xff0000
    )
    embed.set_author(name=f"{ctx.author.display_name}'s Spin", icon_url=ctx.author.display_avatar.url)

    # Add the detailed fields
    embed.add_field(
        name="📝 Bet Details", 
        value=f"**Amount:** 🪙 {bet:,}\n**Bet On:** {bet_target_display}", 
        inline=True
    )
    embed.add_field(
        name="🎯 The Spin", 
        value=f"**Landed On:**\n{color_emoji} **{color_text} {winning_number}**", 
        inline=True
    )

    if win:
        winnings = bet * multiplier
        profit = winnings - bet
        update_wallet(user_id, profit)
        
        embed.add_field(
            name="🎉 Outcome", 
            value=f"**WIN!** (x{multiplier} multiplier)\nYou won 🪙 **{winnings:,}**!", 
            inline=False
        )
    else:
        update_wallet(user_id, -bet)
        
        embed.add_field(
            name="💀 Outcome", 
            value=f"**LOSS!**\nYou lost 🪙 **{bet:,}**.", 
            inline=False
        )

    new_balance = get_wallet(user_id)
    embed.set_footer(text=f"New Wallet Balance: 🪙 {new_balance:,}")
    
    # --- 4. Final Output ---
    await asyncio.sleep(0.8)
    await spin_msg.edit(content="🛑 **The wheel stopped!**", embed=embed)
@bot.hybrid_command(name="sell", description="Sell an item from your inventory")
async def sell(ctx: commands.Context):

    user_id = str(ctx.author.id)

    user_data = get_user_data(user_id)

    inventory = user_data.get("inventory", [])

    if not inventory:

        return await ctx.send(
            "🎒 Your inventory is empty."
        )

    embed = discord.Embed(
        title="💰 Sell Item",
        description="Choose an item to sell.",
        color=0xe67e22
    )

    view = SellView(
        ctx,
        inventory
    )

    await ctx.send(
        embed=embed,
        view=view
    )
@bot.hybrid_command(name="claimdrop", description="Claim the active global drop")
async def claimdrop(ctx: commands.Context):

    global active_global_drop

    if not active_global_drop:

        return await ctx.send(
            "❌ No active global drop."
        )

    user_id = str(ctx.author.id)

    if active_global_drop["type"] == "coins":

        reward = active_global_drop["reward"]

        eco_col.update_one(
            {"_id": user_id},
            {
                "$inc": {"wallet": reward}
            },
            upsert=True
        )

        await ctx.send(
            f"🌠 {ctx.author.mention} claimed the drop and received 🪙 {reward:,}!"
        )

    else:

        item = active_global_drop["item"]

        eco_col.update_one(
            {"_id": user_id},
            {
                "$push": {
                    "inventory": item
                }
            },
            upsert=True
        )

        await ctx.send(
            f"🌠 {ctx.author.mention} claimed:\n\n"
            f"{item['name']} • {item['rarity'].capitalize()}!"
        )

    active_global_drop = None
@tasks.loop(minutes=300)
async def spawn_global_drop():

    global active_global_drop

    drop_type = random.choice([
        "coins",
        "coins",
        "coins",
        "item",
        "item"
    ])

    if drop_type == "coins":

        rewards = [
            5000,
            10000,
            15000,
            25000,
            50000
        ]

        reward = random.choice(rewards)

        active_global_drop = {
            "type": "coins",
            "reward": reward
        }

        embed = discord.Embed(
            title="🌠 GLOBAL DROP",
            description=(
                "A mysterious treasure appeared!\n\n"
                "Use `!claimdrop` first!"
            ),
            color=0xf1c40f
        )

        embed.add_field(
            name="💰 Coin Reward",
            value=f"🪙 {reward:,}"
        )

    else:

        rarity_roll = random.randint(1, 100)

        if rarity_roll <= 60:
            rarity = "common"

        elif rarity_roll <= 88:
            rarity = "rare"

        elif rarity_roll <= 98:
            rarity = "epic"

        else:
            rarity = "legendary"

        item_name, item_value = random.choice(
            ADVENTURE_LOOT[rarity]
        )

        active_global_drop = {
            "type": "item",
            "item": {
                "name": item_name,
                "value": item_value,
                "rarity": rarity
            }
        }

        rarity_colors = {
            "common": 0x95a5a6,
            "rare": 0x3498db,
            "epic": 0x9b59b6,
            "legendary": 0xf1c40f
        }

        embed = discord.Embed(
            title="🌠 GLOBAL ITEM DROP",
            description=(
                "A mysterious item appeared from the skies!\n\n"
                "Use `!claimdrop` first!"
            ),
            color=rarity_colors[rarity]
        )

        embed.add_field(
            name="🎁 Item",
            value=item_name
        )

        embed.add_field(
            name="✨ Rarity",
            value=rarity.capitalize()
        )

    channel_id = 1206197908399980575

    channel = bot.get_channel(channel_id)

    if channel:

        await channel.send(embed=embed)
@bot.hybrid_command(name="inventory",aliases=["inv"], description="View your inventory")
async def inventory(ctx: commands.Context):

    user_id = str(ctx.author.id)

    user_data = get_user_data(user_id)

    inventory = user_data.get("inventory", [])

    if not inventory:

        return await ctx.send(
            "🎒 Your inventory is empty."
        )

    rarity_emojis = {
        "common": "⚪",
        "rare": "🔵",
        "epic": "🟣",
        "legendary": "🟡"
    }

    embed = discord.Embed(
        title=f"🎒 {ctx.author.name}'s Inventory",
        color=0x2ecc71
    )

    total_value = 0

    text = ""

    for item in inventory[:25]:

        rarity = item["rarity"]

        emoji = rarity_emojis.get(rarity, "⚪")

        text += (
            f"{emoji} {item['name']} "
            f"• 🪙 {item['value']:,}\n"
        )

        total_value += item["value"]

    embed.description = text

    embed.add_field(
        name="💰 Total Inventory Value",
        value=f"🪙 {total_value:,}",
        inline=False
    )

    embed.set_footer(
        text=f"{len(inventory)} items stored"
    )

    await ctx.send(embed=embed)

@bot.hybrid_command(name="blackjack", description="Play a realistic hand of blackjack")
@app_commands.describe(bet_amount="Amount ('all', 'half', or number)")
async def blackjack(ctx: commands.Context, bet_amount: str):
    user_id = str(ctx.author.id)
    user_data = get_user_data(user_id)
    
    bet = parse_economy_amount(bet_amount, user_data["wallet"])

    if bet <= 0:
        return await ctx.send("❌ Invalid bet. Please specify a positive number, 'all', or 'half'.")
    if user_data["wallet"] < bet:
        return await ctx.send(f"❌ You don't have enough coins. Your balance is 🪙 {user_data['wallet']:,}.")
    
    # IMPORTANTE: Pasamos "bet" a la vista (View)
    view = BlackjackView(ctx, bet, user_id)
    await ctx.send(embed=view.create_embed(), view=view)
# --- WORK ---
@bot.hybrid_command(name="work", description="Work to earn coins")
async def work(ctx: commands.Context):
    user_id = str(ctx.author.id)
    user_data = get_user_data(user_id)
    
    cooldown = 2700 # 45 minutos
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
        "won a legendary rap battle against an AI"
    ]
    reason = random.choice(jobs)

    # Actualizamos DB
    eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_work": now}}, upsert=True)

    embed = discord.Embed(title="💼 Work Complete", description=f"You {reason} and earned 🪙 **{earnings:,}** coins.", color=0x00ff99)
    embed.set_footer(text="Come back in 45 minutes for another shift.")
    await ctx.send(embed=embed)


# --- CRIME ---
@bot.hybrid_command(name="crime", description="Commit a crime for big money, but risk getting caught!")
async def crime(ctx: commands.Context):
    user_id = str(ctx.author.id)
    user_data = get_user_data(user_id)
    wallet = user_data.get("wallet", 0)
    
    cooldown = 7200 # 2 horas
    last_crime = user_data.get("last_crime", 0)
    now = time.time()
    
    if now - last_crime < cooldown:
        time_left = int(cooldown - (now - last_crime))
        hours, minutes = divmod(time_left, 3600)
        return await ctx.send(f"⏳ The heat is too high! Lay low for {hours}h {minutes//60}m before committing another crime.", ephemeral=True)

    if wallet < 1000:
        return await ctx.send("❌ You need at least 🪙 1,000 in your wallet to commit a crime (to bribe the cops just in case).", ephemeral=True)

    success = random.choice([True, False])
    if success:
        earnings = random.randint(2000, 6500)
        eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": earnings}, "$set": {"last_crime": now}}, upsert=True)
        msg = random.choice(["robbed an underground casino", "hacked a billionaire's bank account", "stole a cybernetic sports car", "smuggled rare alien artifacts", "sold counterfeit Kirka skins on the black market"])
        embed = discord.Embed(title="🦹 Crime Successful", description=f"You {msg} and got away with 🪙 **{earnings:,}** coins!", color=0x2ecc71)
    else:
        fine = random.randint(1000, min(3500, wallet))
        eco_col.update_one({"_id": user_id}, {"$inc": {"wallet": -fine}, "$set": {"last_crime": now}}, upsert=True)
        msg = random.choice(["tripped over a trash can while running from the cops", "left your ID at the crime scene", "tried to hack a government server but forgot to turn on your VPN", "got caught by a cybernetic guard dog", "were betrayed by your getaway driver"])
        embed = discord.Embed(title="🚔 BUSTED!", description=f"You {msg}.\n\nYou were fined 🪙 **{fine:,}** coins.", color=0xe74c3c)

    await ctx.send(embed=embed)


# --- ROB ---

@bot.hybrid_command(name="adventures",aliases=["adv"], description="Send your pet on an adventure")
async def adventures(ctx: commands.Context):

    user_id = str(ctx.author.id)

    user_pets = pets_col.find_one({"_id": user_id})

    if not user_pets or not user_pets.get("pets"):

        return await ctx.send(
            "❌ You don't own any pets.",
            ephemeral=True
        )

    view = AdventureView(
        ctx,
        user_pets["pets"]
    )

    await ctx.send(
        "🌍 Choose a pet for the adventure:",
        view=view
    )
async def run_adventure(interaction, ctx, selected_pet):

    user_id = str(ctx.author.id)

    user_data = get_user_data(user_id)

    cooldown = 1800

    now = time.time()

    last_adventure = user_data.get("last_adventure", 0)

    if now - last_adventure < cooldown:

        remaining = int(cooldown - (now - last_adventure))

        minutes, seconds = divmod(remaining, 60)

        return await interaction.response.send_message(
            f"⏳ Your pets are resting. Try again in {minutes}m {seconds}s.",
            ephemeral=True
        )

    pet_type = selected_pet["type"]

    rarity = PET_RARITIES.get(pet_type, "basic")

    chances = {
        "basic": {
            "common": 80,
            "rare": 18,
            "epic": 2,
            "legendary": 0
        },

        "rare": {
            "common": 60,
            "rare": 30,
            "epic": 9,
            "legendary": 1
        },

        "epic": {
            "common": 40,
            "rare": 40,
            "epic": 17,
            "legendary": 3
        },

        "legendary": {
            "common": 20,
            "rare": 45,
            "epic": 25,
            "legendary": 10
        }
    }

    roll = random.randint(1, 100)

    cumulative = 0

    loot_rarity = "common"

    for r, chance in chances[rarity].items():

        cumulative += chance

        if roll <= cumulative:

            loot_rarity = r

            break

    loot = random.choice(
        ADVENTURE_LOOT[loot_rarity]
    )

    item_name, item_value = loot

    bonus_multiplier = {
        "basic": 1,
        "rare": 1.5,
        "epic": 2,
        "legendary": 4
    }

    final_value = int(
        item_value * bonus_multiplier[rarity]
    )

    eco_col.update_one(
        {"_id": user_id},
        {
            "$push": {
                "inventory": {
                    "name": item_name,
                    "value": final_value,
                    "rarity": loot_rarity
                }
},
            "$set": {"last_adventure": now}
        },
        upsert=True
    )

    event_text = random.choice(
        ADVENTURE_EVENTS[loot_rarity]
    )

    rarity_colors = {
        "common": 0x95a5a6,
        "rare": 0x3498db,
        "epic": 0x9b59b6,
        "legendary": 0xf1c40f
    }

    pet_emoji = PET_SHOP[pet_type]["emoji"]

    embed = discord.Embed(
        title="🌍 Pet Adventure",
        color=rarity_colors[loot_rarity]
    )

    embed.description = (
        f"{pet_emoji} Your **{pet_type}** {event_text}...\n\n"
        f"🎁 It discovered:\n"
        f"## {item_name}\n\n"
        f"💰 Sold for: 🪙 **{final_value:,}**"
    )

    embed.add_field(
        name="✨ Loot Rarity",
        value=loot_rarity.capitalize()
    )

    embed.add_field(
        name="🐾 Pet Rarity",
        value=rarity.capitalize()
    )

    embed.set_footer(
        text="Your pet can adventure again in 30 minutes."
    )

    await interaction.response.edit_message(
        content=None,
        embed=embed,
        view=None
    )

@bot.hybrid_command(name="rob", description="Attempt to rob another member")
async def rob(ctx: commands.Context, member: discord.Member):
    thief_id = str(ctx.author.id)
    target_id = str(member.id)
    user_data = get_user_data(thief_id)
    target_data = get_user_data(target_id)
    
    cooldown = 3600 # 1 hora
    last_rob = user_data.get("last_rob", 0)
    now = time.time()
    
    if now - last_rob < cooldown:
        time_left = int(cooldown - (now - last_rob))
        return await ctx.send(f"⏳ The cops are still looking for you! Lay low for {time_left//60}m.", ephemeral=True)

    if thief_id == target_id: return await ctx.send("❌ You cannot rob yourself.", ephemeral=True)
    if target_data.get("wallet", 0) < 300: return await ctx.send("❌ This user doesn't have enough wallet coins to rob.", ephemeral=True)

    success = random.choice([True, False])
    if success:
        stolen = random.randint(150, int(target_data.get("wallet", 0) * 0.35))
        eco_col.update_one({"_id": thief_id}, {"$inc": {"wallet": stolen}, "$set": {"last_rob": now}}, upsert=True)
        eco_col.update_one({"_id": target_id}, {"$inc": {"wallet": -stolen}}, upsert=True)
        msg = random.choice(["jumped through a window like a movie thief", "pickpocketed them during a crowded concert", "used fake security credentials to access their vault", "escaped through the rooftops after the robbery", "executed the perfect stealth mission", "used smoke grenades and escaped unseen", "hacked their crypto wallet remotely", "bribed the guards and walked out the front door", "used a teleporter to snatch their wallet", "distracted them with a hologram and grabbed the cash", "disguised yourself as a pizza delivery driver and looted the place"])
        embed = discord.Embed(title="🥷 Successful Robbery", description=f"You {msg}.\n\nYou stole 🪙 **{stolen:,}** from {member.mention}.", color=0x00ff00)
    else:
        fine = random.randint(150, 500)
        eco_col.update_one({"_id": thief_id}, {"$inc": {"wallet": -fine}, "$set": {"last_rob": now}}, upsert=True)
        msg = random.choice(["tripped the alarm system", "got caught by security cameras", "accidentally robbed a police officer", "left fingerprints everywhere", "triggered laser security defenses", "was betrayed by your getaway driver", "got tackled by bodyguards", "got outsmarted by a decoy safe", "was chased down by a cybernetic guard dog", "dropped the loot while trying to escape over a fence", "sneezed loudly while hiding in the closet"])
        embed = discord.Embed(title="🚨 Robbery Failed", description=f"You {msg}.\n\nYou paid a fine of 🪙 **{fine:,}**.", color=0xff0000)

    await ctx.send(embed=embed)



@bot.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="The question you want to ask")
async def eight_ball(ctx: commands.Context, question: str):
    responses = [
        "It is certain.", "It is decidedly so.", "Without a doubt.",
        "Yes - definitely.", "You may rely on it.", "As I see it, yes.",
        "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
        "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
        "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.",
        "Outlook not so good.", "Very doubtful."
    ]
    answer = random.choice(responses)
    
    embed = discord.Embed(color=0x2b2d31)
    
    embed.description = (
        f"🎱 **{ctx.author.display_name} asks:** {question}\n"
        f"💬 **Answer:** {answer}"
    )
    
    await ctx.send(embed=embed)

@bot.hybrid_command(name="item", description="Check skin details with strict search")
@app_commands.describe(name="Exact name of the skin (e.g., Nova)")
async def item_lookup(ctx: commands.Context, name: str):
    await ctx.defer()
    try:
        url = f"{KIRKA_API_BASE}/api/inventory/items"
        all_items = await bot.clan_client._request_json_with_retry("GET", url)

        found_item = next((i for i in all_items if i.get('name', '').lower() == name.lower()), None)

        if not found_item:
            suggestions = [i.get('name') for i in all_items if name.lower() in i.get('name', '').lower()]
            suggestions = suggestions[:10]

            error_msg = f"🔍 **Item not found:** `{name}`"
            if suggestions:
                list_str = "\n".join([f"• {s}" for s in suggestions])
                error_msg += f"\n\n**Did you mean one of these?**\n{list_str}"
            
            return await ctx.send(error_msg)

        item_name = found_item.get('name', 'Unknown')
        rarity = found_item.get('rarity', 'COMMON').upper()
        item_type = found_item.get('type', 'ITEM').replace('_', ' ')
        total_owned = found_item.get('totalOwned', 0)
        image_url = found_item.get('renderUrl')

        colors = {
            "COMMON": 0xaaaaaa, "RARE": 0x5555ff, "EPIC": 0xaa00aa,
            "LEGENDARY": 0xffaa00, "MYTHICAL": 0xff5555, "EXOTIC": 0x55ffff
        }
        
        embed = discord.Embed(
            title=f"✨ {item_name}",
            description=f"**Category:** {item_type}",
            color=colors.get(rarity, 0xffffff)
        )

        embed.add_field(name="Tier", value=f"**{rarity}**", inline=True)
        embed.add_field(name="Global Supply", value=f"**{total_owned:,}** owned", inline=True)
        
        if total_owned < 500:
            market_tip = "💎 **High Value:** Extremely rare supply."
        elif total_owned < 2000:
            market_tip = "⚖️ **Medium Value:** Limited edition."
        else:
            market_tip = "🛒 **Common Item:** High supply, lower price."
        
        embed.add_field(name="Market Status", value=market_tip, inline=False)

        if image_url:
            embed.set_image(url=image_url)

        embed.set_footer(text="Data provided by Kirka.io")
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"⚠️ An error occurred: {e}")


@bot.hybrid_command(name="register_monday", description="Save Monday baseline snapshot")
async def register_monday(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    await ctx.defer()
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": extract_member_map(clan_data),
        }
        save_snapshot(MONDAY_SNAPSHOT_PATH, snapshot)
        await ctx.send(
            f"Monday snapshot saved in `{MONDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members."
        )
    except Exception as exc:
        await ctx.send(f"Failed to save Monday snapshot: {exc}")


@bot.hybrid_command(name="register_sunday", description="Save Sunday snapshot")
async def register_sunday(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    await ctx.defer()
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        snapshot = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "clan_name": clan_data.get("name", CLAN_NAME),
            "members": extract_member_map(clan_data),
        }
        save_snapshot(SUNDAY_SNAPSHOT_PATH, snapshot)
        await ctx.send(
            f"Sunday snapshot saved in `{SUNDAY_SNAPSHOT_PATH}` with {len(snapshot['members'])} members."
        )
    except Exception as exc:
        await ctx.send(f"Failed to save Sunday snapshot: {exc}")


@bot.hybrid_command(name="weekly_lb", description="Build weekly leaderboard from Monday/Sunday JSON files")
async def weekly_lb(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    await ctx.defer()

    try:
        monday_data = load_snapshot(MONDAY_SNAPSHOT_PATH)
        sunday_data = load_snapshot(SUNDAY_SNAPSHOT_PATH)

        if not monday_data or not sunday_data:
            return await ctx.send(
                "Need both files first. Run `/register_monday` and `/register_sunday` before `/weekly_lb`."
            )

        rows = build_weekly_rows(monday_data["members"], sunday_data["members"])

        lines = []
        header = f"{'Player':<18} {'Short ID':<10} {'XP':>10}   Status"
        lines.append(header)
        lines.append("-" * 60)

        for row in rows:
            player = str(row[0])[:18]
            short_id = str(row[1])[:10]
            role = str(row[2]).upper()
            xp = f"{row[3]:,}"
            status = row[4]

            if role == "LEADER":
                player_color = "\u001b[33;1m"
            elif role == "OFFICER":
                player_color = "\u001b[34;1m"
            elif role == "NEWBIE":
                player_color = "\u001b[36m"
            else:
                player_color = "\u001b[37m"

            if status == "OK":
                status_color = "\u001b[32m"
            elif status == "MISSING":
                status_color = "\u001b[31m"
            elif status == "REVIEW":
                status_color = "\u001b[33m"
            elif status == "JOINED":
                status_color = "\u001b[36m"
            elif status == "LEFT":
                status_color = "\u001b[35m"
            else:
                status_color = "\u001b[0m"

            reset = "\u001b[0m"

            line = (
                f"{player_color}{player:<18}{reset} "
                f"{short_id:<10} "
                f"{xp:>10}   "
                f"{status_color}{status}{reset}"
            )
            lines.append(line)

        report_header = (
            f"Clan: {sunday_data['clan_name']}\n"
            f"Requirement: {WEEKLY_XP_REQUIREMENT:,} XP\n"
            f"Monday: {monday_data['timestamp_utc']}\n"
            f"Sunday: {sunday_data['timestamp_utc']}\n\n"
        )

        chunks = []
        current_chunk = report_header + "```ansi\n"

        for line in lines:
            test_chunk = current_chunk + line + "\n```"
            if len(test_chunk) > 1900:
                current_chunk += "```"
                chunks.append(current_chunk)
                current_chunk = "```ansi\n" + line + "\n"
            else:
                current_chunk += line + "\n"

        current_chunk += "```"
        chunks.append(current_chunk)

        for i, chunk in enumerate(chunks):
            if i == 0:
                await ctx.send(chunk)
            else:
                await ctx.channel.send(chunk)

    except Exception as exc:
        await ctx.send(f"Failed to build leaderboard: {exc}")


@bot.hybrid_command(name="set_xp", description="Set weekly XP requirement (admin only)")
@app_commands.describe(xp="New weekly XP requirement")
async def set_xp(ctx: commands.Context, xp: int) -> None:
    global WEEKLY_XP_REQUIREMENT
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    if xp <= 0:
        return await ctx.send("XP requirement must be greater than 0.", ephemeral=True)

    WEEKLY_XP_REQUIREMENT = xp
    await ctx.send(f"Weekly XP requirement updated to {WEEKLY_XP_REQUIREMENT:,} XP.")

@bot.hybrid_command(name="sayembed", description="Send a custom embed message (Admin only)")
@app_commands.describe(
    title="Title of the embed",
    description="The main text of the embed",
    color="Hex color code (e.g. 2b2d31 or ff0000)"
)
@app_commands.default_permissions(administrator=True) 
async def sayembed(ctx: commands.Context, title: str, description: str, color: str = "2b2d31"):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)


    try:
        color_int = int(color.lstrip('#'), 16)
    except ValueError:
        color_int = 0x2b2d31 

    embed = discord.Embed(title=title, description=description, color=color_int)

    if ctx.interaction is None: 
        try:
            await ctx.message.delete() 
        except discord.Forbidden:
            pass
        await ctx.send(embed=embed)
    else:
        await ctx.send("Embed sent!", ephemeral=True)
        await ctx.channel.send(embed=embed)


@bot.hybrid_command(name="clan_info", description="Detailed statistics for the current clan")
async def clan_info(ctx: commands.Context) -> None:
    await ctx.defer()
    try:
        clan_data = await bot.clan_client.get_clan_data(CLAN_NAME)
        members = clan_data.get("members", [])
        all_scores = int(clan_data.get("allScores", clan_data.get("scores", 0)) or 0)
        month_scores = int(clan_data.get("monthScores", 0) or 0)
        
        desc = str(clan_data.get("description") or "No description provided.")
        if len(desc) > 250:
            desc = desc[:247] + "..."

        embed = discord.Embed(
            title=f"🏰 Clan Profile: {clan_data.get('name', CLAN_NAME)}",
            description=f"```\n{desc}\n```",
            color=0xffd700,
            timestamp=datetime.now(timezone.utc),
        )
        
        embed.add_field(name="👥 Total Members", value=f"**{len(members)}** / 100", inline=True)
        embed.add_field(name="⭐ Lifetime XP", value=f"**{all_scores:,}**", inline=True)
        embed.add_field(name="📅 Monthly XP", value=f"**{month_scores:,}**", inline=True)
        embed.add_field(name="👑 Clan Leader", value="`AIMTOME`", inline=False)
        embed.set_footer(text="Kirka.io API System • Updated")
        
        embed.set_author(name="Clan Intelligence Module", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)
    except Exception as exc:
        await ctx.send(f"❌ Error fetching clan info: {exc}")


@bot.hybrid_command(name="say", description="Make the bot say something (Admin only)")
@app_commands.describe(message="The message you want the bot to repeat")
@app_commands.default_permissions(administrator=True) 
async def say(ctx: commands.Context, message: str):
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    if ctx.interaction is None: 
        try:
            await ctx.message.delete() 
        except discord.Forbidden:
            pass
        await ctx.send(message)
    else:
        await ctx.send("Message sent!", ephemeral=True)
        await ctx.channel.send(message)

class RPSView(discord.ui.View):
    def __init__(self, player: discord.Member):
        super().__init__(timeout=60)
        self.player = player

    async def handle_choice(self, interaction: discord.Interaction, user_choice: str):
        if interaction.user != self.player:
            return await interaction.response.send_message("❌ This is not your game! Start your own with /rps", ephemeral=True)
        
        choices = ["rock", "paper", "scissors"]
        bot_choice = random.choice(choices)
        emojis = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}

        if user_choice == bot_choice:
            result = "It's a tie! 🤝"
            color = 0xffff00
        elif (user_choice == "rock" and bot_choice == "scissors") or \
             (user_choice == "paper" and bot_choice == "rock") or \
             (user_choice == "scissors" and bot_choice == "paper"):
            result = "You win! 🎉"
            color = 0x00ff00
        else:
            result = "I win! 🤖"
            color = 0xff0000

        embed = discord.Embed(title="Rock, Paper, Scissors", color=color)
        embed.add_field(name="You chose", value=f"{emojis[user_choice]} **{user_choice.capitalize()}**", inline=True)
        embed.add_field(name="I chose", value=f"{emojis[bot_choice]} **{bot_choice.capitalize()}**", inline=True)
        embed.add_field(name="Result", value=f"**{result}**", inline=False)
        
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.blurple)
    async def rock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.gray)
    async def paper_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.red)
    async def scissors_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_choice(interaction, "scissors")

@bot.hybrid_command(name="rps", description="Play Rock, Paper, Scissors against the bot")
async def rps(ctx: commands.Context):
    embed = discord.Embed(
        title="Rock, Paper, Scissors", 
        description="Choose your weapon below! 👇", 
        color=0x2b2d31
    )
    view = RPSView(ctx.author)
    await ctx.send(embed=embed, view=view)

@bot.hybrid_command(name="help", description="Show all available commands")
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="🏆 Kirka.io Bot | Command List",
        description="Here is a list of all available commands to manage the server, the clan, and your wallet! 🎮",
        color=0x2b2d31 
    )

    public_cmds = (
        "**`/userinfo`** - View a member's profile.\n"
        "**`/serverinfo`** - View server details.\n"
        "**`/avatar`** - Get high-res avatar.\n"
        "**`/top_clans`** - View the global Kirka.io clan leaderboard.\n"
        "**`/clan_info`** - View detailed stats for our clan.\n"
        "**`/item [name]`** - Check a skin's rarity and market value.\n"
        "**`/8ball` / `/flip` / `/rps`** - Fun minigames."
    )
    embed.add_field(name="🌍 Public Commands", value=public_cmds, inline=False)

    eco_cmds = (
        "**`/balance`** - Check your wallet and bank.\n"
        "**`/deposit` / `/withdraw`** - Manage your money.\n"
        "**`/work` / `/crime`** - Earn (or risk) coins.\n"
        "**`/daily` / `/weekly`** - Claim free rewards.\n"
        "**`/pay` / `/rob`** - Give to or steal from others.\n"
        "**`/shop` / `/pets` / `/battle`** - Buy and fight battle pets.\n"
        "**`/leaderboard`** - See the richest server members."
    )
    embed.add_field(name="💰 Economy & Casino", value=eco_cmds, inline=False)

    admin_cmds = (
        "**`/register_monday` / `/register_sunday`** - Manage snapshots.\n"
        "**`/weekly_lb` / `/set_xp` / `/delete_snaps`** - Leaderboard config.\n"
        "**`/ban` / `/kick` / `/timeout`** - Moderation tools.\n"
        "**`/warn` / `/warns` / `/delwarn`** - Warning system.\n"
        "**`/purge` / `/lock` / `/slowmode`** - Channel management.\n"
        "**`/role_add` / `/setnick` / `/sayembed`** - Utility tools."
    )
    embed.add_field(name="🛡️ Admin Commands", value=admin_cmds, inline=False)

    embed.set_footer(
        text="🐛 Found a bug or have an issue? Contact: @clxzon_", 
        icon_url=ctx.author.display_avatar.url
    )

    await ctx.send(embed=embed)

@bot.hybrid_command(name="shop",aliases=["buy"], description="View and buy animals for battle")
@app_commands.describe(
    action="Choose 'view' to see the shop or 'buy' to purchase",
    pet_name="Name of the pet to buy"
)
async def shop(ctx: commands.Context, action: str = "view", pet_name: str = None):

    user_id = str(ctx.author.id)

    if action.lower() == "view":

        embed = discord.Embed(
            title="🏪 Pet Shop",
            description="Welcome to the battle pet shop!",
            color=0x3498db
        )

        for name, stats in PET_SHOP.items():

            embed.add_field(
                name=f"{stats['emoji']} {name.capitalize()} - 🪙 {stats['price']:,}",
                value=f"❤️ HP: {stats['hp']} | ⚔️ Damage: {stats['damage']}",
                inline=False
            )

        return await ctx.send(embed=embed)

    elif action.lower() == "buy":

        if not pet_name:
            return await ctx.send("❌ Please specify a pet name.")

        pet_key = pet_name.lower()

        if pet_key not in PET_SHOP:
            return await ctx.send("❌ That pet does not exist.")

        pet_data = PET_SHOP[pet_key]

        balance = get_wallet(user_id)

        if balance < pet_data["price"]:
            return await ctx.send(
                f"❌ You need 🪙 {pet_data['price']:,} coins."
            )

        pet_instance = {
            "pet_id": str(uuid.uuid4()),
            "type": pet_key,
            "hp": pet_data["hp"],
            "damage": pet_data["damage"]
        }

        pets_col.update_one(
            {"_id": user_id},
            {
                "$push": {
                    "pets": pet_instance
                }
            },
            upsert=True
        )

        update_wallet(user_id, -pet_data["price"])

        embed = discord.Embed(
            title="🎉 Pet Purchased",
            description=(
                f"You bought a "
                f"{pet_data['emoji']} "
                f"**{pet_key.capitalize()}**!"
            ),
            color=0x00ff00
        )

        await ctx.send(embed=embed)


async def run_battle_logic(interaction: discord.Interaction, p1: discord.Member, p2: discord.Member, p1_pet_id: str, p2_pet_id: str):
    p1_data = pets_col.find_one({"_id": str(p1.id)})
    p2_data = pets_col.find_one({"_id": str(p2.id)})

    pet1 = next((p for p in p1_data['pets'] if p.get('pet_id') == p1_pet_id or p.get('id') == p1_pet_id), None)
    pet2 = next((p for p in p2_data['pets'] if p.get('pet_id') == p2_pet_id or p.get('id') == p2_pet_id), None)

    if not pet1 or not pet2:
        return await interaction.message.edit(content="Error loading pets.", view=None)

    hp1, dmg1 = pet1['hp'], pet1['damage']
    hp2, dmg2 = pet2['hp'], pet2['damage']

    hit_phrases = ["slashes", "bites", "strikes", "blasts", "smashes", "claws", "tackles"]

    log = []
    turn = 1
    
    while hp1 > 0 and hp2 > 0 and turn <= 10:
        hit1 = random.randint(int(dmg1*0.8), int(dmg1*1.2))
        hp2 -= hit1
        phrase1 = random.choice(hit_phrases)
        log.append(f"💥 {p1.display_name}'s {pet1['type']} {phrase1} for {hit1} damage!")
        if hp2 <= 0: break

        hit2 = random.randint(int(dmg2*0.8), int(dmg2*1.2))
        hp1 -= hit2
        phrase2 = random.choice(hit_phrases)
        log.append(f"💥 {p2.display_name}'s {pet2['type']} {phrase2} for {hit2} damage!")
        turn += 1

    winner = None
    loser = None

    if hp1 > hp2:
        winner = p1
        loser = p2
    elif hp2 > hp1:
        winner = p2
        loser = p1

    embed = discord.Embed(title="⚔️ Battle Result", description="\n".join(log), color=discord.Color.gold())
    
    if winner and loser:
        loser_wallet = get_wallet(str(loser.id))
        base_reward = random.randint(100, 300)
        
        # Ensure we don't take more coins than the loser actually has
        actual_reward = min(base_reward, loser_wallet)
        
        if actual_reward > 0:
            update_wallet(str(winner.id), actual_reward)
            update_wallet(str(loser.id), -actual_reward)
            embed.add_field(name="🏆 Winner", value=f"{winner.mention} won and looted 🪙 {actual_reward} coins from {loser.mention}!")
        else:
            embed.add_field(name="🏆 Winner", value=f"{winner.mention} won, but {loser.mention} had 0 coins to steal!")
    else:
        embed.add_field(name="🤝 Draw", value="The battle ended in a tie!")

    await interaction.message.edit(content="🏁 The battle has ended!", embed=embed, view=None)

class PetSelectView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member, p1_pets: list, p2_pets: list):
        super().__init__(timeout=120)
        self.p1 = p1
        self.p2 = p2
        self.p1_choice = None
        self.p2_choice = None

        opts1 = [discord.SelectOption(label=f"{p['type'].capitalize()} (HP:{p['hp']} DMG:{p['damage']})", value=p.get('pet_id') or p.get('id')) for p in p1_pets[:25]]
        self.select1 = discord.ui.Select(placeholder=f"Player 1: {p1.display_name}, choose your pet", options=opts1, custom_id="select_p1")
        self.select1.callback = self.p1_callback
        self.add_item(self.select1)

        opts2 = [discord.SelectOption(label=f"{p['type'].capitalize()} (HP:{p['hp']} DMG:{p['damage']})", value=p.get('pet_id') or p.get('id')) for p in p2_pets[:25]]
        self.select2 = discord.ui.Select(placeholder=f"Player 2: {p2.display_name}, choose your pet", options=opts2, custom_id="select_p2")
        self.select2.callback = self.p2_callback
        self.add_item(self.select2)

    async def p1_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.p1.id:
            return await interaction.response.send_message("This select menu is not for you.", ephemeral=True)
        
        self.p1_choice = self.select1.values[0]
        self.select1.disabled = True
        
        if self.p1_choice and self.p2_choice:
            await interaction.response.edit_message(content="Both pets selected. Battling...", view=self)
            await run_battle_logic(interaction, self.p1, self.p2, self.p1_choice, self.p2_choice)
        else:
            await interaction.response.edit_message(content="Waiting for the opponent to select...", view=self)

    async def p2_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.p2.id:
            return await interaction.response.send_message("This select menu is not for you.", ephemeral=True)
        
        self.p2_choice = self.select2.values[0]
        self.select2.disabled = True
        
        if self.p1_choice and self.p2_choice:
            await interaction.response.edit_message(content="Both pets selected. Battling...", view=self)
            await run_battle_logic(interaction, self.p1, self.p2, self.p1_choice, self.p2_choice)
        else:
            await interaction.response.edit_message(content="Waiting for the opponent to select...", view=self)

class BattleAcceptView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=60)
        self.p1 = p1
        self.p2 = p2

    @discord.ui.button(label="Accept Battle", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.p2.id:
            return await interaction.response.send_message("Only the challenged player can accept.", ephemeral=True)
        
        p1_data = pets_col.find_one({"_id": str(self.p1.id)})
        p2_data = pets_col.find_one({"_id": str(self.p2.id)})

        view = PetSelectView(self.p1, self.p2, p1_data['pets'], p2_data['pets'])
        await interaction.response.edit_message(content="Battle accepted! Both players, select your pets below.", embed=None, view=view)



@bot.hybrid_command(name="pets", description="View your pets")
async def pets(ctx: commands.Context):

    data = pets_col.find_one({"_id": str(ctx.author.id)})

    if not data or not data.get("pets"):
        return await ctx.send("❌ You don't own any pets.")

    embed = discord.Embed(
        title=f"🐾 {ctx.author.display_name}'s Pets",
        color=0x3498db
    )

    for pet in data["pets"]:

        embed.add_field(
            name=f"🐾 {pet['type'].capitalize()}",
            value=(
                f"❤️ HP: {pet['hp']}\n"
                f"⚔️ Damage: {pet['damage']}"
            ),
            inline=False
        )

    await ctx.send(embed=embed)


@bot.hybrid_command(name="delete_snaps", description="Delete Monday and Sunday snapshots")
async def delete_snaps(ctx: commands.Context) -> None:
    if not is_admin(ctx):
        return await ctx.send("Admin only command.", ephemeral=True)

    try:
        snaps_col.delete_many({})
        await ctx.send("Deleted snapshots: Monday, Sunday")
    except Exception as exc:
        await ctx.send(f"Failed deleting snapshots: {exc}")


def validate_environment() -> None:
    if not DISCORD_TOKEN:
        raise RuntimeError("Missing required environment variable: DISCORD_TOKEN")
    if not KIRKA_API_KEY:
        raise RuntimeError("Missing required environment variable: KIRKA_API_KEY")


if __name__ == "__main__":
    validate_environment()
    keep_alive()
    bot.run(DISCORD_TOKEN)
