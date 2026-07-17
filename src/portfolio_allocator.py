"""
Project Stonks
Portfolio Allocation Engine

Sprint 30A:
Ranks executable recommendations and adjusts allocation aggressiveness
based on broad market context.
"""

import pandas as pd

from config import (
    DEFENSIVE_ALLOCATION_MULTIPLIER,
    SELECTIVE_ALLOCATION_MULTIPLIER,
    RISK_ON_ALLOCATION_MULTIPLIER,
)


def _extract_note_value(notes, prefix):
    if not isinstance(notes, list):
        return None

    for note in notes:
        if isinstance(note, str) and note.startswith(prefix):
            value = note.replace(prefix, "").strip()
            value = (
                value.replace("% of premium per day", "")
                .replace("%", "")
                .replace("$", "")
                .strip()
            )

            try:
                return float(value)
            except ValueError:
                return None

    return None


def _is_executable_trade(row):
    required_fields = [
        "option_strategy",
        "expiration",
        "strike",
        "premium",
        "contracts",
    ]

    if row["action"] != "Evaluate Options":
        return False

    for field in required_fields:
        if field not in row:
            return False

        if pd.isna(row[field]):
            return False

    if int(row["contracts"]) <= 0:
        return False

    return True


def _market_multiplier(market_context):
    risk_mode = market_context.get("risk_mode", "Neutral")

    if risk_mode == "Defensive":
        return DEFENSIVE_ALLOCATION_MULTIPLIER

    if risk_mode == "Selective":
        return SELECTIVE_ALLOCATION_MULTIPLIER

    return RISK_ON_ALLOCATION_MULTIPLIER


def _score_trade(row, market_context):
    if not _is_executable_trade(row):
        return 0

    score = 0

    score += row["confidence"] * 0.45

    contract_score = _extract_note_value(
        row["notes"],
        "Contract Score:",
    )

    if contract_score is not None:
        score += contract_score * 0.35

    theta_drag = _extract_note_value(
        row["notes"],
        "Theta drag:",
    )

    if theta_drag is not None:
        if theta_drag <= 2:
            score += 10
        elif theta_drag <= 3:
            score += 5
        elif theta_drag >= 4:
            score -= 10

    if row["premium"] <= 8:
        score += 8
    elif row["premium"] <= 12:
        score += 5
    elif row["premium"] <= 20:
        score += 2

    if row["position_size_pct"] <= 0.05:
        score += 5
    elif row["position_size_pct"] > 0.08:
        score -= 10

    market_regime = market_context.get("market_regime", "Unknown")

    if market_regime == "Bearish" and row["option_strategy"] == "Long Call":
        score *= 0.50

    if market_regime == "Bullish" and row["option_strategy"] == "Long Put":
        score *= 0.70

    score *= _market_multiplier(market_context)

    return round(score)


def allocate_portfolio(
    trades_df,
    market_context,
    max_recommendations=3,
):

    trades_df = trades_df.copy()

    trades_df["market_regime"] = market_context.get("market_regime")
    trades_df["risk_mode"] = market_context.get("risk_mode")
    trades_df["allocation_bias"] = market_context.get("allocation_bias")
    trades_df["market_score"] = market_context.get("market_score")

    trades_df["allocation_score"] = trades_df.apply(
        lambda row: _score_trade(row, market_context),
        axis=1,
    )

    trades_df["allocation_rank"] = pd.NA
    trades_df["allocation_decision"] = "No Allocation"

    # NEW
    trades_df["PortfolioStatus"] = "NOT_ALLOCATED"

    eligible = trades_df[
        (trades_df["allocation_score"] > 0)
        &
        (trades_df.apply(_is_executable_trade, axis=1))
    ].sort_values(
        "allocation_score",
        ascending=False,
    )

    for rank, idx in enumerate(eligible.index, start=1):
        trades_df.loc[idx, "allocation_rank"] = rank

        if rank <= max_recommendations:
            trades_df.loc[idx, "allocation_decision"] = "Allocate"
            trades_df.loc[idx, "PortfolioStatus"] = "OPEN"
        else:
            trades_df.loc[idx, "allocation_decision"] = "Watch"

    return trades_df