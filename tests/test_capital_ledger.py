from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from capital_ledger import (  # noqa: E402
    LEDGER_COLUMNS, _append_unique, assess_snapshot_sequence,
    nav_identity_residual, weekly_performance,
)


class CapitalLedgerTests(unittest.TestCase):
    def test_append_is_idempotent_and_preserves_first_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.csv"
            first = {column: "" for column in LEDGER_COLUMNS}
            first.update({"EventID": "E1", "Amount": 100})
            changed = dict(first, Amount=999)
            self.assertEqual(_append_unique(path, [first], LEDGER_COLUMNS, "EventID"), 1)
            self.assertEqual(_append_unique(path, [changed], LEDGER_COLUMNS, "EventID"), 0)
            with path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["Amount"], "100")

    def test_nav_jump_is_quarantined_not_repaired(self):
        rows = [
            {"AsOfDate": "2026-09-07", "NetLiquidatingValue": "100000", "DataQualityStatus": "COMPLETE", "DataQualityIssues": ""},
            {"AsOfDate": "2026-09-08", "NetLiquidatingValue": "200000", "DataQualityStatus": "COMPLETE", "DataQualityIssues": ""},
            {"AsOfDate": "2026-09-09", "NetLiquidatingValue": "99000", "DataQualityStatus": "COMPLETE", "DataQualityIssues": ""},
        ]
        result = assess_snapshot_sequence(rows)
        self.assertEqual(result[1]["DataQualityStatus"], "QUARANTINED")
        self.assertEqual(result[2]["DataQualityStatus"], "COMPLETE")
        self.assertEqual(result[1]["NetLiquidatingValue"], "200000")

    def test_weekly_return_refuses_incomplete_deployed_capital_coverage(self):
        rows = [
            {"AsOfDate": "2026-09-07", "NetLiquidatingValue": "100000", "OptionMarketValue": "5000", "DataQualityStatus": "COMPLETE"},
            {"AsOfDate": "2026-09-11", "NetLiquidatingValue": "99000", "OptionMarketValue": "6000", "DataQualityStatus": "COMPLETE"},
        ]
        result = weekly_performance(rows, "2026-09-07", "2026-09-11", 15000)
        self.assertEqual(result["net_pnl"], -1000)
        self.assertAlmostEqual(result["return_on_experiment_base_pct"], -1 / 15)
        self.assertIsNone(result["return_on_time_weighted_deployed_capital_pct"])
        self.assertEqual(result["deployed_capital_status"], "INSUFFICIENT_DAILY_SNAPSHOTS")

    def test_nav_identity_reconciles_flows_pnl_and_fees(self):
        residual = nav_identity_residual(
            beginning_nav=100000, ending_nav=100440, external_flows=0,
            realized_pnl=500, unrealized_pnl_change=-50, fees=10,
        )
        self.assertEqual(residual, 0)


if __name__ == "__main__":
    unittest.main()
