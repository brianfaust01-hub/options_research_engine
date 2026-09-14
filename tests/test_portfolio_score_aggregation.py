from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from portfolio_allocator import (  # noqa: E402
    _build_portfolio_reason,
    _calculate_portfolio_score,
    allocate_portfolio,
)


def executable_trade(score=89.4, strategy="Long Call"):
    return {
        "ticker": "TEST",
        "action": "Evaluate Options",
        "option_strategy": strategy,
        "expiration": "2026-11-20",
        "strike": 100.0,
        "premium": 5.0,
        "contracts": 1,
        "institutional_trade_score": score,
        "institutional_trade_grade": "A-",
        "execution_score": 90.0,
        "trade_quality_score": 80.0,
        "confidence": 90.0,
    }


class PortfolioScoreAggregationTests(unittest.TestCase):
    def test_selective_market_is_bounded_point_penalty(self):
        row = pd.Series(executable_trade())
        context = {"market_regime": "Neutral", "risk_mode": "Selective"}

        self.assertEqual(_calculate_portfolio_score(row, context), 84.4)
        self.assertIn("-5.0 points", _build_portfolio_reason(row, context))

    def test_selective_market_does_not_make_strong_trade_ineligible(self):
        result = allocate_portfolio(
            pd.DataFrame([executable_trade()]),
            {"market_regime": "Neutral", "risk_mode": "Selective"},
            max_recommendations=1,
        )

        self.assertEqual(result.iloc[0]["portfolio_score"], 84.4)
        self.assertEqual(result.iloc[0]["allocation_decision"], "Allocate")
        self.assertEqual(result.iloc[0]["portfolio_market_multiplier"], 0.75)

    def test_directional_mismatch_remains_a_separate_penalty(self):
        row = pd.Series(executable_trade(score=90.0, strategy="Long Put"))
        context = {"market_regime": "Bullish", "risk_mode": "Selective"}

        self.assertEqual(_calculate_portfolio_score(row, context), 79.0)


if __name__ == "__main__":
    unittest.main()
