"""
Project Stonks
Configuration
"""

from pathlib import Path

# ---------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------

PROJECT_NAME = "Project Stonks"

VERSION = "0.3.0-alpha"

CONFIG_VERSION = "ResearchMode_v1"

# ---------------------------------------------------------------------
# Operating Modes
# ---------------------------------------------------------------------

PAPER_TRADING = True

TEST_MODE = False

# Allow disabling journal writes while developing.
# Set back to True before normal daily runs.
ENABLE_JOURNAL_WRITES = True

# ---------------------------------------------------------------------
# Test Universe
# ---------------------------------------------------------------------

TEST_TICKERS = [
    "AAPL",
    "IFF",
    "NVDA",
    "PCG",
    "TFC",
    "TSN",
    "BRK-B",
    "BF-B",
]

LOOKBACK_PERIOD = "1y"

INTERVAL = "1d"

# ---------------------------------------------------------------------
# Paper Portfolio
# ---------------------------------------------------------------------

PAPER_PORTFOLIO_VALUE = 15_000

MAX_POSITION_SIZE_PCT = 0.08

MAX_TRADE_RISK_PCT = 0.025

MAX_POSITION_SIZE_PCT = 0.08

# ---------------------------------------------------------------------
# Research Engine
# ---------------------------------------------------------------------

MIN_EXECUTABLE_CONTRACT_SCORE = 25

# Counterfactual capacity target. The production allocator intentionally
# retains its existing limit of three while Sprint 35A findings await
# holdings, concentration, and correlation context.
MAX_ALLOCATED_TRADES = 5

# Portfolio-level capital arbitration. The candidate pool bounds expensive
# earnings checks; it is not a trade-count or deployment target.
PORTFOLIO_ARBITRATION_CANDIDATE_POOL = 30
PORTFOLIO_MIN_FORWARD_SCORE = 70.0
PORTFOLIO_INCUMBENT_ADVANTAGE = 5.0
MAX_CAPITAL_UTILIZATION_PCT = 1.00
MAX_AGGREGATE_STOP_LOSS_PCT = 0.10
MAX_SECTOR_EXPOSURE_PCT = 0.35
MAX_THEME_EXPOSURE_PCT = 0.25

# Portfolio construction must balance diversification with operational
# simplicity. Existing holdings consume slots; ADD decisions do not.
MAX_ACTIVE_PORTFOLIO_POSITIONS = 10
MIN_POSITION_VALUE_PCT = 0.02
MAX_CONTRACTS_PER_POSITION = 3

# Long-premium stop orders are execution guidance, not guaranteed loss caps.
# Bound total premium exposed even when modeled stop losses remain acceptable.
MAX_LONG_PREMIUM_AT_RISK_PCT = 0.50

# A new ticker must overcome a small operational hurdle. Repeated sector and
# theme exposure receives an additional marginal ranking penalty while hard
# concentration limits remain in force.
PORTFOLIO_NEW_POSITION_PENALTY = 2.0
PORTFOLIO_SECTOR_REPEAT_PENALTY = 2.0
PORTFOLIO_THEME_REPEAT_PENALTY = 3.0

MIN_OPPORTUNITY_SCORE = 70

# ---------------------------------------------------------------------
# Contract Search
# ---------------------------------------------------------------------

MIN_OPTION_DTE = 14

# Long-premium recommendations use expiration runway separately from their
# short thesis clock. Production selection will not choose contracts below
# this floor.
MIN_LONG_PREMIUM_DTE = 45

MAX_OPTION_DTE = 150

MIN_OPTION_PREMIUM = 0.05

MAX_PREMIUM_PCT_OF_STOCK = 0.25

MIN_MONEYNESS = 0.90

MAX_MONEYNESS = 1.40

# ---------------------------------------------------------------------
# Execution Engine (Sprint 32B)
# ---------------------------------------------------------------------

EXECUTION_ENGINE_ENABLED = True

EXECUTION_ENGINE_TEST_MODE = True

RESEARCH_PRICE_METHOD = "MID"

EXECUTION_ENTRY_METHOD = "ASK"

EXECUTION_EXIT_METHOD = "BID"

# Execution grading thresholds

EXECUTION_SPREAD_GRADE_A = 0.03

EXECUTION_SPREAD_GRADE_B = 0.06

EXECUTION_SPREAD_GRADE_C = 0.10

EXECUTION_SPREAD_GRADE_D = 0.15

# Execution score weights

EXECUTION_SPREAD_WEIGHT = 0.60

EXECUTION_OPEN_INTEREST_WEIGHT = 0.25

EXECUTION_VOLUME_WEIGHT = 0.15

# Execution thresholds
# Currently informational.
# Sprint 33B will begin enforcing these.

TARGET_SPREAD_PCT = 0.05

MAX_ACCEPTABLE_SPREAD_PCT = 0.15

MIN_EXECUTION_SCORE = 70

MIN_EXECUTION_GRADE = "C"

# ---------------------------------------------------------------------
# Institutional Trade Score (Sprint 33)
# ---------------------------------------------------------------------

# The master score used to rank trades for portfolio allocation.

INSTITUTIONAL_RESEARCH_WEIGHT = 0.40

INSTITUTIONAL_CONTRACT_WEIGHT = 0.25

INSTITUTIONAL_EXECUTION_WEIGHT = 0.20

INSTITUTIONAL_TRADE_QUALITY_WEIGHT = 0.15

# Reserved for future learning engine enhancements.

INSTITUTIONAL_MARKET_WEIGHT = 0.00

INSTITUTIONAL_DIVERSIFICATION_WEIGHT = 0.00

# ---------------------------------------------------------------------
# Portfolio Allocation (Sprint 33)
# ---------------------------------------------------------------------

# Feature flags for future experimentation.

PORTFOLIO_SCORE_USE_EXECUTION = True

PORTFOLIO_SCORE_USE_TRADE_QUALITY = True

PORTFOLIO_SCORE_MARKET_MULTIPLIER = True

# ---------------------------------------------------------------------
# Market Regime
# ---------------------------------------------------------------------

ALLOW_CALLS_IN_BEARISH_REGIME = False

ALLOW_PUTS_IN_BULLISH_REGIME = True

DEFENSIVE_ALLOCATION_MULTIPLIER = 0.50

SELECTIVE_ALLOCATION_MULTIPLIER = 0.75

RISK_ON_ALLOCATION_MULTIPLIER = 1.00

# ---------------------------------------------------------------------
# Debug
# ---------------------------------------------------------------------

DEBUG_OPTION_SELECTOR = False

# ---------------------------------------------------------------------
# Legacy Manual Paper Positions
#
# Kept only for backwards compatibility.
# paper_portfolio.csv is now the source of truth.
# ---------------------------------------------------------------------

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

# ---------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"

RAW_DATA_DIR = DATA_DIR / "raw"

PROCESSED_DATA_DIR = DATA_DIR / "processed"

REPORTS_DIR = BASE_DIR / "reports"

JOURNAL_DIR = BASE_DIR / "journal"
