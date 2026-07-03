"""
Project Stonks
Trade Journal

Sprint 20:
Structured recommendation journal with fields needed for outcome review.
"""

from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from config import VERSION, CONFIG_VERSION


JOURNAL_PATH = Path("data/trade_journal.csv")


def _build_recommendation_id(trade_dict: dict, timestamp: datetime) -> str:
    ticker = trade_dict.get("ticker", "UNKNOWN")
    action = trade_dict.get("action", "UNKNOWN")
    strategy = trade_dict.get("option_strategy", "NO_OPTION")

    clean_timestamp = timestamp.strftime("%Y%m%d_%H%M%S")

    return f"{clean_timestamp}_{ticker}_{action}_{strategy}"


def _classify_trade_status(trade_dict: dict) -> str:
    if trade_dict.get("action") == "Watch":
        return "WATCHLIST"

    if trade_dict.get("action") != "Evaluate Options":
        return "PASS"

    if trade_dict.get("option_strategy") is None:
        return "NOT_EXECUTABLE"

    if trade_dict.get("contracts") in [None, 0]:
        return "NOT_EXECUTABLE"

    return "PAPER_TRADE_CANDIDATE"


def _get_latest_underlying_price(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="5d")

        if history.empty:
            return None

        return float(history["Close"].iloc[-1])

    except Exception:
        return None


def log_trade_recommendation(trade):

    JOURNAL_PATH.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now()

    trade_dict = asdict(trade)

    trade_dict["RecommendationID"] = _build_recommendation_id(
        trade_dict,
        timestamp,
    )
    trade_dict["RecommendationDate"] = timestamp
    trade_dict["ProjectVersion"] = VERSION
    trade_dict["ConfigVersion"] = CONFIG_VERSION
    trade_dict["TradeStatus"] = _classify_trade_status(trade_dict)

    trade_dict["EntryUnderlyingPrice"] = _get_latest_underlying_price(
        trade_dict["ticker"]
    )
    trade_dict["CurrentUnderlyingPrice"] = None
    trade_dict["CurrentDTE"] = None

    trade_dict["EntryPrice"] = trade_dict.get("premium")
    trade_dict["ExitPrice"] = None
    trade_dict["ExitDate"] = None
    trade_dict["ExitReason"] = None
    trade_dict["PnL"] = None
    trade_dict["PnLPct"] = None
    trade_dict["SPYReturnPct"] = None
    trade_dict["AlphaVsSPY"] = None
    trade_dict["LastReviewedDate"] = None
    trade_dict["OutcomeReviewed"] = False

    df = pd.DataFrame([trade_dict])

    if JOURNAL_PATH.exists():
        existing = pd.read_csv(JOURNAL_PATH)

        df = pd.concat(
            [existing, df],
            ignore_index=True,
        )

    df.to_csv(
        JOURNAL_PATH,
        index=False,
    )