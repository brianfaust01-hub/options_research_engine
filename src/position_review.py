"""
Project Stonks
Position Review Engine

Sprint 27:
Reviews existing paper positions against the latest recommendation set.

Purpose:
Every daily scan should answer:

- Should I hold existing positions?
- Did any hit profit target?
- Did any hit stop loss?
- Did any hit time stop?
- Is the position still supported by the latest research?
- Is the ticker being recommended again because we already own it?
"""

from datetime import datetime

import pandas as pd
import yfinance as yf

from config import OPEN_PAPER_POSITIONS


def _get_option_mark(position: dict):
    """
    Pulls current option mark from yfinance when possible.

    Falls back to lastPrice if bid/ask are unavailable.
    """

    ticker = position["ticker"]
    expiration = position["expiration"]
    strike = float(position["strike"])

    option_strategy = position.get("option_strategy", "")

    option_type = "call"

    if "Put" in option_strategy:
        option_type = "put"

    try:
        stock = yf.Ticker(ticker)
        chain = stock.option_chain(expiration)

        options = chain.calls

        if option_type == "put":
            options = chain.puts

        match = options[
            options["strike"] == strike
        ]

        if match.empty:
            return None

        row = match.iloc[0]

        bid = float(row.get("bid", 0))
        ask = float(row.get("ask", 0))
        last_price = float(row.get("lastPrice", 0))

        if bid > 0 and ask > 0:
            return (bid + ask) / 2

        if last_price > 0:
            return last_price

        return None

    except Exception:
        return None


def _calculate_dte(expiration: str):
    expiration_date = datetime.strptime(expiration, "%Y-%m-%d").date()
    today = datetime.today().date()

    return (expiration_date - today).days


def _find_latest_recommendation(position: dict, trades_df: pd.DataFrame):
    ticker = position["ticker"]

    matches = trades_df[
        trades_df["ticker"] == ticker
    ].copy()

    if matches.empty:
        return None

    matches = matches.sort_values(
        ["allocation_score", "confidence"],
        ascending=[False, False],
    )

    return matches.iloc[0]


def _review_single_position(position: dict, trades_df: pd.DataFrame):
    ticker = position["ticker"]

    entry_price = float(position["entry_price"])
    profit_target = float(position["profit_target"])
    stop_loss = float(position["stop_loss"])
    time_stop_dte = int(position["time_stop_dte"])

    current_price = _get_option_mark(position)

    dte = _calculate_dte(position["expiration"])

    pnl_pct = None
    pnl_dollars = None

    if current_price is not None:
        pnl_pct = (current_price - entry_price) / entry_price
        pnl_dollars = (
            current_price - entry_price
        ) * 100 * int(position["contracts"])

    latest_recommendation = _find_latest_recommendation(
        position,
        trades_df,
    )

    latest_action = None
    latest_allocation_decision = None
    latest_allocation_score = None
    latest_trade_quality = None
    latest_grade = None

    if latest_recommendation is not None:
        latest_action = latest_recommendation.get("action")
        latest_allocation_decision = latest_recommendation.get(
            "allocation_decision"
        )
        latest_allocation_score = latest_recommendation.get(
            "allocation_score"
        )
        latest_trade_quality = latest_recommendation.get(
            "trade_quality_score"
        )
        latest_grade = latest_recommendation.get(
            "trade_quality_grade"
        )

    recommendation = "HOLD"
    reason = "Position remains open"

    if current_price is not None and current_price >= profit_target:
        recommendation = "SELL"
        reason = "Profit target reached"

    elif current_price is not None and current_price <= stop_loss:
        recommendation = "SELL"
        reason = "Stop loss reached"

    elif dte <= time_stop_dte:
        recommendation = "SELL"
        reason = "Time stop reached"

    elif latest_recommendation is None:
        recommendation = "REVIEW"
        reason = "Ticker no longer appears in latest recommendation set"

    elif latest_action == "Pass":
        recommendation = "REVIEW"
        reason = "Latest research downgraded ticker to Pass"

    elif latest_allocation_decision == "Allocate":
        recommendation = "HOLD"
        reason = "Ticker remains allocated by latest scan"

    elif latest_action == "Watch":
        recommendation = "HOLD"
        reason = "Ticker moved to watchlist but no exit rule triggered"

    elif latest_allocation_decision in ["Watch", "No Allocation"]:
        recommendation = "HOLD"
        reason = "Ticker still valid but not currently allocated"

    return {
        "ticker": ticker,
        "option_strategy": position["option_strategy"],
        "expiration": position["expiration"],
        "strike": position["strike"],
        "contracts": position["contracts"],
        "entry_price": entry_price,
        "current_price": current_price,
        "pnl_pct": pnl_pct,
        "pnl_dollars": pnl_dollars,
        "profit_target": profit_target,
        "stop_loss": stop_loss,
        "dte": dte,
        "time_stop_dte": time_stop_dte,
        "latest_action": latest_action,
        "latest_allocation_decision": latest_allocation_decision,
        "latest_allocation_score": latest_allocation_score,
        "latest_trade_quality": latest_trade_quality,
        "latest_grade": latest_grade,
        "position_recommendation": recommendation,
        "position_reason": reason,
    }


def review_positions(trades_df: pd.DataFrame):
    results = []

    for position in OPEN_PAPER_POSITIONS:
        results.append(
            _review_single_position(
                position=position,
                trades_df=trades_df,
            )
        )

    return pd.DataFrame(results)