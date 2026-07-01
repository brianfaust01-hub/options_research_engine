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

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

RAW_DATA_DIR = DATA_DIR / "raw"

PROCESSED_DATA_DIR = DATA_DIR / "processed"

REPORTS_DIR = BASE_DIR / "reports"

JOURNAL_DIR = BASE_DIR / "journal"