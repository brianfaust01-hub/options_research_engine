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

from report_writer import build_daily_report  # noqa: E402


class ActionEmailReportTests(unittest.TestCase):
    def test_report_contains_only_allocated_trade_actions(self):
        recommendations = pd.DataFrame([
            {
                "ticker": "PUT1", "opportunity_type": "Long Put Candidate",
                "allocation_decision": "Allocate", "allocation_rank": 1,
                "option_strategy": "Long Put", "expiration": "2026-10-16",
                "strike": 90, "contracts": 1, "premium": 2,
                "execution_entry_price": 2.05, "profit_target_pct": .75,
                "stop_loss_pct": .35, "time_stop_dte": 14,
                "max_risk_dollars": 200, "institutional_trade_grade": "A",
                "execution_grade": "A", "market_regime": "Neutral",
                "risk_mode": "Normal", "breadth_regime": "Neutral",
            },
            {
                "ticker": "WATCH1", "opportunity_type": "Long Call Candidate",
                "allocation_decision": "Watch", "allocation_rank": 2,
            },
        ])
        positions = pd.DataFrame([{
            "ticker": "OPEN1", "position_recommendation": "HOLD",
            "option_strategy": "Long Call", "expiration": "2026-11-20",
            "strike": 100, "contracts": 1, "current_price": 4,
            "pnl_pct": .10, "profit_target": 7, "stop_loss": 2.6,
            "dte": 91, "position_reason": "No exit rule triggered",
        }])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rec_path = root / "recommendations.csv"
            pos_path = root / "positions.csv"
            recommendations.to_csv(rec_path, index=False)
            positions.to_csv(pos_path, index=False)
            report_path = build_daily_report(rec_path, pos_path, root)
            markdown = report_path.read_text(encoding="utf-8")
            html = report_path.with_suffix(".html").read_text(encoding="utf-8")

        self.assertIn("PUT1", markdown)
        self.assertNotIn("WATCH1", markdown)
        self.assertIn("Long Put", markdown)
        self.assertIn("$3.50", markdown)
        self.assertIn("$1.30", markdown)
        self.assertIn("HOLD", markdown)
        self.assertIn("PUT1", html)


if __name__ == "__main__":
    unittest.main()
