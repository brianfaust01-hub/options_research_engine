from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from allocation_capacity_audit import audit_files  # noqa: E402
from portfolio_allocator import (  # noqa: E402
    allocate_portfolio,
    explain_allocation_ineligibility,
)


def executable_trade(ticker: str, score: float) -> dict:
    return {
        "ticker": ticker,
        "action": "Evaluate Options",
        "option_strategy": "Long Call",
        "expiration": "2026-12-18",
        "strike": 100.0,
        "premium": 5.0,
        "contracts": 1,
        "institutional_trade_score": score,
        "institutional_trade_grade": "B",
        "execution_score": score,
        "trade_quality_score": score,
        "confidence": score,
        "spread_pct": 0.05,
        "option_open_interest": 500,
        "sector": "Fixture",
        "industry": "Fixture",
    }


class AllocationCapacityAuditTests(unittest.TestCase):
    def test_diagnostic_reasons_match_existing_executability_gates(self):
        row = pd.Series(
            {
                "ticker": "BROKEN",
                "action": "Pass",
                "premium": 0,
                "contracts": 0,
            }
        )

        reasons = explain_allocation_ineligibility(row)

        self.assertIn("ACTION_NOT_EVALUATE_OPTIONS", reasons)
        self.assertIn("MISSING_OPTION_STRATEGY", reasons)
        self.assertIn("MISSING_EXPIRATION", reasons)
        self.assertIn("MISSING_OR_INVALID_STRIKE", reasons)
        self.assertIn("MISSING_OR_INVALID_PREMIUM", reasons)
        self.assertIn("MISSING_OR_INVALID_CONTRACTS", reasons)
        self.assertIn(
            "MISSING_OR_INVALID_INSTITUTIONAL_TRADE_SCORE",
            reasons,
        )

    def test_production_allocator_still_allocates_exactly_three(self):
        frame = pd.DataFrame(
            executable_trade(f"T{index}", 90 - index)
            for index in range(5)
        )
        result = allocate_portfolio(
            frame,
            market_context={
                "market_regime": "Bullish",
                "risk_mode": "Normal",
            },
        )

        self.assertEqual(
            int(result["allocation_decision"].eq("Allocate").sum()),
            3,
        )
        self.assertEqual(
            int(result["allocation_decision"].eq("Watch").sum()),
            2,
        )

    def test_audit_finds_rank_four_and_five_without_changing_them(self):
        frame = pd.DataFrame(
            executable_trade(f"T{index}", 90 - index)
            for index in range(5)
        )
        allocated = allocate_portfolio(
            frame,
            market_context={
                "market_regime": "Bullish",
                "risk_mode": "Normal",
            },
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trade_recommendations_fixture.csv"
            allocated.to_csv(path, index=False)
            report = audit_files([path], counterfactual_limit=5)

        self.assertTrue(report["configuration"]["limits_disagree"])
        self.assertFalse(
            report["configuration"]["production_behavior_changed"]
        )
        self.assertEqual(
            len(report["counterfactual"]["candidates"]),
            2,
        )
        self.assertEqual(
            report["counterfactual"]["strategy_mix"],
            {"Long Call": 2},
        )


if __name__ == "__main__":
    unittest.main()
