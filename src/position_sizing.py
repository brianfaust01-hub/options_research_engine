"""
Project Stonks
Position Sizing Engine

Sprint 17:
Risk-aware paper trading position sizing.
"""

from config import (
    PAPER_PORTFOLIO_VALUE,
    MAX_SINGLE_CONTRACT_COST_PCT,
)


def calculate_position_size(
    confidence: int,
    premium: float | None,
    option_strategy: str | None,
):
    if premium is None or option_strategy is None:
        return {
            "position_size_pct": None,
            "position_value": None,
            "max_risk_dollars": None,
            "contracts": None,
        }

    contract_cost = premium * 100

    max_single_contract_cost = (
        PAPER_PORTFOLIO_VALUE * MAX_SINGLE_CONTRACT_COST_PCT
    )

    if contract_cost > max_single_contract_cost:
        contracts = 0
    else:
        contracts = 1

    position_value = contracts * contract_cost
    position_size_pct = position_value / PAPER_PORTFOLIO_VALUE
    max_risk_dollars = position_value

    return {
        "position_size_pct": position_size_pct,
        "position_value": position_value,
        "max_risk_dollars": max_risk_dollars,
        "contracts": contracts,
    }