"""
Project Stonks
Configuration
"""

from pathlib import Path

PROJECT_NAME = "Project Stonks"

VERSION = "0.2.0"

CONFIG_VERSION = "Momentum_v1"

PAPER_TRADING = True

TEST_MODE = True

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

MAX_POSITION_SIZE_PCT = 0.05
MAX_TRADE_RISK_PCT = 0.015
MAX_SINGLE_CONTRACT_COST_PCT = 0.08

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

RAW_DATA_DIR = DATA_DIR / "raw"

PROCESSED_DATA_DIR = DATA_DIR / "processed"

REPORTS_DIR = BASE_DIR / "reports"

JOURNAL_DIR = BASE_DIR / "journal"