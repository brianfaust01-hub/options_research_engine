"""
Project Stonks
Portfolio Allocation Engine

Sprint 21

Ranks executable trade recommendations based on overall capital allocation
attractiveness.

This is intentionally separate from OpportunityScore.

OpportunityScore answers:
    "Is this a good trade?"

AllocationScore answers:
    "If I only have limited capital, how much does this trade deserve
     relative to every other opportunity?"
"""

import pandas as pd


def _extract_note_value(notes, prefix):
    """
    Pulls numeric values out of notes such as:

    Contract Score: 100
    Theta drag: 2.53% of premium per day
    """

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
    """
    Only executable option trades should receive allocation scores.

    This prevents trades with NaN option fields from ranking.
    """

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


def _score_trade(row):

    if not _is_executable_trade(row):
        return 0

    score = 0

    ###################################
    # Research confidence
    ###################################

    score += row["confidence"] * 0.45

    ###################################
    # Contract quality
    ###################################

    contract_score = _extract_note_value(
        row["notes"],
        "Contract Score:",
    )

    if contract_score is not None:
        score += contract_score * 0.35

    ###################################
    # Theta drag
    ###################################

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

    ###################################
    # Lower premium preferred
    ###################################

    if row["premium"] <= 8:
        score += 8

    elif row["premium"] <= 12:
        score += 5

    elif row["premium"] <= 20:
        score += 2

    ###################################
    # Smaller portfolio allocation preferred
    ###################################

    if row["position_size_pct"] <= 0.05:
        score += 5

    elif row["position_size_pct"] > 0.08:
        score -= 10

    return round(score)


def allocate_portfolio(
    trades_df,
    max_recommendations=3,
):

    trades_df = trades_df.copy()

    ###################################
    # Calculate Allocation Scores
    ###################################

    trades_df["allocation_score"] = trades_df.apply(
        _score_trade,
        axis=1,
    )

    trades_df["allocation_rank"] = pd.NA

    trades_df["allocation_decision"] = "No Allocation"

    ###################################
    # Only executable trades compete
    ###################################

    eligible = trades_df[
        (trades_df["allocation_score"] > 0)
        &
        (trades_df.apply(_is_executable_trade, axis=1))
    ].sort_values(
        "allocation_score",
        ascending=False,
    )

    ###################################
    # Rank trades
    ###################################

    for rank, idx in enumerate(
        eligible.index,
        start=1,
    ):

        trades_df.loc[idx, "allocation_rank"] = rank

        if rank <= max_recommendations:

            trades_df.loc[
                idx,
                "allocation_decision",
            ] = "Allocate"

        else:

            trades_df.loc[
                idx,
                "allocation_decision",
            ] = "Watch"

    return trades_df