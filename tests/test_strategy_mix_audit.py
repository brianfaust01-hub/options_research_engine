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

from opportunity_engine import (  # noqa: E402
    calculate_directional_opportunity_scores,
)
from strategy_mix_audit import audit_files  # noqa: E402


class StrategyMixAuditTests(unittest.TestCase):
    def test_research_direction_is_not_consumed_by_current_scoring(self):
        inputs = {
            "TrendScore": 0,
            "MomentumScore": 80,
            "LiquidityScore": 20,
            "StrategyScore": 80,
        }

        bullish_label = calculate_directional_opportunity_scores(
            {**inputs, "Direction": "Bullish"}
        )
        bearish_label = calculate_directional_opportunity_scores(
            {**inputs, "Direction": "Bearish"}
        )

        self.assertEqual(bullish_label, bearish_label)

    def test_strong_bearish_momentum_magnitude_does_not_reach_put_gate(self):
        scores = calculate_directional_opportunity_scores(
            {
                "Direction": "Bearish",
                "TrendScore": 0,
                "MomentumScore": 80,
                "LiquidityScore": 20,
                "StrategyScore": 80,
            }
        )

        self.assertEqual(scores["BullishScore"], 45)
        self.assertEqual(scores["BearishScore"], 65)
        self.assertLess(scores["BearishScore"], 75)

    def test_low_momentum_value_can_reach_put_gate(self):
        scores = calculate_directional_opportunity_scores(
            {
                "Direction": "Bearish",
                "TrendScore": 0,
                "MomentumScore": 20,
                "LiquidityScore": 20,
                "StrategyScore": 80,
            }
        )

        self.assertEqual(scores["BearishScore"], 100)
        self.assertGreaterEqual(scores["DirectionalConviction"], 25)

    def test_audit_identifies_first_zero_put_stage(self):
        frame = pd.DataFrame(
            [
                {
                    "ticker": "CALL",
                    "opportunity_type": "Long Call Candidate",
                    "action": "Evaluate Options",
                    "option_strategy": "Long Call",
                    "allocation_decision": "Allocate",
                },
                {
                    "ticker": "PASS",
                    "opportunity_type": "No Clear Edge",
                    "action": "Pass",
                    "option_strategy": None,
                    "allocation_decision": "No Allocation",
                },
            ]
        )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trade_recommendations_fixture.csv"
            frame.to_csv(path, index=False)
            report = audit_files([path])

        self.assertEqual(
            report["first_zero_put_stage"],
            "OPPORTUNITY_ENGINE",
        )
        self.assertFalse(report["production_behavior_changed"])


if __name__ == "__main__":
    unittest.main()
