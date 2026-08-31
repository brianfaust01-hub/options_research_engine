"""
Project Stonks
Position Sizing Engine

Sprint 33C

Determines how much capital should be allocated to each recommendation.

The engine uses a single source of truth:

    MAX_POSITION_SIZE_PCT

Everything else is derived from that value.
"""

from math import floor

from config import (
    MAX_CONTRACTS_PER_POSITION,
    MAX_POSITION_SIZE_PCT,
    PAPER_PORTFOLIO_VALUE,
)


def calculate_position_size(
    confidence: int,
    premium: float | None,
    option_strategy: str | None,
):
    """
    Calculate the recommended paper position size.

    Returns
    -------
    dict
    """

    if premium is None or option_strategy is None:
        return {
            "position_size_pct": None,
            "position_value": None,
            "max_risk_dollars": None,
            "contracts": None,
        }

    contract_cost = premium * 100

    max_position_value = (
        PAPER_PORTFOLIO_VALUE
        * MAX_POSITION_SIZE_PCT
    )

    if contract_cost <= 0:
        contracts = 0
    else:
        contracts = floor(
            max_position_value
            / contract_cost
        )

    contracts = min(
        contracts,
        MAX_CONTRACTS_PER_POSITION,
    )

    position_value = (
        contracts
        * contract_cost
    )

    position_size_pct = (
        position_value
        / PAPER_PORTFOLIO_VALUE
        if PAPER_PORTFOLIO_VALUE > 0
        else 0
    )

    max_risk_dollars = position_value

    return {
        "position_size_pct": round(
            position_size_pct,
            4,
        ),
        "position_value": round(
            position_value,
            2,
        ),
        "max_risk_dollars": round(
            max_risk_dollars,
            2,
        ),
        "contracts": contracts,
    }
