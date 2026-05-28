import os
import logging
from dotenv import load_dotenv

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
OWNER_IDS = {1436417791615045785}

ROULETTE_RED = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
VALID_BETS = {"red", "black", "even", "odd", "specific_number", "1st", "2nd", "3rd"}

CARD_EMOJIS = {
    '♠️': {'2': '🂢', '3': '🂣', '4': '🂤', '5': '🂥', '6': '🂦', '7': '🂧', '8': '🂨', '9': '🂩', '10': '🂪', 'J': '🂫', 'Q': '🂭', 'K': '🂮', 'A': '🂡'},
    '♥️': {'2': '🂲', '3': '🂳', '4': '🂴', '5': '🂵', '6': '🂶', '7': '🂷', '8': '🂸', '9': '🂹', '10': '🂺', 'J': '🂻', 'Q': '🂽', 'K': '🂾', 'A': '🂱'},
    '♦️': {'2': '🃂', '3': '🃃', '4': '🃄', '5': '🃅', '6': '🃆', '7': '🃇', '8': '🃈', '9': '🃉', '10': '🃊', 'J': '🃋', 'Q': '🃍', 'K': '🃎', 'A': '🃁'},
    '♣️': {'2': '🃒', '3': '🃓', '4': '🃔', '5': '🃕', '6': '🃖', '7': '🃗', '8': '🃘', '9': '🃙', '10': '🃚', 'J': '🃛', 'Q': '🃝', 'K': '🃞', 'A': '🃑'},
}
CARD_BACK = "🂠"

MONDAY_SNAPSHOT_PATH = "monday_snapshot"
SUNDAY_SNAPSHOT_PATH = "sunday_snapshot"

PET_LOOT_PROBABILITIES = {
    "slime":    {"common": 80, "rare": 15, "epic": 4,  "legendary": 1},
    "dog":      {"common": 75, "rare": 20, "epic": 4,  "legendary": 1},
    "cat":      {"common": 70, "rare": 23, "epic": 6,  "legendary": 1},
    "owl":      {"common": 65, "rare": 25, "epic": 8,  "legendary": 2},
    "fox":      {"common": 60, "rare": 30, "epic": 8,  "legendary": 2},
    "wolf":     {"common": 50, "rare": 35, "epic": 12, "legendary": 3},
    "tiger":    {"common": 45, "rare": 38, "epic": 14, "legendary": 3},
    "bear":     {"common": 40, "rare": 40, "epic": 15, "legendary": 5},
    "griffin":  {"common": 35, "rare": 42, "epic": 18, "legendary": 5},
    "dragon":   {"common": 25, "rare": 45, "epic": 22, "legendary": 8},
    "golem":    {"common": 20, "rare": 45, "epic": 25, "legendary": 10},
    "hydra":    {"common": 15, "rare": 45, "epic": 28, "legendary": 12},
    "pegasus":  {"common": 10, "rare": 40, "epic": 35, "legendary": 15},
    "phoenix":  {"common": 5,  "rare": 35, "epic": 40, "legendary": 20},
    "chimera":  {"common": 5,  "rare": 30, "epic": 40, "legendary": 25},
    "kraken":   {"common": 2,  "rare": 28, "epic": 40, "legendary": 30},
    "leviathan":{"common": 0,  "rare": 25, "epic": 40, "legendary": 35},
    "titan":    {"common": 0,  "rare": 15, "epic": 45, "legendary": 40},
    "bahamut":  {"common": 0,  "rare": 5,  "epic": 45, "legendary": 50},
}

PET_SHOP = {
    "slime":    {"price": 5_000,       "hp": 50,   "damage": 10,  "emoji": "🧪"},
    "dog":      {"price": 12_000,      "hp": 100,  "damage": 20,  "emoji": "🐕"},
    "cat":      {"price": 15_000,      "hp": 80,   "damage": 25,  "emoji": "🐈"},
    "owl":      {"price": 25_000,      "hp": 90,   "damage": 30,  "emoji": "🦉"},
    "fox":      {"price": 40_000,      "hp": 110,  "damage": 35,  "emoji": "🦊"},
    "wolf":     {"price": 85_000,      "hp": 150,  "damage": 40,  "emoji": "🐺"},
    "tiger":    {"price": 150_000,     "hp": 180,  "damage": 50,  "emoji": "🐯"},
    "bear":     {"price": 225_000,     "hp": 250,  "damage": 35,  "emoji": "🐻"},
    "griffin":  {"price": 500_000,     "hp": 300,  "damage": 60,  "emoji": "🦅"},
    "dragon":   {"price": 1_200_000,   "hp": 350,  "damage": 70,  "emoji": "🐉"},
    "golem":    {"price": 2_500_000,   "hp": 550,  "damage": 50,  "emoji": "🗿"},
    "hydra":    {"price": 5_000_000,   "hp": 450,  "damage": 90,  "emoji": "🐍"},
    "pegasus":  {"price": 8_500_000,   "hp": 400,  "damage": 85,  "emoji": "🦄"},
    "phoenix":  {"price": 15_000_000,  "hp": 400,  "damage": 120, "emoji": "🐦‍🔥"},
    "chimera":  {"price": 25_000_000,  "hp": 500,  "damage": 130, "emoji": "🦁"},
    "kraken":   {"price": 50_000_000,  "hp": 600,  "damage": 150, "emoji": "🦑"},
    "leviathan":{"price": 100_000_000, "hp": 800,  "damage": 180, "emoji": "🌊"},
    "titan":    {"price": 250_000_000, "hp": 1000, "damage": 200, "emoji": "👑"},
    "bahamut":  {"price": 500_000_000, "hp": 1500, "damage": 300, "emoji": "🌌"},
}

ROLE_SHOP = {
    "bronze":    {"price": 25_000,        "claim": 2_000,       "role_id": 1508820992749867212},
    "silver":    {"price": 75_000,        "claim": 5_000,       "role_id": 1508821178645610638},
    "gold":      {"price": 200_000,       "claim": 12_000,      "role_id": 1508821213634494574},
    "diamond":   {"price": 500_000,       "claim": 30_000,      "role_id": 1508822070191194354},
    "emerald":   {"price": 1_000_000,     "claim": 75_000,      "role_id": 1508821247583195217},
    "mythic":    {"price": 3_000_000,     "claim": 200_000,     "role_id": 1508821304399237301},
    "cosmic":    {"price": 10_000_000,    "claim": 650_000,     "role_id": 1508821333796978818},
    "eternal":   {"price": 25_000_000,    "claim": 1_500_000,   "role_id": 1508821363647840376},
    "titan":     {"price": 75_000_000,    "claim": 4_000_000,   "role_id": 1508821400457187429},
    "godlike":   {"price": 200_000_000,   "claim": 10_000_000,  "role_id": 1508821439665406072},
    "celestial": {"price": 500_000_000,   "claim": 25_000_000,  "role_id": 1508821730372878447},
    "ascended":  {"price": 1_000_000_000, "claim": 60_000_000,  "role_id": 1508821474855747614},
}

PET_RARITIES = {
    "slime": "basic", "dog": "basic", "cat": "basic", "owl": "basic", "fox": "basic",
    "wolf": "rare", "tiger": "rare", "bear": "rare", "griffin": "rare",
    "dragon": "epic", "golem": "epic", "hydra": "epic", "pegasus": "epic",
    "phoenix": "legendary", "chimera": "legendary", "kraken": "legendary",
    "leviathan": "legendary", "titan": "legendary", "bahamut": "legendary",
}

ADVENTURE_LOOT = {
    "common": [
        ("🪵 Stick", 15), ("🪨 Rock", 20), ("🔩 Screw", 25), ("🧻 Old Cloth", 18),
        ("🥫 Rusty Can", 22), ("🪢 Rope", 30), ("🧴 Plastic Bottle", 12),
        ("📎 Metal Scrap", 35), ("🪛 Broken Tool", 40), ("🪙 Small Coin", 50),
        ("🔋 Dead Battery", 28), ("📦 Wooden Crate", 45), ("🕯️ Candle", 20),
        ("🧱 Brick", 26), ("⚙️ Gear", 55), ("🪓 Rusty Axe", 60),
        ("🪤 Bear Trap", 75), ("📜 Torn Map", 80), ("🥄 Silver Spoon", 95),
        ("🧲 Magnet", 40), ("🧃 Juice Box", 15), ("🪙 Copper Coin", 35),
        ("🎣 Fishing Hook", 45), ("📻 Broken Radio", 90), ("⌚ Old Watch", 110),
        ("🧤 Leather Glove", 50), ("🪖 Cracked Helmet", 120), ("🗝️ Tiny Key", 140),
        ("🪞 Shattered Mirror", 75),
    ],
    "rare": [
        ("💍 Silver Ring", 500), ("🪙 Gold Coin", 750), ("💎 Sapphire", 1200),
        ("🔮 Magic Orb", 1500), ("📿 Ancient Necklace", 1800), ("⚔️ Knight Dagger", 2200),
        ("🏺 Ancient Vase", 2500), ("💠 Emerald", 3000), ("🧪 Rare Potion", 3500),
        ("📦 Treasure Chest", 4000), ("🗡️ Assassin Blade", 4200), ("🛡️ Golden Shield", 5000),
        ("💰 Hidden Stash", 5500), ("📜 Enchanted Scroll", 6000), ("🪬 Lucky Charm", 6500),
        ("🧿 Mystic Eye", 7000), ("🐚 Pearl Shell", 7500), ("💎 Ruby Crystal", 8000),
        ("⚡ Charged Core", 8500), ("🔑 Ancient Key", 9000),
    ],
    "epic": [
        ("👑 Royal Crown", 12000), ("💜 Amethyst Crystal", 15000), ("🐉 Dragon Scale", 18000),
        ("🔥 Phoenix Feather", 22000), ("⚡ Energy Core", 26000), ("🌌 Cosmic Fragment", 30000),
        ("💠 Mythic Gem", 35000), ("🗿 Titan Relic", 40000), ("🧬 Ancient DNA", 45000),
        ("🪐 Void Stone", 50000), ("📖 Forbidden Tome", 55000), ("🩸 Blood Ruby", 60000),
        ("🧊 Frozen Heart", 70000), ("☄️ Meteor Fragment", 80000), ("👁️ Cursed Eye", 90000),
    ],
    "legendary": [
        ("🌟 Celestial Artifact", 120000), ("👁️ Eye of Eternity", 150000),
        ("💫 Divine Crystal", 200000), ("🐲 Ancient Dragon Egg", 300000),
        ("🌌 Universe Shard", 500000), ("👑 Crown of Gods", 750000),
        ("⚔️ Blade of Chaos", 1000000), ("🪐 Core of the Void", 1500000),
        ("🌠 Fallen Star", 2000000), ("🧿 Orb of Infinity", 5000000),
    ],
}

ADVENTURE_EVENTS = {
    "common": [
        "searched through trash piles",
        "explored an abandoned alley",
        "wandered through old ruins",
        "dug near a broken wagon",
        "searched a forgotten campsite",
    ],
    "rare": [
        "explored an ancient cave",
        "snuck into a merchant caravan",
        "searched a hidden temple",
        "raided a bandit stash",
        "explored underground tunnels",
    ],
    "epic": [
        "explored volcanic ruins",
        "crossed forbidden lands",
        "searched a cursed fortress",
        "flew above ancient kingdoms",
        "ventured into magical forests",
    ],
    "legendary": [
        "vanished into the void itself",
        "crossed dimensions",
        "explored celestial ruins",
        "entered a forgotten realm",
        "traveled beyond mortal lands",
    ],
}
