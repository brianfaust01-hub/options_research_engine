from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from broker_reconciliation import (  # noqa: E402
    BrokerTrade, apply_confirmed_closures, pair_round_trips, reconcile_portfolio,
)


class BrokerReconciliationTests(unittest.TestCase):
    def test_fifo_round_trip_preserves_broker_prices(self):
        common = dict(ticker="ABC", expiration="2026-09-18", strike=100.0, option_type="CALL", quantity=1)
        trades = [
            BrokerTrade("2026-08-01T10:00:00", "BUY", position_effect="TO OPEN", price=2.0, order_type="LMT", **common),
            BrokerTrade("2026-08-02T10:00:00", "SELL", position_effect="TO CLOSE", price=3.5, order_type="STP", **common),
        ]
        result = pair_round_trips(trades)
        self.assertEqual(result[0]["gross_pnl"], 150.0)
        self.assertEqual(result[0]["exit_order_type"], "STP")

    def test_closed_broker_trade_flags_stale_open_position_without_mutation(self):
        portfolio = pd.DataFrame([{
            "PositionID": "P1", "Ticker": "ABC", "OptionStrategy": "Long Call",
            "Expiration": "2026-09-18", "Strike": 100, "EntryPremium": 2.0, "Status": "OPEN",
        }])
        original = portfolio.copy(deep=True)
        trips = [{"ticker": "ABC", "expiration": "2026-09-18", "strike": 100.0,
                  "option_type": "CALL", "entry_price": 2.0, "opened_at": "x", "closed_at": "y"}]
        result = reconcile_portfolio(portfolio, trips)
        self.assertEqual(result[0]["reconciliation_status"], "MATCHED_CLOSED")
        self.assertTrue(result[0]["requires_portfolio_review"])
        pd.testing.assert_frame_equal(portfolio, original)

    def test_confirmed_closure_is_applied_to_copy_on_disk(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portfolio.csv"
            pd.DataFrame([{
                "PositionID": "P1", "Ticker": "ABC", "EntryPremium": 2.0,
                "Status": "OPEN", "ExitDate": None, "ExitReason": None,
                "ExitPremium": None, "CurrentPremium": None, "PnLPct": None,
                "LastReviewed": None,
            }]).to_csv(path, index=False)
            report = {"portfolio_reconciliation": [{
                "position_id": "P1", "requires_portfolio_review": True,
                "broker_trade": {"closed_at": "2026-08-21T14:00:00", "exit_price": 1.0},
            }]}
            self.assertEqual(apply_confirmed_closures(report, path), 1)
            result = pd.read_csv(path)
        self.assertEqual(result.loc[0, "Status"], "CLOSED")
        self.assertEqual(result.loc[0, "ExitReason"], "BROKER_RECONCILED_CLOSE")
        self.assertEqual(result.loc[0, "PnLPct"], -0.5)


if __name__ == "__main__":
    unittest.main()
