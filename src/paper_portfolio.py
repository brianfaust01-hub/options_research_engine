"""
Project Stonks
Paper Portfolio

Sprint 30B

Single source of truth for active paper positions.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


PORTFOLIO_PATH = Path("data/paper_portfolio.csv")


PORTFOLIO_COLUMNS = [
    "PositionID",
    "RecommendationID",
    "Ticker",
    "OptionStrategy",
    "Expiration",
    "Strike",
    "Contracts",
    "EntryPremium",
    "EntryDate",
    "Status",
    "ExitDate",
    "ExitReason",
    "ExitPremium",
    "CurrentUnderlying",
    "CurrentPremium",
    "PnLPct",
    "AlphaVsSPY",
    "LastReviewed",
    "PeakPremium",
    "PeakPremiumDate",
    "RecommendedStop",
    "RecommendedStopDate",
    "ProfitProtectionStatus",
    "LockedProfitPct",
]


def load_portfolio() -> pd.DataFrame:

    if not PORTFOLIO_PATH.exists():

        df = pd.DataFrame(columns=PORTFOLIO_COLUMNS)

        PORTFOLIO_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        df.to_csv(PORTFOLIO_PATH, index=False)

        return df

    portfolio = pd.read_csv(PORTFOLIO_PATH)
    for column in PORTFOLIO_COLUMNS:
        if column not in portfolio.columns:
            portfolio[column] = None
    return portfolio


def save_portfolio(df: pd.DataFrame):

    PORTFOLIO_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        PORTFOLIO_PATH,
        index=False,
    )


def get_open_positions():

    portfolio = load_portfolio()

    if portfolio.empty:
        return portfolio

    return portfolio[
        portfolio["Status"] == "OPEN"
    ].copy()


def allocate_position(
    recommendation_id,
    ticker,
    option_strategy,
    expiration,
    strike,
    contracts,
    entry_premium,
):

    portfolio = load_portfolio()

    position = {
        "PositionID": datetime.now().strftime("%Y%m%d%H%M%S%f"),
        "RecommendationID": recommendation_id,
        "Ticker": ticker,
        "OptionStrategy": option_strategy,
        "Expiration": expiration,
        "Strike": strike,
        "Contracts": contracts,
        "EntryPremium": entry_premium,
        "EntryDate": datetime.now().isoformat(timespec="seconds"),
        "Status": "OPEN",
        "ExitDate": None,
        "ExitReason": None,
        "ExitPremium": None,
        "CurrentUnderlying": None,
        "CurrentPremium": None,
        "PnLPct": None,
        "AlphaVsSPY": None,
        "LastReviewed": None,
        "PeakPremium": entry_premium,
        "PeakPremiumDate": datetime.now().isoformat(timespec="seconds"),
        "RecommendedStop": None,
        "RecommendedStopDate": None,
        "ProfitProtectionStatus": "INACTIVE",
        "LockedProfitPct": None,
    }

    portfolio = pd.concat(
        [
            portfolio,
            pd.DataFrame([position]),
        ],
        ignore_index=True,
    )

    save_portfolio(portfolio)


def update_position(position_id, **updates):

    portfolio = load_portfolio()

    if portfolio.empty:
        return

    mask = portfolio["PositionID"] == position_id

    for key, value in updates.items():

        if key in portfolio.columns:
            portfolio.loc[mask, key] = value

    save_portfolio(portfolio)


def close_position(
    position_id,
    exit_price,
    exit_reason,
):

    update_position(
        position_id,
        Status="CLOSED",
        ExitDate=datetime.now().isoformat(timespec="seconds"),
        ExitPremium=exit_price,
        ExitReason=exit_reason,
    )
