from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from exit_rules import build_exit_plan  # noqa: E402
from position_review import DEFAULT_STOP_LOSS_PCT  # noqa: E402


class AdaptiveExitRuleTests(unittest.TestCase):
    def test_liquid_short_high_time_edge_trade_can_reach_five_percent(self):
        plan = build_exit_plan(
            confidence=90, premium=10, entry_price=10.10, dte=60, theta=-.35,
            implied_volatility=.25, spread_pct=.01, execution_score=95,
            time_edge_score=90, expected_move_window_days=5,
        )
        self.assertEqual(plan["stop_loss_pct"], .05)
        self.assertEqual(plan["stop_loss_price"], 9.59)
        self.assertEqual(plan["exit_reference_price"], 10.10)
        self.assertEqual(plan["profit_target_pct"], .125)
        self.assertEqual(plan["profit_target_price"], 11.36)

    def test_high_iv_and_wide_spread_never_exceed_twenty_percent(self):
        plan = build_exit_plan(
            confidence=90, premium=10, entry_price=10.20, dte=60, theta=-.10,
            implied_volatility=1.20, spread_pct=.12, execution_score=50,
            time_edge_score=50, expected_move_window_days=30,
        )
        self.assertEqual(plan["stop_loss_pct"], .20)
        self.assertEqual(plan["stop_loss_price"], 8.16)
        self.assertEqual(plan["profit_target_pct"], .50)

    def test_spread_noise_floor_prevents_unrealistically_tight_stop(self):
        plan = build_exit_plan(
            confidence=90, premium=10, entry_price=10, dte=60, theta=-.40,
            implied_volatility=.25, spread_pct=.04, execution_score=99,
            time_edge_score=99, expected_move_window_days=5,
        )
        self.assertEqual(plan["stop_loss_pct"], .08)
        self.assertIn("quote-noise floor", plan["stop_loss_reason"])

    def test_position_review_fallback_uses_hard_backstop(self):
        self.assertEqual(DEFAULT_STOP_LOSS_PCT, .20)


if __name__ == "__main__":
    unittest.main()
