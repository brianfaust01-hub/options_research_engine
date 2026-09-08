from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from empirical_exit_policy import build_shadow_exit_plan  # noqa: E402


class EmpiricalExitPolicyTests(unittest.TestCase):
    def setUp(self):
        self.production = {"stop_loss_pct": .14, "profit_target_pct": .32}
        self.context = {
            "entry_price": 10.0,
            "option_strategy": "Long Call",
            "dte": 60,
            "expected_move_window_days": 7,
            "implied_volatility": .45,
            "broker_delta": .55,
        }

    def test_sparse_history_is_explicit_and_falls_back_without_execution_change(self):
        result = build_shadow_exit_plan(
            production_plan=self.production,
            records=[{
                **self.context,
                "option_return_path": [0.02, 0.08, 0.14],
            }],
            **self.context,
        )
        self.assertEqual(result["shadow_exit_policy_status"], "INSUFFICIENT_OPTION_PATHS")
        self.assertEqual(result["shadow_stop_loss_pct"], .14)
        self.assertEqual(result["shadow_profit_target_pct"], .32)
        self.assertEqual(self.production, {"stop_loss_pct": .14, "profit_target_pct": .32})

    def test_calibrated_shadow_uses_ordered_paths_and_hard_stop_cap(self):
        winning_path = [-.04, .12, .30, -.25]
        losing_path = [-.06, -.12, -.18]
        records = [
            {**self.context, "option_return_path": winning_path}
            for _ in range(21)
        ] + [
            {**self.context, "option_return_path": losing_path}
            for _ in range(9)
        ]
        result = build_shadow_exit_plan(
            production_plan=self.production,
            records=records,
            **self.context,
        )
        self.assertEqual(result["shadow_exit_policy_status"], "CALIBRATED_SHADOW_ONLY")
        self.assertEqual(result["shadow_exit_sample_size"], 30)
        self.assertLessEqual(result["shadow_stop_loss_pct"], .20)
        self.assertGreater(result["shadow_target_first_rate"], 0)
        self.assertGreater(result["shadow_stop_first_rate"], 0)


if __name__ == "__main__":
    unittest.main()
