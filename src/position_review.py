"""
Project Stonks
Position Review Engine

Sprint 30B

Reviews actual paper portfolio positions against the latest
recommendation set.

Source of truth:

- data/paper_portfolio.csv

Current option pricing is provided by the Charles Schwab
Market Data API.

The research journal remains separate and immutable.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from paper_portfolio import get_open_positions
from schwab.market_data_client import get_normalized_option


DEFAULT_PROFIT_TARGET_PCT = 0.75
DEFAULT_STOP_LOSS_PCT = 0.35
DEFAULT_TIME_STOP_DTE = 14


def _safe_float(
    value,
    default=None,
):
    if value is None or pd.isna(value):
        return default

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return default


def _safe_int(
    value,
    default=0,
):
    if value is None or pd.isna(value):
        return default

    try:
        return int(
            float(value)
        )

    except (
        TypeError,
        ValueError,
    ):
        return default


def _get_option_mark(
    position: dict,
):
    """
    Pull the current option mark from Schwab Market Data.

    Pricing preference:

    1. Schwab Mark
    2. Bid/ask midpoint
    3. Last trade

    Mark or midpoint is preferred because option last-trade
    values may be stale, especially for illiquid contracts.
    """

    ticker = str(
        position["Ticker"]
    ).upper().strip()

    expiration = str(
        position["Expiration"]
    )

    strike = float(
        position["Strike"]
    )

    option_strategy = str(
        position.get(
            "OptionStrategy",
            "",
        )
    )

    option_type = (
        "PUT"
        if "PUT" in option_strategy.upper()
        else "CALL"
    )

    try:

        option = (
            get_normalized_option(
                ticker=ticker,
                expiration=expiration,
                strike=strike,
                option_type=option_type,
            )
        )

        if option is None:
            return None

        mark = _safe_float(
            option.get(
                "Mark"
            )
        )

        if (
            mark is not None
            and mark > 0
        ):
            return mark

        bid = _safe_float(
            option.get(
                "Bid"
            ),
            0.0,
        )

        ask = _safe_float(
            option.get(
                "Ask"
            ),
            0.0,
        )

        if (
            bid > 0
            and ask > 0
        ):
            return (
                bid + ask
            ) / 2

        last_price = _safe_float(
            option.get(
                "Last"
            ),
            0.0,
        )

        if last_price > 0:
            return last_price

    except Exception as error:

        print(
            "Schwab option pricing failed for "
            f"{ticker} "
            f"{expiration} "
            f"{strike}: "
            f"{error}"
        )

        return None

    return None


def _calculate_dte(
    expiration: str,
):
    try:

        expiration_date = datetime.strptime(
            expiration,
            "%Y-%m-%d",
        ).date()

    except (
        TypeError,
        ValueError,
    ):
        return None

    return (
        expiration_date
        - datetime.today().date()
    ).days


def _find_latest_recommendation(
    position: dict,
    trades_df: pd.DataFrame,
):
    ticker = str(
        position["Ticker"]
    )

    if (
        trades_df.empty
        or "ticker" not in trades_df.columns
    ):
        return None

    matches = trades_df[
        trades_df[
            "ticker"
        ].astype(str)
        == ticker
    ].copy()

    if matches.empty:
        return None

    sort_columns = [
        column
        for column in [
            "allocation_score",
            "confidence",
        ]
        if column in matches.columns
    ]

    if sort_columns:

        matches = matches.sort_values(
            sort_columns,
            ascending=[
                False
            ] * len(
                sort_columns
            ),
        )

    return matches.iloc[0]


def _resolve_exit_rules(
    position: dict,
):
    entry_premium = _safe_float(
        position.get(
            "EntryPremium"
        )
    )

    profit_target = _safe_float(
        position.get(
            "ProfitTarget"
        )
    )

    stop_loss = _safe_float(
        position.get(
            "StopLoss"
        )
    )

    time_stop_dte = _safe_int(
        position.get(
            "TimeStopDTE"
        ),
        DEFAULT_TIME_STOP_DTE,
    )

    if entry_premium is not None:

        if profit_target is None:

            profit_target = (
                entry_premium
                * (
                    1
                    + DEFAULT_PROFIT_TARGET_PCT
                )
            )

        if stop_loss is None:

            stop_loss = (
                entry_premium
                * (
                    1
                    - DEFAULT_STOP_LOSS_PCT
                )
            )

    return (
        profit_target,
        stop_loss,
        time_stop_dte,
    )


def _review_single_position(
    position: dict,
    trades_df: pd.DataFrame,
):
    ticker = str(
        position["Ticker"]
    )

    entry_price = _safe_float(
        position.get(
            "EntryPremium"
        )
    )

    contracts = _safe_int(
        position.get(
            "Contracts"
        ),
        0,
    )

    (
        profit_target,
        stop_loss,
        time_stop_dte,
    ) = _resolve_exit_rules(
        position
    )

    #
    # Current option pricing now comes from Schwab.
    #

    current_price = (
        _get_option_mark(
            position
        )
    )

    dte = _calculate_dte(
        str(
            position["Expiration"]
        )
    )

    pnl_pct = None
    pnl_dollars = None

    if (
        current_price is not None
        and entry_price is not None
        and entry_price > 0
    ):

        pnl_pct = (
            current_price
            - entry_price
        ) / entry_price

        pnl_dollars = (
            current_price
            - entry_price
        ) * 100 * contracts

    latest_recommendation = (
        _find_latest_recommendation(
            position=position,
            trades_df=trades_df,
        )
    )

    latest_action = None
    latest_allocation_decision = None
    latest_allocation_score = None
    latest_trade_quality = None
    latest_grade = None

    if latest_recommendation is not None:

        latest_action = (
            latest_recommendation.get(
                "action"
            )
        )

        latest_allocation_decision = (
            latest_recommendation.get(
                "allocation_decision"
            )
        )

        latest_allocation_score = (
            latest_recommendation.get(
                "allocation_score"
            )
        )

        latest_trade_quality = (
            latest_recommendation.get(
                "trade_quality_score"
            )
        )

        latest_grade = (
            latest_recommendation.get(
                "trade_quality_grade"
            )
        )

    recommendation = "HOLD"
    reason = "Position remains open"

    if (
        current_price is not None
        and profit_target is not None
        and current_price
        >= profit_target
    ):

        recommendation = "SELL"
        reason = (
            "Profit target reached"
        )

    elif (
        current_price is not None
        and stop_loss is not None
        and current_price
        <= stop_loss
    ):

        recommendation = "SELL"
        reason = (
            "Stop loss reached"
        )

    elif (
        dte is not None
        and dte
        <= time_stop_dte
    ):

        recommendation = "SELL"
        reason = (
            "Time stop reached"
        )

    elif latest_recommendation is None:

        recommendation = "REVIEW"

        reason = (
            "Ticker no longer appears in latest "
            "recommendation set"
        )

    elif latest_action == "Pass":

        recommendation = "REVIEW"

        reason = (
            "Latest research downgraded ticker "
            "to Pass"
        )

    elif (
        latest_allocation_decision
        == "Allocate"
    ):

        recommendation = "HOLD"

        reason = (
            "Ticker remains allocated by latest scan"
        )

    elif latest_action == "Watch":

        recommendation = "HOLD"

        reason = (
            "Ticker moved to watchlist but no exit "
            "rule triggered"
        )

    elif latest_allocation_decision in [
        "Watch",
        "No Allocation",
    ]:

        recommendation = "HOLD"

        reason = (
            "Ticker still valid but not currently "
            "allocated"
        )

    return {
        "ticker": ticker,
        "option_strategy": position.get(
            "OptionStrategy"
        ),
        "expiration": position.get(
            "Expiration"
        ),
        "strike": position.get(
            "Strike"
        ),
        "contracts": contracts,
        "entry_price": entry_price,
        "current_price": current_price,
        "pnl_pct": pnl_pct,
        "pnl_dollars": pnl_dollars,
        "profit_target": profit_target,
        "stop_loss": stop_loss,
        "dte": dte,
        "time_stop_dte": time_stop_dte,
        "latest_action": latest_action,
        "latest_allocation_decision": (
            latest_allocation_decision
        ),
        "latest_allocation_score": (
            latest_allocation_score
        ),
        "latest_trade_quality": (
            latest_trade_quality
        ),
        "latest_grade": latest_grade,
        "position_recommendation": (
            recommendation
        ),
        "position_reason": reason,
    }


def review_positions(
    trades_df: pd.DataFrame,
):
    open_positions = (
        get_open_positions()
    )

    if open_positions.empty:
        return pd.DataFrame()

    results = []

    for (
        _,
        position,
    ) in open_positions.iterrows():

        results.append(
            _review_single_position(
                position=(
                    position.to_dict()
                ),
                trades_df=trades_df,
            )
        )

    return pd.DataFrame(
        results
    )