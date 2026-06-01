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

MONDAY_SNAPSHOT_PATH = "xp_monday.json"
SUNDAY_SNAPSHOT_PATH = "sunday_snapshot"

PET_LOOT_PROBABILITIES = {
    # BASIC
    "slime":    {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "rabbit":   {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "mouse":    {"common": 92, "rare": 6, "epic": 1.5, "legendary": 0.5},
    "bat":      {"common": 88, "rare": 10, "epic": 1.5, "legendary": 0.5},
    "spider":   {"common": 86, "rare": 12, "epic": 1.5, "legendary": 0.5},
    "snake":    {"common": 85, "rare": 12, "epic": 2.5, "legendary": 0.5},
    "frog":     {"common": 90, "rare": 8, "epic": 1.5, "legendary": 0.5},
    "turtle":   {"common": 85, "rare": 12, "epic": 2.5, "legendary": 0.5},
    "parrot":   {"common": 84, "rare": 13, "epic": 2.5, "legendary": 0.5},
    "penguin":  {"common": 83, "rare": 14, "epic": 2.5, "legendary": 0.5},
    "raccoon":  {"common": 82, "rare": 15, "epic": 2.5, "legendary": 0.5},
    "dog":      {"common": 83, "rare": 14, "epic": 2.5, "legendary": 0.5},
    "cat":      {"common": 80, "rare": 17, "epic": 2.5, "legendary": 0.5},
    "owl":      {"common": 78, "rare": 18, "epic": 3.5, "legendary": 0.5},
    "fox":      {"common": 75, "rare": 20, "epic": 4.5, "legendary": 0.5},

    # RARE
    "wolf":     {"common": 70, "rare": 24, "epic": 5,   "legendary": 1},
    "tiger":    {"common": 65, "rare": 28, "epic": 6,   "legendary": 1},
    "bear":     {"common": 63, "rare": 30, "epic": 6,   "legendary": 1},
    "griffin":  {"common": 60, "rare": 31, "epic": 8,   "legendary": 1},

    # EPIC
    "dragon":   {"common": 55, "rare": 30, "epic": 13,  "legendary": 2},
    "golem":    {"common": 52, "rare": 32, "epic": 14,  "legendary": 2},
    "hydra":    {"common": 50, "rare": 32, "epic": 15,  "legendary": 3},
    "pegasus":  {"common": 45, "rare": 35, "epic": 16,  "legendary": 4},

    # LEGENDARY
    "phoenix":      {"common": 35, "rare": 35, "epic": 25, "legendary": 4.5, "godly": 0.5},
    "chimera":      {"common": 33, "rare": 34, "epic": 27, "legendary": 5.5, "godly": 0.5},
    "kraken":       {"common": 30, "rare": 33, "epic": 30, "legendary": 6,   "godly": 1},
    "leviathan":    {"common": 27, "rare": 30, "epic": 34, "legendary": 8,   "godly": 1},
    "titan":        {"common": 25, "rare": 25, "epic": 37, "legendary": 11,  "godly": 2},
    "bahamut":      {"common": 20, "rare": 20, "epic": 44, "legendary": 14,  "godly": 2},
    "cthulhu":      {"common": 15, "rare": 15, "epic": 47, "legendary": 20,  "godly": 3},
    "reaper":       {"common": 15, "rare": 15, "epic": 47, "legendary": 20,  "godly": 3},
    "archangel":    {"common": 10, "rare": 10, "epic": 50, "legendary": 26,  "godly": 4},
    "demon_lord":   {"common": 10, "rare": 10, "epic": 50, "legendary": 26,  "godly": 4},
    "void_dragon":  {"common": 5,  "rare": 5,  "epic": 45, "legendary": 40,  "godly": 5},
}

PET_SHOP = {
    "slime":    {"price": 5_000,       "hp": 50,   "damage": 10,  "emoji": "🧪"},
    "rabbit":   {"price": 3_500,       "hp": 40,   "damage": 8,   "emoji": "🐇"},
    "mouse":    {"price": 2_500,       "hp": 30,   "damage": 12,  "emoji": "🐭"},
    "bat":      {"price": 6_000,       "hp": 45,   "damage": 15,  "emoji": "🦇"},
    "spider":   {"price": 7_500,       "hp": 35,   "damage": 22,  "emoji": "🕷️"},
    "snake":    {"price": 9_000,       "hp": 60,   "damage": 18,  "emoji": "🐍"},
    "frog":     {"price": 4_500,       "hp": 55,   "damage": 10,  "emoji": "🐸"},
    "turtle":   {"price": 10_000,      "hp": 120,  "damage": 5,   "emoji": "🐢"},
    "parrot":   {"price": 8_000,       "hp": 50,   "damage": 20,  "emoji": "🦜"},
    "penguin":  {"price": 11_000,      "hp": 70,   "damage": 15,  "emoji": "🐧"},
    "raccoon":  {"price": 13_000,      "hp": 65,   "damage": 25,  "emoji": "🦝"},
    "dog":      {"price": 12_000,      "hp": 100,  "damage": 20,  "emoji": "🐕"},
    "cat":      {"price": 15_000,      "hp": 80,   "damage": 25,  "emoji": "🐈"},
    "owl":      {"price": 25_000,      "hp": 90,   "damage": 30,  "emoji": "🦉"},
    "fox":      {"price": 40_000,      "hp": 110,  "damage": 35,  "emoji": "🦊"},
    "lynx":     {"price": 35_000,      "hp": 100,  "damage": 45,  "emoji": "🐆"},
    "panther":  {"price": 45_000,      "hp": 120,  "damage": 55,  "emoji": "🐈‍⬛"},
    "rhino":    {"price": 65_000,      "hp": 200,  "damage": 30,  "emoji": "🦏"},
    "elephant": {"price": 80_000,      "hp": 250,  "damage": 35,  "emoji": "🐘"},
    "shark":    {"price": 55_000,      "hp": 130,  "damage": 60,  "emoji": "🦈"},
    "eagle":    {"price": 40_000,      "hp": 90,   "damage": 50,  "emoji": "🦅"},
    "cobra":    {"price": 30_000,      "hp": 80,   "damage": 65,  "emoji": "🐍"},
    "hyena":    {"price": 28_000,      "hp": 110,  "damage": 40,  "emoji": "🐕"},
    "cheetah":  {"price": 50_000,      "hp": 85,   "damage": 75,  "emoji": "🐆"},
    "gorilla":  {"price": 70_000,      "hp": 180,  "damage": 45,  "emoji": "🦍"},
    "wolf":     {"price": 85_000,      "hp": 150,  "damage": 40,  "emoji": "🐺"},
    "tiger":    {"price": 150_000,     "hp": 220,  "damage": 80,  "emoji": "🐯"},
    "bear":     {"price": 225_000,     "hp": 300,  "damage": 60,  "emoji": "🐻"},
    "griffin":  {"price": 500_000,     "hp": 450,  "damage": 120, "emoji": "🦅"},
    "unicorn":  {"price": 180_000,     "hp": 200,  "damage": 100, "emoji": "🦄"},
    "manticore":{"price": 250_000,     "hp": 280,  "damage": 110, "emoji": "🦁"},
    "basilisk": {"price": 350_000,     "hp": 350,  "damage": 130, "emoji": "🦎"},
    "cerberus": {"price": 500_000,     "hp": 500,  "damage": 140, "emoji": "🐕"},
    "thunderbird":{"price": 750_000,   "hp": 400,  "damage": 250, "emoji": "⚡"},
    "yeti":     {"price": 450_000,     "hp": 600,  "damage": 90,  "emoji": "🧊"},
    "wyvern":   {"price": 850_000,     "hp": 450,  "damage": 220, "emoji": "🐲"},
    "ent":      {"price": 400_000,     "hp": 800,  "damage": 70,  "emoji": "🌳"},
    "minotaur": {"price": 300_000,     "hp": 420,  "damage": 140, "emoji": "🐂"},
    "golem_core":{"price": 600_000,    "hp": 750,  "damage": 110, "emoji": "💠"},
    "dragon":   {"price": 1_200_000,   "hp": 1000, "damage": 300, "emoji": "🐉"},
    "golem":    {"price": 2_500_000,   "hp": 2000, "damage": 250, "emoji": "🗿"},
    "hydra":    {"price": 5_000_000,   "hp": 3000, "damage": 400, "emoji": "🐍"},
    "pegasus":  {"price": 8_500_000,   "hp": 4500, "damage": 550, "emoji": "🦄"},
    "phoenix":  {"price": 15_000_000,  "hp": 6000, "damage": 800, "emoji": "🐦‍🔥"},
    "chimera":  {"price": 25_000_000,  "hp": 8000, "damage": 1000, "emoji": "🦁"},
    "kraken":   {"price": 50_000_000,  "hp": 12000, "damage": 1500, "emoji": "🦑"},
    "leviathan":{"price": 100_000_000, "hp": 20000, "damage": 2500, "emoji": "🌊"},
    "titan":    {"price": 250_000_000, "hp": 40000, "damage": 4500, "emoji": "👑"},
    "bahamut":  {"price": 500_000_000, "hp": 75000, "damage": 8000, "emoji": "🌌"},
    "cthulhu":  {"price": 15_000_000_000, "hp": 250_000, "damage": 25_000, "emoji": "🐙"},
    "reaper":   {"price": 12_000_000_000, "hp": 180_000, "damage": 35_000, "emoji": "💀"},
    "archangel":{"price": 25_000_000_000, "hp": 500_000, "damage": 45_000, "emoji": "😇"},
    "demon_lord":{"price": 20_000_000_000, "hp": 400_000, "damage": 55_000, "emoji": "😈"},
    "void_dragon":{"price": 75_000_000_000, "hp": 1_500_000, "damage": 150_000, "emoji": "🌌"},
}

FOOD_ITEMS = {
    "basic": {"price": 25_000, "hunger": 20, "emoji": "🍖", "name": "Basic Food"},
    "premium": {"price": 100_000, "hunger": 50, "emoji": "🥩", "name": "Premium Food"},
    "enchanted": {"price": 500_000, "hunger": 100, "emoji": "🍱", "name": "Enchanted Food"},
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
    "secret":     {"price": 75_000_000,    "claim": 4_000_000,   "role_id": 1508821400457187429},
    "godlike":   {"price": 200_000_000,   "claim": 10_000_000,  "role_id": 1508821439665406072},
    "celestial": {"price": 500_000_000,   "claim": 25_000_000,  "role_id": 1508821730372878447},
    "ascended":  {"price": 1_000_000_000, "claim": 60_000_000,  "role_id": 1508821474855747614},
}

PET_RARITIES = {
    "slime": "basic", "rabbit": "basic", "mouse": "basic", "bat": "basic", "spider": "basic",
    "snake": "basic", "frog": "basic", "turtle": "basic", "parrot": "basic", "penguin": "basic",
    "raccoon": "basic", "dog": "basic", "cat": "basic", "owl": "basic", "fox": "basic",
    "wolf": "rare", "tiger": "rare", "bear": "rare", "griffin": "rare", "lynx": "rare",
    "panther": "rare", "rhino": "rare", "elephant": "rare", "shark": "rare", "eagle": "rare",
    "cobra": "rare", "hyena": "rare", "cheetah": "rare", "gorilla": "rare",
    "dragon": "epic", "golem": "epic", "hydra": "epic", "pegasus": "epic", "unicorn": "epic",
    "manticore": "epic", "basilisk": "epic", "cerberus": "epic", "thunderbird": "epic", "yeti": "epic",
    "wyvern": "epic", "ent": "epic", "minotaur": "epic", "golem_core": "epic",
    "phoenix": "legendary", "chimera": "legendary", "kraken": "legendary",
    "leviathan": "legendary", "titan": "legendary", "bahamut": "legendary",
    "cthulhu": "legendary", "reaper": "legendary", "archangel": "legendary",
    "demon_lord": "legendary", "void_dragon": "legendary",
}

ADVENTURE_LOOT = {
    "common": [
        ("🪵 Stick", 8), ("🪨 Rock", 10), ("🔩 Screw", 12), ("🧻 Old Cloth", 9),
        ("🥫 Rusty Can", 11), ("🪢 Rope", 15), ("🧴 Plastic Bottle", 6),
        ("📎 Metal Scrap", 18), ("🪛 Broken Tool", 20), ("🪙 Small Coin", 25),
        ("🔋 Dead Battery", 14), ("📦 Wooden Crate", 22), ("🕯️ Candle", 10),
        ("🧱 Brick", 13), ("⚙️ Gear", 28), ("🪓 Rusty Axe", 30),
        ("🪤 Bear Trap", 38), ("📜 Torn Map", 40), ("🥄 Silver Spoon", 48),
        ("🧲 Magnet", 20), ("🧃 Juice Box", 8), ("🪙 Copper Coin", 18),
        ("🎣 Fishing Hook", 22), ("📻 Broken Radio", 45), ("⌚ Old Watch", 55),
        ("🧤 Leather Glove", 25), ("🪖 Cracked Helmet", 60), ("🗝️ Tiny Key", 70),
        ("🪞 Shattered Mirror", 38), ("🥾 Old Boot", 5), ("🔩 Rusty Nail", 6),
        ("🥄 Plastic Spoon", 4), ("📦 Cardboard Box", 8), ("🍾 Empty Bottle", 3),
        ("🩹 Used Bandage", 10), ("🦴 Fish Bone", 7), ("📰 Soggy Newspaper", 9),
        ("🧦 Dirty Sock", 6), ("🖇️ Bent Paperclip", 4), ("💎 Glass Shard", 11),
        ("🔪 Dull Knife", 13), ("🧵 Frayed String", 7), ("🔮 Chipped Marble", 8),
        ("🔥 Burnt Match", 2), ("🪵 Twig", 3), ("🪨 Gravel", 4), ("🔩 Nut", 5),
    ],

    "rare": [
        ("💍 Silver Ring", 200), ("🪙 Gold Coin", 300), ("💎 Sapphire", 480),
        ("🔮 Magic Orb", 600), ("📿 Ancient Necklace", 720), ("⚔️ Knight Dagger", 880),
        ("🏺 Ancient Vase", 1000), ("💠 Emerald", 1200), ("🧪 Rare Potion", 1400),
        ("📦 Treasure Chest", 1600), ("🗡️ Assassin Blade", 1680), ("🛡️ Golden Shield", 2000),
        ("💰 Hidden Stash", 2200), ("📜 Enchanted Scroll", 2400), ("🪬 Lucky Charm", 2600),
        ("🧿 Mystic Eye", 2800), ("🐚 Pearl Shell", 3000), ("💎 Ruby Crystal", 3200),
        ("⚡ Charged Core", 3400), ("🔑 Ancient Key", 3600), ("🪨 Polished Pebble", 180),
        ("🪙 Silver Coin", 240), ("🗝️ Iron Key", 340), ("🥉 Bronze Medal", 280),
        ("🧣 Silk Handkerchief", 440), ("🪈 Ornate Flute", 540), ("🪢 Sturdy Rope", 360),
        ("🍄 Glowing Mushroom", 620), ("🪮 Ivory Comb", 720), ("💎 Jade Fragment", 840),
        ("🧭 Steel Compass", 960), ("🔍 Magnifying Glass", 1080), ("🎒 Leather Satchel", 1280),
        ("🧪 Crystal Vial", 1440), ("✨ Gold Nugget", 1800), ("🏹 Hunting Bow", 1520),
    ],

    "epic": [
        ("👑 Royal Crown", 3000), ("💜 Amethyst Crystal", 3750), ("🐉 Dragon Scale", 4500),
        ("🔥 Phoenix Feather", 5500), ("⚡ Energy Core", 6500), ("🌌 Cosmic Fragment", 7500),
        ("💠 Mythic Gem", 8750), ("🗿 Titan Relic", 10000), ("🧬 Ancient DNA", 11250),
        ("🪐 Void Stone", 12500), ("📖 Forbidden Tome", 13750), ("🩸 Blood Ruby", 15000),
        ("🧊 Frozen Heart", 17500), ("☄️ Meteor Fragment", 20000), ("👁️ Cursed Eye", 22500),
        ("🦷 Dragon Tooth", 3500), ("🧭 Enchanted Compass", 4375), ("🪙 Ancient Coin", 5000),
        ("💍 Ruby Ring", 6250), ("🧥 Shadow Cloak", 8000), ("🌙 Moonstone", 9500),
        ("☀️ Solar Flare", 11250), ("🗺️ Star Map", 13000), ("🧪 Elixir of Life", 15000),
        ("⛏️ Mithril Ingot", 18750), ("🪶 Phoenix Down", 21250), ("🦾 Titan's Grip", 23750),
        ("🌀 Void Essence", 27500), ("🧸 Cursed Doll", 32500), ("🐑 Golden Fleece", 37500),
    ],

    "legendary": [
        ("🌟 Celestial Artifact", 6000), ("👁️ Eye of Eternity", 7500),
        ("💫 Divine Crystal", 10000), ("🐲 Ancient Dragon Egg", 15000),
        ("🌌 Universe Shard", 25000), ("👑 Crown of Gods", 37500),
        ("⚔️ Blade of Chaos", 50000), ("🪐 Core of the Void", 75000),
        ("🌠 Fallen Star", 100000), ("🧿 Orb of Infinity", 250000),
        ("🗡️ Excalibur", 125000), ("🎁 Pandora's Box", 200000),
        ("💎 Philosopher's Stone", 325000), ("☀️ Eye of Ra", 450000),
        ("🔱 Spear of Destiny", 600000), ("🏆 Holy Grail", 1000000),
        ("🛡️ Aegis Shield", 1750000), ("🔨 Mjolnir", 2500000),
        ("📖 Necronomicon", 3750000), ("⛲ Fountain of Youth", 5000000),
        ("⌛ Chronos' Hourglass", 7500000), ("🌟 Star of Bethlehem", 12500000),
        ("🌍 Atlas' Globe", 20000000), ("🔥 Prometheus' Flame", 30000000),
        ("🪽 Icarus' Wings", 50000000),
    ],

    "godly": [
        ("🌌 Heart of the Multiverse", 50000000),
        ("⚡ Zeus' Master Bolt", 120000000),
        ("🔱 Poseidon's Trident", 150000000),
        ("🔥 Hades' Helm of Darkness", 180000000),
        ("👁️ All-Seeing Eye of Odin", 250000000),
        ("🗡️ Godslayer Blade", 500000000),
        ("🛡️ Shield of the First God", 800000000),
        ("💍 One Ring to Rule Them All", 1500000000),
        ("🌌 Infinite Gauntlet", 3000000000),
        ("✨ Essence of Creation", 10000000000),
    ],
}

ADVENTURE_EVENTS = {
    "common": [
        "searched through trash piles",
        "explored an abandoned alley",
        "wandered through old ruins",
        "dug near a broken wagon",
        "searched a forgotten campsite",
        "rummaged through a dusty attic",
        "scavenged a local junkyard",
        "checked under a loose floorboard",
        "walked through a foggy meadow",
        "poked around an old well",
        "inspected a hollow log",
        "sifted through river silt",
    ],
    "rare": [
        "explored an ancient cave",
        "snuck into a merchant caravan",
        "searched a hidden temple",
        "raided a bandit stash",
        "explored underground tunnels",
        "ventured into a deep ravine",
        "scaled a crumbling watchtower",
        "found a secret passage in the library",
        "investigated a mysterious shipwreck",
        "tracked a glowing trail in the woods",
        "deciphered markings on a stone monolith",
        "discovered a secluded mountain shrine",
    ],
    "epic": [
        "explored volcanic ruins",
        "crossed forbidden lands",
        "searched a cursed fortress",
        "flew above ancient kingdoms",
        "ventured into magical forests",
        "descended into the crystal depths",
        "survived the shifting desert dunes",
        "entered a floating sky island",
        "braved the whispers of the shadow realm",
        "climbed the peak of the world",
        "unlocked a vault from the golden age",
        "navigated a labyrinth of illusions",
    ],
    "legendary": [
        "vanished into the void itself",
        "crossed dimensions",
        "explored celestial ruins",
        "entered a forgotten realm",
        "traveled beyond mortal lands",
        "reached the source of all magic",
        "battled through the heart of a supernova",
        "stood before the throne of eternity",
        "walked the path of the stars",
        "unraveled the fabric of reality",
        "witnessed the birth of a new galaxy",
        "spoke with the ancients of the beyond",
    ],
    "godly": [
        "ascended to the divine plane",
        "confronted the creators of the universe",
        "rewrote the laws of physics",
        "harnessed the power of a trillion stars",
        "transcended space and time",
        "received a blessing from the primordial gods",
        "survived the collapse of a parallel dimension",
        "unlocked the secrets of the infinite multiverse",
    ],
}
