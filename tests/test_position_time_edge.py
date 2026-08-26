from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from position_review import _review_single_position  # noqa: E402


class PositionTimeEdgeTests(unittest.TestCase):
    @patch("position_review.datetime")
    @patch("position_review._get_option_mark", return_value=1.05)
    def test_position_exits_before_earnings_inside_thesis_window(
        self, _mark, mocked_datetime,
    ):
        mocked_datetime.today.return_value = pd.Timestamp("2026-08-25").to_pydatetime()
        mocked_datetime.strptime.side_effect = lambda value, fmt: __import__(
            "datetime"
        ).datetime.strptime(value, fmt)
        position = {
            "Ticker": "TEST", "EntryPremium": 1.0, "Contracts": 1,
            "Expiration": "2026-10-16", "Strike": 100,
            "OptionStrategy": "Long Call", "EntryDate": "2026-08-24T10:00:00",
        }
        recommendations = pd.DataFrame([{
            "ticker": "TEST", "action": "Evaluate Options",
            "allocation_decision": "Allocate", "allocation_score": 90,
            "expected_move_window_days": 5, "time_edge_score": 88,
            "earnings_date": "2026-08-26",
        }])
        result = _review_single_position(position, recommendations)
        self.assertEqual(result["position_recommendation"], "SELL")
        self.assertIn("Earnings inside", result["position_reason"])

    @patch("position_review.datetime")
    @patch("position_review._get_option_mark", return_value=0.90)
    def test_unproductive_position_exits_at_short_thesis_deadline(
        self, _mark, mocked_datetime,
    ):
        mocked_datetime.today.return_value = pd.Timestamp("2026-08-31").to_pydatetime()
        mocked_datetime.strptime.side_effect = lambda value, fmt: __import__(
            "datetime"
        ).datetime.strptime(value, fmt)
        position = {
            "Ticker": "TEST", "EntryPremium": 1.0, "Contracts": 1,
            "Expiration": "2026-10-16", "Strike": 100,
            "OptionStrategy": "Long Call", "EntryDate": "2026-08-24T10:00:00",
        }
        recommendations = pd.DataFrame([{
            "ticker": "TEST", "action": "Evaluate Options",
            "allocation_decision": "Allocate", "allocation_score": 90,
            "expected_move_window_days": 5, "time_edge_score": 88,
            "earnings_date": "2026-11-01",
        }])
        result = _review_single_position(position, recommendations)
        self.assertEqual(result["position_recommendation"], "SELL")
        self.assertIn("window expired", result["position_reason"])
        self.assertEqual(result["thesis_deadline"], "2026-08-31")


if __name__ == "__main__":
    unittest.main()
