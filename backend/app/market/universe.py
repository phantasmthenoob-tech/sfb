"""Ticker classification shared by the simulator, API and research tools.

Stocks have one industry sector and any number of exposure tags. ETFs are kept
out of the stock universe: they remain loadable as benchmarks but agents do not
trade them.
"""
from __future__ import annotations

from dataclasses import dataclass

INDUSTRY_SECTORS: tuple[str, ...] = (
    "Technology",
    "Banking and finance",
    "Healthcare and pharmaceuticals",
    "Food and agriculture",
    "Retail and consumer goods",
    "Energy and oil",
    "Defense and aerospace",
    "Transportation and logistics",
    "Manufacturing",
    "Telecommunications",
    "Real estate",
    "Utilities",
    "Materials and mining",
)

EXPOSURE_TAGS: tuple[str, ...] = (
    "Government policy",
    "Defense spending",
    "Trade policy",
    "Geopolitical risk",
    "Interest rates",
    "Energy policy",
    "AI adoption",
    "China exposure",
)

# Sensible defaults for every company in a sector. Ticker-specific overrides
# below add or remove exposures without forcing a second mutually-exclusive
# category.
SECTOR_EXPOSURES: dict[str, tuple[str, ...]] = {
    "Technology": ("Government policy", "Trade policy", "AI adoption", "China exposure", "Interest rates"),
    "Banking and finance": ("Government policy", "Interest rates", "Trade policy"),
    "Healthcare and pharmaceuticals": ("Government policy", "Trade policy", "Interest rates"),
    "Food and agriculture": ("Trade policy", "Energy policy", "Government policy"),
    "Retail and consumer goods": ("Trade policy", "Interest rates", "Government policy"),
    "Energy and oil": ("Energy policy", "Geopolitical risk", "Government policy"),
    "Defense and aerospace": ("Defense spending", "Geopolitical risk", "Government policy", "Trade policy"),
    "Transportation and logistics": ("Energy policy", "Trade policy", "Geopolitical risk"),
    "Manufacturing": ("Trade policy", "Interest rates", "AI adoption", "Energy policy"),
    "Telecommunications": ("Government policy", "Interest rates", "AI adoption"),
    "Real estate": ("Interest rates", "Government policy"),
    "Materials and mining": ("Trade policy", "Energy policy", "Geopolitical risk"),
}

EXPOSURE_OVERRIDES: dict[str, tuple[str, ...]] = {
    "AAPL": ("China exposure", "AI adoption", "Trade policy"),
    "TSLA": ("China exposure", "Energy policy", "Trade policy"),
    "NVDA": ("AI adoption", "China exposure", "Trade policy"),
    "AMD": ("AI adoption", "China exposure"),
    "AVGO": ("AI adoption", "China exposure"),
    "JPM": ("Interest rates", "Government policy"),
    "BAC": ("Interest rates", "Government policy"),
    "LLY": ("Government policy", "Trade policy"),
    "PFE": ("Government policy", "Trade policy"),
    "XOM": ("Energy policy", "Geopolitical risk"),
    "CVX": ("Energy policy", "Geopolitical risk"),
    "LMT": ("Defense spending", "Geopolitical risk"),
    "RTX": ("Defense spending", "Geopolitical risk"),
    "NOC": ("Defense spending", "Geopolitical risk"),
    "BA": ("Defense spending", "Trade policy", "Geopolitical risk"),
    "DAL": ("Energy policy", "Geopolitical risk"),
    "UAL": ("Energy policy", "Geopolitical risk"),
    "F": ("Trade policy", "Interest rates", "Energy policy"),
    "T": ("Government policy", "Interest rates"),
    "VZ": ("Government policy", "Interest rates"),
    "FCX": ("China exposure", "Trade policy", "Geopolitical risk"),
    "NEM": ("Geopolitical risk", "Energy policy"),
    "ADM": ("Trade policy", "Energy policy"),
    "TSN": ("Trade policy", "Energy policy"),
}

STOCKS: tuple[tuple[str, str, str], ...] = (
    # Technology (12)
    ("AAPL", "Apple", "Technology"),
    ("MSFT", "Microsoft", "Technology"),
    ("NVDA", "NVIDIA", "Technology"),
    ("TSLA", "Tesla", "Technology"),
    ("AVGO", "Broadcom", "Technology"),
    ("AMD", "Advanced Micro Devices", "Technology"),
    ("ORCL", "Oracle", "Technology"),
    ("CRM", "Salesforce", "Technology"),
    ("ADBE", "Adobe", "Technology"),
    ("CSCO", "Cisco Systems", "Technology"),
    ("IBM", "IBM", "Technology"),
    ("INTC", "Intel", "Technology"),
    # Banking and finance (10)
    ("JPM", "JPMorgan Chase", "Banking and finance"),
    ("BAC", "Bank of America", "Banking and finance"),
    ("WFC", "Wells Fargo", "Banking and finance"),
    ("C", "Citigroup", "Banking and finance"),
    ("GS", "Goldman Sachs", "Banking and finance"),
    ("MS", "Morgan Stanley", "Banking and finance"),
    ("BLK", "BlackRock", "Banking and finance"),
    ("SCHW", "Charles Schwab", "Banking and finance"),
    ("AXP", "American Express", "Banking and finance"),
    ("USB", "U.S. Bancorp", "Banking and finance"),
    # Healthcare and pharmaceuticals (10)
    ("LLY", "Eli Lilly", "Healthcare and pharmaceuticals"),
    ("UNH", "UnitedHealth Group", "Healthcare and pharmaceuticals"),
    ("JNJ", "Johnson & Johnson", "Healthcare and pharmaceuticals"),
    ("MRK", "Merck", "Healthcare and pharmaceuticals"),
    ("PFE", "Pfizer", "Healthcare and pharmaceuticals"),
    ("ABBV", "AbbVie", "Healthcare and pharmaceuticals"),
    ("TMO", "Thermo Fisher Scientific", "Healthcare and pharmaceuticals"),
    ("ABT", "Abbott Laboratories", "Healthcare and pharmaceuticals"),
    ("DHR", "Danaher", "Healthcare and pharmaceuticals"),
    ("BMY", "Bristol Myers Squibb", "Healthcare and pharmaceuticals"),
    # Food and agriculture (10)
    ("PG", "Procter & Gamble", "Food and agriculture"),
    ("KO", "Coca-Cola", "Food and agriculture"),
    ("PEP", "PepsiCo", "Food and agriculture"),
    ("COST", "Costco", "Food and agriculture"),
    ("MDLZ", "Mondelez International", "Food and agriculture"),
    ("GIS", "General Mills", "Food and agriculture"),
    ("CAG", "Conagra Brands", "Food and agriculture"),
    ("HSY", "Hershey", "Food and agriculture"),
    ("ADM", "Archer-Daniels-Midland", "Food and agriculture"),
    ("TSN", "Tyson Foods", "Food and agriculture"),
    # Retail and consumer goods (10)
    ("AMZN", "Amazon", "Retail and consumer goods"),
    ("HD", "Home Depot", "Retail and consumer goods"),
    ("LOW", "Lowe's", "Retail and consumer goods"),
    ("TGT", "Target", "Retail and consumer goods"),
    ("NKE", "Nike", "Retail and consumer goods"),
    ("MCD", "McDonald's", "Retail and consumer goods"),
    ("SBUX", "Starbucks", "Retail and consumer goods"),
    ("TJX", "TJX Companies", "Retail and consumer goods"),
    ("DG", "Dollar General", "Retail and consumer goods"),
    ("WMT", "Walmart", "Retail and consumer goods"),
    # Energy and oil (10)
    ("XOM", "Exxon Mobil", "Energy and oil"),
    ("CVX", "Chevron", "Energy and oil"),
    ("COP", "ConocoPhillips", "Energy and oil"),
    ("SLB", "SLB", "Energy and oil"),
    ("EOG", "EOG Resources", "Energy and oil"),
    ("OXY", "Occidental Petroleum", "Energy and oil"),
    ("PSX", "Phillips 66", "Energy and oil"),
    ("VLO", "Valero Energy", "Energy and oil"),
    ("KMI", "Kinder Morgan", "Energy and oil"),
    ("HAL", "Halliburton", "Energy and oil"),
    # Defense and aerospace (10)
    ("LMT", "Lockheed Martin", "Defense and aerospace"),
    ("RTX", "RTX", "Defense and aerospace"),
    ("NOC", "Northrop Grumman", "Defense and aerospace"),
    ("GD", "General Dynamics", "Defense and aerospace"),
    ("BA", "Boeing", "Defense and aerospace"),
    ("HII", "Huntington Ingalls", "Defense and aerospace"),
    ("LHX", "L3Harris Technologies", "Defense and aerospace"),
    ("TDG", "TransDigm Group", "Defense and aerospace"),
    ("TXT", "Textron", "Defense and aerospace"),
    ("CW", "Curtiss-Wright", "Defense and aerospace"),
    # Transportation and logistics (10)
    ("UPS", "UPS", "Transportation and logistics"),
    ("FDX", "FedEx", "Transportation and logistics"),
    ("UNP", "Union Pacific", "Transportation and logistics"),
    ("CSX", "CSX", "Transportation and logistics"),
    ("NSC", "Norfolk Southern", "Transportation and logistics"),
    ("DAL", "Delta Air Lines", "Transportation and logistics"),
    ("UAL", "United Airlines", "Transportation and logistics"),
    ("LUV", "Southwest Airlines", "Transportation and logistics"),
    ("CHRW", "C.H. Robinson", "Transportation and logistics"),
    ("EXPD", "Expeditors International", "Transportation and logistics"),
    # Manufacturing (10)
    ("CAT", "Caterpillar", "Manufacturing"),
    ("DE", "Deere", "Manufacturing"),
    ("HON", "Honeywell", "Manufacturing"),
    ("GE", "GE Aerospace", "Manufacturing"),
    ("MMM", "3M", "Manufacturing"),
    ("EMR", "Emerson Electric", "Manufacturing"),
    ("ETN", "Eaton", "Manufacturing"),
    ("ITW", "Illinois Tool Works", "Manufacturing"),
    ("PH", "Parker Hannifin", "Manufacturing"),
    ("F", "Ford Motor", "Manufacturing"),
    # Telecommunications (8)
    ("T", "AT&T", "Telecommunications"),
    ("VZ", "Verizon", "Telecommunications"),
    ("TMUS", "T-Mobile US", "Telecommunications"),
    ("CMCSA", "Comcast", "Telecommunications"),
    ("CHTR", "Charter Communications", "Telecommunications"),
    ("VOD", "Vodafone", "Telecommunications"),
    ("AMX", "America Movil", "Telecommunications"),
    ("TU", "TELUS", "Telecommunications"),
    # Real estate (10)
    ("PLD", "Prologis", "Real estate"),
    ("AMT", "American Tower", "Real estate"),
    ("EQIX", "Equinix", "Real estate"),
    ("CCI", "Crown Castle", "Real estate"),
    ("SPG", "Simon Property Group", "Real estate"),
    ("O", "Realty Income", "Real estate"),
    ("PSA", "Public Storage", "Real estate"),
    ("WELL", "Welltower", "Real estate"),
    ("DLR", "Digital Realty", "Real estate"),
    ("VTR", "Ventas", "Real estate"),
    # Materials and mining (10)
    ("LIN", "Linde", "Materials and mining"),
    ("SHW", "Sherwin-Williams", "Materials and mining"),
    ("FCX", "Freeport-McMoRan", "Materials and mining"),
    ("NEM", "Newmont", "Materials and mining"),
    ("DOW", "Dow", "Materials and mining"),
    ("DD", "DuPont", "Materials and mining"),
    ("APD", "Air Products", "Materials and mining"),
    ("ECL", "Ecolab", "Materials and mining"),
    ("NUE", "Nucor", "Materials and mining"),
    ("VMC", "Vulcan Materials", "Materials and mining"),
)

ETFS: tuple[tuple[str, str], ...] = (
    ("SPY", "SPDR S&P 500 ETF"),
    ("QQQ", "Invesco QQQ Trust"),
    ("IWM", "iShares Russell 2000 ETF"),
    ("DIA", "SPDR Dow Jones Industrial Average ETF"),
    ("EFA", "iShares MSCI EAFE ETF"),
    ("EEM", "iShares MSCI Emerging Markets ETF"),
    ("GLD", "SPDR Gold Shares"),
    ("TLT", "iShares 20+ Year Treasury Bond ETF"),
)


@dataclass(frozen=True)
class TickerProfile:
    symbol: str
    name: str
    kind: str
    sector: str | None
    exposures: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "ticker": self.symbol,
            "name": self.name,
            "kind": self.kind,
            "sector": self.sector,
            "exposures": list(self.exposures),
        }


def _stock_profile(symbol: str, name: str, sector: str) -> TickerProfile:
    tags = set(SECTOR_EXPOSURES[sector])
    tags.update(EXPOSURE_OVERRIDES.get(symbol, ()))
    ordered = tuple(tag for tag in EXPOSURE_TAGS if tag in tags)
    return TickerProfile(symbol, name, "stock", sector, ordered)


STOCK_PROFILES: tuple[TickerProfile, ...] = tuple(
    _stock_profile(symbol, name, sector) for symbol, name, sector in STOCKS
)
ETF_PROFILES: tuple[TickerProfile, ...] = tuple(
    TickerProfile(symbol, name, "etf", None, ()) for symbol, name in ETFS
)
PROFILE_BY_SYMBOL: dict[str, TickerProfile] = {
    profile.symbol: profile for profile in (*STOCK_PROFILES, *ETF_PROFILES)
}

DEFAULT_STOCKS: tuple[str, ...] = tuple(profile.symbol for profile in STOCK_PROFILES)
DEFAULT_ETFS: tuple[str, ...] = tuple(profile.symbol for profile in ETF_PROFILES)
DEFAULT_UNIVERSE: tuple[str, ...] = DEFAULT_STOCKS + DEFAULT_ETFS


def profile_for(ticker: str) -> TickerProfile | None:
    return PROFILE_BY_SYMBOL.get(ticker.upper())


def is_stock(ticker: str) -> bool:
    profile = profile_for(ticker)
    return profile is None or profile.kind == "stock"


def universe_payload() -> dict:
    return {
        "stocks": [profile.as_dict() for profile in STOCK_PROFILES],
        "etfs": [profile.as_dict() for profile in ETF_PROFILES],
        "sectors": list(INDUSTRY_SECTORS),
        "exposures": list(EXPOSURE_TAGS),
    }
