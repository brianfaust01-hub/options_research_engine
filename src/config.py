"""
Project Stonks
Configuration
"""

from pathlib import Path

PROJECT_NAME = "Project Stonks"

VERSION = "0.3.0-alpha"

CONFIG_VERSION = "ResearchMode_v1"

PAPER_TRADING = True

TEST_MODE = False

TEST_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "AMD",
    "AVGO",
    "MU",
    "DDOG",
    "FFIV",
]

LOOKBACK_PERIOD = "1y"

INTERVAL = "1d"

# Paper portfolio assumptions
PAPER_PORTFOLIO_VALUE = 15_000

MAX_POSITION_SIZE_PCT = 0.08
MAX_TRADE_RISK_PCT = 0.025
MAX_SINGLE_CONTRACT_COST_PCT = 0.12

# Research mode thresholds
MIN_EXECUTABLE_CONTRACT_SCORE = 25
MAX_ALLOCATED_TRADES = 5
MIN_OPPORTUNITY_SCORE = 70

# Contract search controls
MIN_OPTION_DTE = 14
MAX_OPTION_DTE = 150
MIN_OPTION_PREMIUM = 0.05
MAX_PREMIUM_PCT_OF_STOCK = 0.25
MIN_MONEYNESS = 0.90
MAX_MONEYNESS = 1.40

# Market regime controls
ALLOW_CALLS_IN_BEARISH_REGIME = False
ALLOW_PUTS_IN_BULLISH_REGIME = True
DEFENSIVE_ALLOCATION_MULTIPLIER = 0.50
SELECTIVE_ALLOCATION_MULTIPLIER = 0.75
RISK_ON_ALLOCATION_MULTIPLIER = 1.00

# Debug controls
DEBUG_OPTION_SELECTOR = False

# Paper positions
# These are manually maintained for now.
# Schwab / Thinkorswim integration will replace this later.
OPEN_PAPER_POSITIONS = [
    {
        "ticker": "IBKR",
        "option_strategy": "Long Call",
        "expiration": "2026-09-18",
        "strike": 100.0,
        "contracts": 1,
        "entry_price": 5.35,
        "current_price": None,
        "profit_target": 9.28,
        "stop_loss": 3.45,
        "time_stop_dte": 14,
    },
    {
        "ticker": "UPS",
        "option_strategy": "Long Call",
        "expiration": "2026-08-21",
        "strike": 115.0,
        "contracts": 1,
        "entry_price": 3.40,
        "current_price": None,
        "profit_target": 5.56,
        "stop_loss": 2.06,
        "time_stop_dte": 14,
    },
]

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

RAW_DATA_DIR = DATA_DIR / "raw"

PROCESSED_DATA_DIR = DATA_DIR / "processed"

REPORTS_DIR = BASE_DIR / "reports"

JOURNAL_DIR = BASE_DIR / "journal"