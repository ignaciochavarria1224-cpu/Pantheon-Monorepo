"""
Asset universe manager for Olympus.
Defines and manages the default set of ~200 liquid US equities across sectors.
No ETFs, options, crypto, or illiquid names in the default list.
"""

from __future__ import annotations
from typing import Optional

from core.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default universe: ~200 liquid US large/mid-cap equities across 8 sectors.
# Organized by sector for readability and easy maintenance.
# To add or remove a symbol: edit the relevant sector list below.
# ---------------------------------------------------------------------------

_UNIVERSE_BY_SECTOR: dict[str, list[str]] = {
    "technology": [
        "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "INTC",
        "QCOM", "TXN", "NOW", "ADBE", "INTU", "MU", "AMAT", "LRCX",
        "KLAC", "MRVL", "ADI", "SNPS", "CDNS", "FTNT", "PANW", "CRWD",
        "ZS", "TEAM", "WDAY", "SNOW", "DDOG", "NTNX",
    ],
    "communication_services": [
        "META", "GOOGL", "GOOG", "NFLX", "DIS", "CMCSA", "T", "VZ",
        "TMUS", "CHTR", "PARA", "WBD", "SNAP", "PINS", "RBLX",
    ],
    "consumer_discretionary": [
        "AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "TJX",
        "BKNG", "CMG", "ORLY", "AZO", "ROST", "DHI", "LEN",
        "PHM", "YUM", "HLT", "MAR", "RCL",
    ],
    "consumer_staples": [
        "WMT", "PG", "COST", "KO", "PEP", "PM", "MO", "MDLZ",
        "CL", "KMB", "GIS", "K", "HSY", "STZ", "BF.B",
    ],
    "financials": [
        "BRK.B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS",
        "BLK", "SCHW", "AXP", "C", "USB", "PNC", "TFC",
        "COF", "ICE", "CME", "SPGI", "MCO",
    ],
    "healthcare": [
        "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "DHR",
        "PFE", "BMY", "AMGN", "GILD", "ISRG", "SYK", "BSX",
        "MDT", "ZBH", "BAX", "HCA", "CVS",
    ],
    "industrials": [
        "CAT", "DE", "HON", "UPS", "RTX", "LMT", "NOC", "GE",
        "MMM", "EMR", "ETN", "PH", "ROK", "CMI", "ITW",
        "GD", "TDG", "FDX", "NSC", "UNP",
    ],
    "energy": [
        "XOM", "CVX", "COP", "EOG", "SLB", "MPC", "PSX", "VLO",
        "PXD", "OXY", "HES", "HAL", "DVN", "FANG", "BKR",
    ],
    "materials": [
        "LIN", "APD", "SHW", "FCX", "NEM", "NUE", "STLD",
        "DOW", "DD", "PPG",
    ],
    "real_estate": [
        "PLD", "AMT", "EQIX", "CCI", "SPG", "O", "DLR",
        "PSA", "WELL", "AVB",
    ],
    "utilities": [
        "NEE", "SO", "DUK", "AEP", "EXC", "XEL", "SRE",
        "ED", "ETR", "EIX",
    ],
}

# Flat list derived from the sector map — this is the authoritative universe
_DEFAULT_UNIVERSE: list[str] = [
    symbol
    for symbols in _UNIVERSE_BY_SECTOR.values()
    for symbol in symbols
]


class UniverseManager:
    """
    Manages the asset universe for Olympus.

    The default universe is a hardcoded set of ~200 liquid US equities.
    It is stable and inspectable — no API call required to define it.
    """

    def __init__(
        self,
        symbols: Optional[list[str]] = None,
        sector_filter: Optional[list[str]] = None,
    ) -> None:
        """
        Args:
            symbols: Override the default universe with a custom list.
            sector_filter: Restrict to specific sectors from _UNIVERSE_BY_SECTOR.
                           Ignored if symbols is provided.
        """
        if symbols is not None:
            self._symbols = [s.upper().strip() for s in symbols]
        elif sector_filter is not None:
            filtered: list[str] = []
            for sector in sector_filter:
                sector_lower = sector.lower()
                if sector_lower in _UNIVERSE_BY_SECTOR:
                    filtered.extend(_UNIVERSE_BY_SECTOR[sector_lower])
                else:
                    logger.warning("Unknown sector filter: '%s' — skipped", sector)
            self._symbols = filtered
        else:
            self._symbols = list(_DEFAULT_UNIVERSE)

        logger.info(
            "UniverseManager initialized with %d symbols", len(self._symbols)
        )

    def get_all_symbols(self) -> list[str]:
        """Return all symbols in the universe."""
        return list(self._symbols)

    def get_symbol_count(self) -> int:
        """Return the number of symbols in the universe."""
        return len(self._symbols)

    def get_symbols_by_sector(self, sector: str) -> list[str]:
        """Return symbols for a given sector. Returns empty list for unknown sectors."""
        return list(_UNIVERSE_BY_SECTOR.get(sector.lower(), []))

    def get_available_sectors(self) -> list[str]:
        """Return all sector names available in the default universe."""
        return list(_UNIVERSE_BY_SECTOR.keys())

    def get_sector_for_symbol(self, symbol: str) -> Optional[str]:
        """Return the sector name for a symbol, or None if not mapped."""
        symbol_upper = symbol.upper()
        for sector, symbols in _UNIVERSE_BY_SECTOR.items():
            if symbol_upper in symbols:
                return sector
        return None

    def contains(self, symbol: str) -> bool:
        """Return True if symbol is in the universe."""
        return symbol.upper() in self._symbols
