"""
Project Stonks
Configuration Settings

All configurable values live here.
"""

from pathlib import Path

# ======================================================
# Project Information
# ======================================================

PROJECT_NAME = "Project Stonks"

VERSION = "0.1.0"

# ======================================================
# Market Data
# ======================================================

UNIVERSE = "SP500"

LOOKBACK_PERIOD = "1y"

INTERVAL = "1d"

# ======================================================
# Project Directories
# ======================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

RAW_DATA_DIR = DATA_DIR / "raw"

PROCESSED_DATA_DIR = DATA_DIR / "processed"

REPORTS_DIR = BASE_DIR / "reports"

JOURNAL_DIR = BASE_DIR / "journal"

# Scoring Weights

TREND_WEIGHT = 30
MOMENTUM_WEIGHT = 25
OPPORTUNITY_WEIGHT = 20
LIQUIDITY_WEIGHT = 15
RISK_WEIGHT = 10