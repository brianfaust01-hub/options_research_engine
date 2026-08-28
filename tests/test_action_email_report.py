from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from report_writer import build_daily_report  # noqa: E402


class ActionEmailReportTests(unittest.TestCase):
    def test_flat_portfolio_empty_csv_builds_report_without_false_warning(self):
        recommendations = pd.DataFrame([{
            "ticker": "WATCH1", "opportunity_type": "Long Call Candidate",
            "allocation_decision": "Watch", "allocation_rank": 1,
            "market_regime": "Neutral", "risk_mode": "Normal",
            "breadth_regime": "Neutral",
        }])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rec_path = root / "recommendations.csv"
            pos_path = root / "position_actions.csv"
            recommendations.to_csv(rec_path, index=False)
            pos_path.write_text("\n", encoding="utf-8")
            report_path = build_daily_report(rec_path, pos_path, root)
            markdown = report_path.read_text(encoding="utf-8")

        self.assertIn("## Current Position Actions\n\nNone.", markdown)
        self.assertNotIn("Position analysis unavailable", markdown)

    def test_report_contains_only_allocated_trade_actions(self):
        recommendations = pd.DataFrame([
            {
                "ticker": "PUT1", "opportunity_type": "Long Put Candidate",
                "allocation_decision": "Allocate", "allocation_rank": 1,
                "option_strategy": "Long Put", "expiration": "2026-10-16",
                "strike": 90, "contracts": 1, "premium": 2,
                "execution_entry_price": 2.05, "profit_target_pct": .75,
                "stop_loss_pct": .35, "time_stop_dte": 14,
                "profit_target_price": 3.58, "stop_loss_price": 1.75,
                "max_risk_dollars": 200, "institutional_trade_grade": "A",
                "execution_grade": "A", "market_regime": "Neutral",
                "risk_mode": "Normal", "breadth_regime": "Neutral",
                "expected_move_window_days": 5, "time_edge_score": 88,
                "time_edge_grade": "A", "earnings_date": "2026-11-01",
                "earnings_status": "CONFIRMED",
                "shadow_conservative_contracts": 1,
                "shadow_balanced_contracts": 2,
                "shadow_aggressive_contracts": 3,
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
            "trading_days_in_position": 2,
            "expected_move_window_days": 5,
            "thesis_deadline": "2026-08-28",
            "earnings_date": "2026-11-01",
        }])

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rec_path = root / "recommendations.csv"
            pos_path = root / "positions.csv"
            recommendations.to_csv(rec_path, index=False)
            positions.to_csv(pos_path, index=False)
            hindsight_path = root / "hindsight.json"
            hindsight_path.write_text(json.dumps({
                "generated_at": "2026-08-25T12:00:00",
                "horizons": {"7D": {
                    "win_rate": .56, "evaluated": 42,
                    "sample_status": "CREDIBLE",
                }},
                "counts": {"thesis_episodes": 31},
                "allocation_primary": {
                    "all_recommendations": {"win_rate": .56, "evaluated": 42, "sample_status": "CREDIBLE"},
                    "allocated": {"win_rate": .60, "evaluated": 5, "sample_status": "PRELIMINARY"},
                    "unallocated": {"win_rate": .54, "evaluated": 30, "sample_status": "CREDIBLE"},
                },
                "episode_primary": {"win_rate": .55, "evaluated": 31, "sample_status": "CREDIBLE"},
                "recent_version": {
                    "version": "0.3.0",
                    "allocation": {"allocated": {"win_rate": .75, "evaluated": 4, "sample_status": "PRELIMINARY"}},
                },
            }), encoding="utf-8")
            report_path = build_daily_report(
                rec_path, pos_path, root, hindsight_path
            )
            markdown = report_path.read_text(encoding="utf-8")
            html = report_path.with_suffix(".html").read_text(encoding="utf-8")

        self.assertIn("PUT1", markdown)
        self.assertNotIn("WATCH1", markdown)
        self.assertIn("Long Put", markdown)
        self.assertIn("$3.58", markdown)
        self.assertIn("$1.75", markdown)
        self.assertIn("HOLD", markdown)
        self.assertIn("5d / 88 A", markdown)
        self.assertIn("1/2/3", markdown)
        self.assertIn("Day 2 / 5", markdown)
        self.assertIn("research-only", markdown)
        self.assertIn("Research Health (Not Trading Guidance)", markdown)
        self.assertIn("All recommendations: 56.0% (42 evaluated; CREDIBLE)", markdown)
        self.assertIn("Allocated recommendations: 60.0% (5 evaluated; PRELIMINARY)", markdown)
        self.assertIn("Known unallocated recommendations: 54.0%", markdown)
        self.assertIn("Latest-version allocated: 75.0%", markdown)
        self.assertIn("PUT1", html)


if __name__ == "__main__":
    unittest.main()
