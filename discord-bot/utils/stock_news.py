import random

# News templates for the Stock Market
# Format: {symbol: [list of (message, price_multiplier)]}
# Multiplier > 1.0 positive, < 1.0 negative

MARKET_NEWS = {
    "VRTX": [
        ("Vertex Dynamics announces a breakthrough in Quantum AI processing!", 1.15),
        ("A major security breach was detected in Vertex's neural network servers.", 0.85),
        ("Vertex Dynamics signs a massive contract with the Global Defense Agency.", 1.10),
        ("The CEO of Vertex Dynamics was seen testing a secret exoskeleton prototype.", 1.05),
        ("Regulatory concerns over Vertex's AI ethics cause a slight market dip.", 0.92),
        ("Vertex's new robot companion 'V-Buddy' sells out in minutes!", 1.08),
        ("Rumors of a merger between Vertex and a major energy firm surface.", 1.04),
        ("A software glitch in Vertex's automated factories slows down production.", 0.90),
        ("Vertex Dynamics wins the 'Innovation of the Year' award.", 1.06),
        ("Vertex faces a lawsuit over data privacy in its latest AI model.", 0.88),
    ],
    "GLBL": [
        ("Global Energy successfully launches the world's largest solar farm.", 1.12),
        ("An oil spill in the northern sector causes environmental backlash for Global Energy.", 0.80),
        ("Global Energy discovers a massive lithium deposit in a remote region.", 1.15),
        ("Government subsidies for green energy boost Global Energy's outlook.", 1.07),
        ("A series of power outages in the city are blamed on Global Energy's grid.", 0.88),
        ("Global Energy's new fusion reactor prototype shows promising results.", 1.10),
        ("High maintenance costs for aging infrastructure impact Global Energy's profits.", 0.93),
        ("Global Energy partners with a tech giant to build smart cities.", 1.05),
        ("Global Energy's quarterly report shows record-breaking revenue.", 1.09),
        ("A sudden drop in global energy demand causes a minor stock decline.", 0.95),
    ],
    "AURA": [
        ("Aura Pharmaceuticals receives FDA approval for a revolutionary cancer treatment.", 1.20),
        ("Aura Pharmaceuticals faces a recall of its popular allergy medication.", 0.75),
        ("Aura's new longevity drug 'Aeterna' enters the final phase of testing.", 1.12),
        ("Rumors of Aura Pharmaceuticals being acquired by a tech giant drive prices up.", 1.08),
        ("Aura Pharmaceuticals' research lab suffers a catastrophic equipment failure.", 0.85),
        ("Aura Pharmaceuticals opens a new state-of-the-art research center in Europe.", 1.05),
        ("Aura Pharmaceuticals' patent for a key drug is challenged in court.", 0.88),
        ("Aura Pharmaceuticals' CEO announces a focus on affordable healthcare.", 1.03),
        ("Aura Pharmaceuticals' vaccine distribution network expands globally.", 1.06),
        ("Aura Pharmaceuticals' latest clinical trial yields disappointing results.", 0.82),
    ],
    "ORBT": [
        ("Orbital Space successfully lands the first commercial mission on Mars!", 1.25),
        ("An Orbital Space rocket explodes during a routine test flight.", 0.70),
        ("Orbital Space announces a new luxury space hotel 'The Celestial'.", 1.15),
        ("Orbital Space's satellite network 'Starlight' reaches full global coverage.", 1.10),
        ("Space debris damages an Orbital Space orbital platform.", 0.85),
        ("Orbital Space signs a multi-billion dollar deal for asteroid mining.", 1.18),
        ("A major investor pulls out of Orbital Space's moon colony project.", 0.80),
        ("Orbital Space's first space tourism flight is a resounding success.", 1.09),
        ("Orbital Space faces regulatory hurdles for its new orbital elevator.", 0.92),
        ("Orbital Space's deep space probe sends back incredible data from Europa.", 1.04),
    ],
    "TITN": [
        ("Titan Heavy Industries secures a contract for a new fleet of cargo ships.", 1.10),
        ("A strike at Titan's main manufacturing plant halts all production.", 0.82),
        ("Titan Heavy Industries unveils a new line of ultra-durable mining equipment.", 1.08),
        ("Titan's construction division wins a bid for a massive undersea bridge.", 1.07),
        ("Titan Heavy Industries faces allegations of using substandard materials.", 0.85),
        ("Titan Heavy Industries' new automated assembly line increases efficiency.", 1.06),
        ("Titan Heavy Industries' quarterly earnings fall short of expectations.", 0.90),
        ("Titan Heavy Industries' expansion into the Asian market is ahead of schedule.", 1.04),
        ("Titan Heavy Industries' CEO steps down unexpectedly, causing uncertainty.", 0.93),
        ("Titan Heavy Industries' new eco-friendly steel production is a hit.", 1.05),
    ],
    "CRPT": [
        ("CryptoVault Financial announces a new decentralized exchange platform.", 1.18),
        ("Regulators launch an investigation into CryptoVault's transaction practices.", 0.72),
        ("CryptoVault partners with a major bank for blockchain integration.", 1.14),
        ("A massive hack drains funds from CryptoVault's hot wallets.", 0.60),
        ("CryptoVault's new staking program offers record-high APY rewards.", 1.12),
        ("Government cracks down on crypto exchanges, hitting CryptoVault hard.", 0.78),
        ("CryptoVault launches its own stablecoin, shaking up the market.", 1.10),
        ("A prominent whale dumps a massive position in CryptoVault tokens.", 0.82),
        ("CryptoVault achieves record trading volume in Q3.", 1.08),
        ("Rumors of CryptoVault insolvency spark a brief panic sell-off.", 0.68),
    ],
    "GENERAL": [
        ("The Global Stock Market enters a period of unprecedented growth!", 1.05),
        ("A sudden economic recession causes a market-wide decline.", 0.95),
        ("New trade agreements boost investor confidence across all sectors.", 1.03),
        ("A global logistics crisis slows down international trade.", 0.97),
        ("Technological advancements drive a minor boom in the tech sector.", 1.02),
        ("Political instability in key regions causes market volatility.", 0.98),
        ("Interest rates are lowered, encouraging more investment.", 1.04),
        ("A major bank failure sends shockwaves through the financial world.", 0.92),
        ("Record-low unemployment rates boost consumer spending.", 1.03),
        ("A global pandemic scare causes a temporary market panic.", 0.90),
    ],
}

# Generic templates for IPO companies without dedicated news. {name} is replaced.
GENERIC_IPO_NEWS = [
    ("{name} reports stronger-than-expected quarterly earnings.", 1.12),
    ("{name}'s CEO makes a controversial statement, unsettling investors.", 0.88),
    ("{name} announces a major partnership deal.", 1.10),
    ("{name} faces an unexpected supply chain disruption.", 0.85),
    ("{name} launches a new product line to positive reviews.", 1.08),
    ("{name} is under regulatory scrutiny over compliance issues.", 0.82),
    ("Analysts upgrade {name} to 'Strong Buy' following recent results.", 1.14),
    ("{name} suffers a data breach affecting thousands of customers.", 0.78),
    ("{name} announces a share buyback program.", 1.06),
    ("{name}'s expansion into new markets exceeds expectations.", 1.11),
]


def get_random_news(active_symbols=None):
    """
    Get a random news event.
    - 70%: company-specific news for symbols with dedicated MARKET_NEWS entries
    - 15%: generic news applied to an IPO/unknown symbol
    - 15%: general market news affecting all stocks (ALL)
    """
    from config import STOCKS

    current_symbols = active_symbols or list(STOCKS.keys())
    known_symbols = [s for s in current_symbols if s in MARKET_NEWS]
    unknown_symbols = [s for s in current_symbols if s not in MARKET_NEWS]

    roll = random.random()

    if roll < 0.70 and known_symbols:
        symbol = random.choice(known_symbols)
        news_item = random.choice(MARKET_NEWS[symbol])
        return symbol, news_item[0], news_item[1]

    elif roll < 0.85 and unknown_symbols:
        symbol = random.choice(unknown_symbols)
        company_name = STOCKS.get(symbol, {}).get("name", symbol)
        template, multiplier = random.choice(GENERIC_IPO_NEWS)
        message = template.format(name=company_name)
        return symbol, message, multiplier

    else:
        news_item = random.choice(MARKET_NEWS["GENERAL"])
        return "ALL", news_item[0], news_item[1]
