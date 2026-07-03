"""
Project Stonks
Outcome Review Engine
"""

from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf

from trade_journal import JOURNAL_PATH


OPEN_STATUS = "PAPER_TRADE_CANDIDATE"


def _get_latest_stock_price(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        history = stock.history(period="5d")

        if history.empty:
            return None

        return float(history["Close"].iloc[-1])

    except Exception:
        return None


def _calculate_underlying_return(row, latest_price: float):
    entry_price = row.get("EntryUnderlyingPrice")

    if pd.isna(entry_price) or entry_price is None:
        return None

    entry_price = float(entry_price)

    if entry_price <= 0:
        return None

    if row.get("option_strategy") == "Long Put":
        return (entry_price - latest_price) / entry_price

    return (latest_price - entry_price) / entry_price


def _get_spy_return(recommendation_date, current_date):
    try:
        spy = yf.Ticker("SPY")

        start_date = recommendation_date.date()
        end_date = current_date.date() + timedelta(days=1)

        if start_date >= current_date.date():
            history = spy.history(period="5d")
        else:
            history = spy.history(
                start=start_date,
                end=end_date,
            )

        if history.empty or len(history) < 2:
            return None

        start_price = float(history["Close"].iloc[0])
        end_price = float(history["Close"].iloc[-1])

        if start_price <= 0:
            return None

        return (end_price - start_price) / start_price

    except Exception:
        return None


def _determine_exit_reason(row, pnl_pct, current_dte):
    if pnl_pct is None:
        return None

    profit_target = row.get("profit_target_pct")
    stop_loss = row.get("stop_loss_pct")
    time_stop_dte = row.get("time_stop_dte")

    if pd.notna(profit_target) and pnl_pct >= float(profit_target):
        return "PROFIT_TARGET"

    if pd.notna(stop_loss) and pnl_pct <= -float(stop_loss):
        return "STOP_LOSS"

    if (
        pd.notna(time_stop_dte)
        and current_dte is not None
        and current_dte <= int(time_stop_dte)
    ):
        return "TIME_STOP"

    return None


def _calculate_current_dte(expiration):
    if pd.isna(expiration) or expiration is None:
        return None

    try:
        expiration_date = datetime.strptime(str(expiration), "%Y-%m-%d").date()
    except ValueError:
        return None

    return (expiration_date - datetime.now().date()).days


def review_open_trades():
    if not JOURNAL_PATH.exists():
        return {
            "reviewed": 0,
            "closed": 0,
            "message": "No trade journal found.",
        }

    journal = pd.read_csv(JOURNAL_PATH)

    if journal.empty or "TradeStatus" not in journal.columns:
        return {
            "reviewed": 0,
            "closed": 0,
            "message": "No structured journal entries found.",
        }

    open_mask = journal["TradeStatus"] == OPEN_STATUS
    open_trades = journal[open_mask].copy()

    if open_trades.empty:
        return {
            "reviewed": 0,
            "closed": 0,
            "message": "No open paper trades to review.",
        }

    reviewed = 0
    closed = 0
    current_date = datetime.now()
    current_date_string = current_date.isoformat(timespec="seconds")

    for index, row in open_trades.iterrows():
        ticker = row["ticker"]
        latest_price = _get_latest_stock_price(ticker)

        if latest_price is None:
            continue

        recommendation_date = pd.to_datetime(row["RecommendationDate"])

        pnl_pct = _calculate_underlying_return(row, latest_price)
        spy_return_pct = _get_spy_return(recommendation_date, current_date)

        alpha_vs_spy = None

        if pnl_pct is not None and spy_return_pct is not None:
            alpha_vs_spy = pnl_pct - spy_return_pct

        current_dte = _calculate_current_dte(row.get("expiration"))
        exit_reason = _determine_exit_reason(row, pnl_pct, current_dte)

        journal.loc[index, "CurrentUnderlyingPrice"] = latest_price
        journal.loc[index, "CurrentDTE"] = current_dte
        journal.loc[index, "PnLPct"] = pnl_pct
        journal.loc[index, "SPYReturnPct"] = spy_return_pct
        journal.loc[index, "AlphaVsSPY"] = alpha_vs_spy
        journal.loc[index, "LastReviewedDate"] = current_date_string
        journal.loc[index, "OutcomeReviewed"] = True

        reviewed += 1

        if exit_reason is not None:
            journal.loc[index, "TradeStatus"] = "CLOSED"
            journal.loc[index, "ExitDate"] = current_date_string
            journal.loc[index, "ExitReason"] = exit_reason
            journal.loc[index, "ExitPrice"] = latest_price
            closed += 1

    journal.to_csv(JOURNAL_PATH, index=False)

    return {
        "reviewed": reviewed,
        "closed": closed,
        "message": f"Reviewed {reviewed} open paper trades; closed {closed}.",
    }