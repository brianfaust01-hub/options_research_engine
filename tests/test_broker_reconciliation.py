from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from broker_reconciliation import (  # noqa: E402
    BrokerTrade, apply_confirmed_closures, build_attribution_report,
    load_current_option_positions, pair_round_trips, reconcile_portfolio,
    load_thinkorswim_trades_many, sync_current_positions,
)


class BrokerReconciliationTests(unittest.TestCase):
    def test_overlapping_evidence_statements_deduplicate_fills(self):
        statement_text = """Account Statement for X since 10/1/26 through 10/2/26

Account Trade History
,Exec Time,Spread,Side,Qty,Total Cost,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
,10/1/26 10:00:00,SINGLE,SELL,-1,0,TO CLOSE,OLD,20 NOV 26,100,CALL,1.50,1.50,STP

Options
Symbol,Option Code,Exp,Strike,Type,Qty,Trade Price,Mark,Mark Value
,OVERALL TOTALS,,,,,,,$0.00
"""
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.csv"
            second = Path(directory) / "second.csv"
            first.write_text(statement_text, encoding="utf-8")
            second.write_text(statement_text, encoding="utf-8")
            trades = load_thinkorswim_trades_many([first, second])
        self.assertEqual(len(trades), 1)

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

    def test_attribution_preserves_loss_and_layers_user_rule(self):
        trade = {"opened_at": "open-1", "entry_price": 10.0, "exit_price": 7.0,
                 "gross_pnl": -300.0, "closed_at": "close-1"}
        report = {"source_path": "source.csv", "portfolio_reconciliation": [],
                  "unmatched_broker_round_trips": [trade]}
        review = {"execution_error_loss_threshold": -0.20,
                  "confirmed_project_allocations": ["open-1"],
                  "project_recommendation_only": []}
        result = build_attribution_report(report, review)
        self.assertEqual(result["trades"][0]["gross_pnl"], -300.0)
        self.assertEqual(result["trades"][0]["trade_source"], "PROJECT_STONKS_ALLOCATED")
        self.assertEqual(result["trades"][0]["outcome_attribution"], "USER_REVIEWED_EXECUTION_PROCESS_ERROR")
        self.assertEqual(result["execution_error_count"], 1)

    def test_current_position_sync_closes_refreshes_and_creates_exact_contracts(self):
        statement_text = """Account Statement for X since 9/17/26 through 9/21/26

Account Trade History
,Exec Time,Spread,Side,Qty,Total Cost,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
,9/18/26 09:30:00,SINGLE,SELL,-1,0,TO CLOSE,OLD,20 NOV 26,100,CALL,1.50,1.50,STP
,9/18/26 10:30:00,SINGLE,BUY,+2,0,TO OPEN,NEW,20 NOV 26,50,CALL,2.00,2.00,LMT

Options
Symbol,Option Code,Exp,Strike,Type,Qty,Trade Price,Mark,Mark Value
KEEP,KEEP261120C100,20 NOV 26,100,CALL,+1,3.00,3.50,$350.00
NEW,NEW261120C50,20 NOV 26,50,CALL,+2,2.00,2.25,$450.00
,OVERALL TOTALS,,,,,,,$800.00
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            statement = root / "statement.csv"
            statement.write_text(statement_text, encoding="utf-8")
            portfolio = root / "portfolio.csv"
            columns = ["PositionID", "RecommendationID", "BrokerPositionID", "Ticker",
                "OptionStrategy", "Expiration", "Strike", "Contracts", "EntryPremium",
                "EntryDate", "Status", "ExitDate", "ExitReason", "ExitPremium",
                "CurrentUnderlying", "CurrentPremium", "PnLPct", "AlphaVsSPY",
                "LastReviewed", "CurrentDTE", "UnderlyingReturnPct", "SPYReturnPct",
                "PeakPremium", "PeakPremiumDate", "RecommendedStop", "RecommendedStopDate",
                "ProfitProtectionStatus", "LockedProfitPct"]
            pd.DataFrame([
                dict.fromkeys(columns) | {"PositionID": "P000001", "Ticker": "OLD", "OptionStrategy": "Long Call", "Expiration": "2026-11-20", "Strike": 100, "Contracts": 1, "EntryPremium": 2, "Status": "OPEN"},
                dict.fromkeys(columns) | {"PositionID": "P000002", "Ticker": "KEEP", "OptionStrategy": "Long Call", "Expiration": "2026-11-20", "Strike": 100, "Contracts": 1, "EntryPremium": 3, "Status": "OPEN"},
            ], columns=columns).to_csv(portfolio, index=False)
            journal = root / "journal.csv"
            pd.DataFrame([{"RecommendationID": "r-new", "RecommendationDate": "2026-09-18T10:00:00",
                "Ticker": "NEW", "option_strategy": "Long Call", "expiration": "2026-11-20",
                "strike": 50, "allocation_decision": "Allocate", "stop_loss_price": 1.6}]).to_csv(journal, index=False)
            before_statement = statement.read_bytes()
            result = sync_current_positions(statement, portfolio, journal)
            actual = pd.read_csv(portfolio)
            after_statement = statement.read_bytes()
        self.assertEqual(result["closed_position_ids"], ["P000001"])
        self.assertEqual(result["created_position_ids"], ["P000003"])
        self.assertEqual(result["open_positions"], 2)
        self.assertEqual(int(actual.loc[actual.Ticker == "NEW", "Contracts"].iloc[0]), 2)
        self.assertEqual(float(actual.loc[actual.Ticker == "KEEP", "CurrentPremium"].iloc[0]), 3.5)
        self.assertEqual(actual.loc[actual.Ticker == "OLD", "ExitReason"].iloc[0], "BROKER_RECONCILED_CLOSE")
        self.assertEqual(after_statement, before_statement)

    def test_current_position_sync_uses_broker_weighted_average_entry(self):
        statement_text = """Account Statement for X since 9/28/26 through 9/29/26

Account Trade History
,Exec Time,Spread,Side,Qty,Total Cost,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
,9/28/26 10:00:00,SINGLE,BUY,+2,0,TO OPEN,MRK,20 NOV 26,155,CALL,5.10,5.10,LMT
,9/29/26 10:00:00,SINGLE,BUY,+1,0,TO OPEN,MRK,20 NOV 26,155,CALL,4.40,4.40,LMT

Options
Symbol,Option Code,Exp,Strike,Type,Qty,Trade Price,Mark,Mark Value
MRK,MRK261120C155,20 NOV 26,155,CALL,+3,4.8667,5.475,$1642.50
,OVERALL TOTALS,,,,,,,$1642.50
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            statement = root / "statement.csv"
            statement.write_text(statement_text, encoding="utf-8")
            portfolio = root / "portfolio.csv"
            columns = ["PositionID", "RecommendationID", "BrokerPositionID", "Ticker",
                "OptionStrategy", "Expiration", "Strike", "Contracts", "EntryPremium",
                "EntryDate", "Status", "ExitDate", "ExitReason", "ExitPremium",
                "CurrentUnderlying", "CurrentPremium", "PnLPct", "AlphaVsSPY",
                "LastReviewed", "CurrentDTE", "UnderlyingReturnPct", "SPYReturnPct",
                "PeakPremium", "PeakPremiumDate", "RecommendedStop", "RecommendedStopDate",
                "ProfitProtectionStatus", "LockedProfitPct"]
            pd.DataFrame(columns=columns).to_csv(portfolio, index=False)
            journal = root / "journal.csv"
            pd.DataFrame([{"RecommendationID": "r-mrk", "RecommendationDate": "2026-09-28T09:00:00",
                "Ticker": "MRK", "option_strategy": "Long Call", "expiration": "2026-11-20",
                "strike": 155, "allocation_decision": "Allocate", "stop_loss_price": 4.0}]).to_csv(journal, index=False)
            sync_current_positions(statement, portfolio, journal)
            actual = pd.read_csv(portfolio).iloc[0]
        self.assertAlmostEqual(float(actual["EntryPremium"]), 4.8667)
        self.assertAlmostEqual(float(actual["PnLPct"]), 5.475 / 4.8667 - 1)


if __name__ == "__main__":
    unittest.main()
