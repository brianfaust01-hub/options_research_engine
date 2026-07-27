"""
Project Stonks
Trade Scoring Engine

Sprint 33A

Purpose
-------
Produces a single institutional-quality score for every executable trade.

The goal is to separate trade evaluation from portfolio allocation.

Portfolio Allocation should only need to answer:

    "Which trades have the highest Institutional Trade Score?"

rather than understanding how every individual metric should be weighted.

Future versions can incorporate:

- Historical strategy performance
- Sector concentration
- Correlation
- Expected slippage
- Portfolio diversification
- Learning Engine feedback
"""

from __future__ import annotations

import math


GRADE_THRESHOLDS = [
    (95, "A+"),
    (90, "A"),
    (85, "A-"),
    (80, "B+"),
    (75, "B"),
    (70, "B-"),
    (65, "C+"),
    (60, "C"),
    (55, "C-"),
    (50, "D"),
    (0, "F"),
]


def _safe_number(value, default=0.0):

    if value is None:
        return default

    try:
        if math.isnan(float(value)):
            return default
    except Exception:
        pass

    try:
        return float(value)
    except Exception:
        return default


def _grade(score):

    for threshold, grade in GRADE_THRESHOLDS:

        if score >= threshold:
            return grade

    return "F"


def calculate_institutional_trade_score(
    research_score,
    contract_score,
    execution_score,
    trade_quality_score,
):
    """
    Calculates the overall institutional trade score.

    Parameters
    ----------
    research_score : int
        Strategy / research conviction (0-100)

    contract_score : int
        Option contract quality (0-100)

    execution_score : int
        Liquidity / spread / execution quality (0-100)

    trade_quality_score : int
        Existing trade quality score (0-100)

    Returns
    -------
    dict
    """

    research_score = _safe_number(research_score)

    contract_score = _safe_number(contract_score)

    execution_score = _safe_number(execution_score)

    trade_quality_score = _safe_number(
        trade_quality_score
    )

    institutional_score = (
        research_score * 0.40
        + contract_score * 0.25
        + execution_score * 0.20
        + trade_quality_score * 0.15
    )

    institutional_score = round(
        institutional_score,
        1,
    )

    return {
        "institutional_trade_score": institutional_score,
        "institutional_trade_grade": _grade(
            institutional_score
        ),
        "components": {
            "research_score": research_score,
            "contract_score": contract_score,
            "execution_score": execution_score,
            "trade_quality_score": trade_quality_score,
        },
    }


if __name__ == "__main__":

    example = calculate_institutional_trade_score(
        research_score=95,
        contract_score=92,
        execution_score=88,
        trade_quality_score=70,
    )

    print(example)