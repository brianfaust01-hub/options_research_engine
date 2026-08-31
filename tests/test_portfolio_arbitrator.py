from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from portfolio_arbitrator import arbitrate_portfolio  # noqa: E402


def candidate(ticker, score=90, price=10, stop_pct=.10, execution=90):
    return {
        "ticker": ticker, "action": "Evaluate Options", "contracts": 1,
        "execution_entry_price": price, "premium": price,
        "stop_loss_pct": stop_pct, "stop_loss_price": price * (1 - stop_pct),
        "portfolio_score": score, "shadow_time_adjusted_score": score,
        "execution_score": execution, "earnings_status": "CONFIRMED",
        "earnings_allocation_override": False, "allocation_decision": "Watch",
        "PortfolioStatus": "NOT_ALLOCATED",
    }


def position(ticker, score=85, price=10, entry=10, contracts=1, pnl=0):
    return {
        "ticker": ticker, "contracts": contracts, "current_price": price,
        "entry_price": entry, "stop_loss": price * .90, "pnl_dollars": pnl,
        "latest_allocation_score": score, "position_recommendation": "HOLD",
        "position_reason": "thesis remains valid",
    }


class PortfolioArbitratorTests(unittest.TestCase):
    def test_cash_and_strong_candidate_opens(self):
        result = arbitrate_portfolio(pd.DataFrame([candidate("NEW", price=5)]), pd.DataFrame(), 15000)
        self.assertEqual(result.candidates.iloc[0]["portfolio_action"], "OPEN")

    def test_better_candidate_recycles_weakest_holding_when_cash_is_constrained(self):
        holdings = [position(f"H{i}", score=100 - i, price=2.4) for i in range(12)]
        holdings[-1]["latest_allocation_score"] = 70
        result = arbitrate_portfolio(
            pd.DataFrame([candidate("BETTER", score=110, price=2.4)]),
            pd.DataFrame(holdings), 3000,
        )
        self.assertEqual(result.candidates.iloc[0]["portfolio_action"], "OPEN")
        self.assertEqual(result.positions.iloc[-1]["portfolio_action"], "CLOSE")
        self.assertGreater(result.summary["capital_recycled"], 0)

    def test_strong_incumbent_holds_despite_new_candidate(self):
        holdings = [position(f"H{i}", score=100, price=1.2) for i in range(9)]
        holdings.append(position("KEEP", score=90, price=1.2))
        result = arbitrate_portfolio(
            pd.DataFrame([candidate("NEW", score=92, price=2.4)]),
            pd.DataFrame(holdings), 3000,
        )
        keep = result.positions[result.positions["ticker"].eq("KEEP")].iloc[0]
        self.assertEqual(keep["portfolio_action"], "HOLD")
        self.assertEqual(result.candidates.iloc[0]["portfolio_action"], "PASS")

    def test_candidate_below_quality_threshold_passes(self):
        result = arbitrate_portfolio(
            pd.DataFrame([candidate("WEAK", score=65)]), pd.DataFrame(), 15000
        )
        self.assertEqual(result.candidates.iloc[0]["portfolio_action"], "PASS")
        self.assertIn("below", result.candidates.iloc[0]["portfolio_action_reason"])

    def test_theme_concentration_rejects_otherwise_strong_candidate(self):
        rows = [candidate(ticker, score=score) for ticker, score in [
            ("AAPL", 99), ("MSFT", 98), ("GOOGL", 97), ("META", 96)
        ]]
        result = arbitrate_portfolio(pd.DataFrame(rows), pd.DataFrame(), 15000)
        rejected = result.candidates[result.candidates["portfolio_action"].eq("PASS")]
        self.assertEqual(len(rejected), 1)
        self.assertIn("theme/correlation", rejected.iloc[0]["portfolio_action_reason"])

    def test_risk_limit_retains_intentional_cash(self):
        rows = [candidate(f"R{i}", score=99 - i, stop_pct=.20) for i in range(10)]
        result = arbitrate_portfolio(pd.DataFrame(rows), pd.DataFrame(), 15000)
        self.assertLessEqual(result.summary["expected_loss_at_stops_pct"], .10)
        self.assertGreater(result.summary["intentional_cash_pct"], 0)
        self.assertIn("intentional", result.summary["intentional_cash_reason"])

    def test_independent_opportunities_deploy_more_than_old_three_trade_allocator(self):
        rows = [candidate(f"I{i}", score=99 - i) for i in range(8)]
        result = arbitrate_portfolio(pd.DataFrame(rows), pd.DataFrame(), 15000)
        self.assertEqual(int(result.candidates["allocation_decision"].eq("Allocate").sum()), 7)
        self.assertGreater(result.summary["capital_deployed"], 3000)
        self.assertLessEqual(result.summary["capital_utilization_pct"], .50)

    def test_profitable_but_deteriorated_position_closes(self):
        result = arbitrate_portfolio(
            pd.DataFrame(), pd.DataFrame([position("PROFIT", score=60, pnl=200)]), 15000
        )
        self.assertEqual(result.positions.iloc[0]["portfolio_action"], "CLOSE")

    def test_temporarily_down_strong_position_holds(self):
        result = arbitrate_portfolio(
            pd.DataFrame(), pd.DataFrame([position("DOWN", score=90, price=9, entry=10, pnl=-100)]), 15000
        )
        self.assertEqual(result.positions.iloc[0]["portfolio_action"], "HOLD")

    def test_utilization_and_nav_return_metrics(self):
        result = arbitrate_portfolio(
            pd.DataFrame(), pd.DataFrame([position("METRIC", score=90, price=11, entry=10, pnl=100)]), 15000
        )
        self.assertAlmostEqual(result.summary["capital_utilization_pct"], 1100 / 15000)
        self.assertAlmostEqual(result.summary["return_on_deployed_capital_pct"], .10)
        self.assertAlmostEqual(result.summary["return_on_total_nav_pct"], 100 / 15000)

    def test_same_ticker_increment_is_labeled_add(self):
        result = arbitrate_portfolio(
            pd.DataFrame([candidate("SAME", score=95, price=5)]),
            pd.DataFrame([position("SAME", score=90, price=5)]), 15000,
        )
        self.assertEqual(result.candidates.iloc[0]["portfolio_action"], "ADD")
        self.assertEqual(result.candidates.iloc[0]["PortfolioStatus"], "OPEN")
        self.assertEqual(result.candidates.iloc[0]["contracts"], 1)

    def test_add_never_exceeds_total_three_contract_ceiling(self):
        result = arbitrate_portfolio(
            pd.DataFrame([candidate("SAME", score=95, price=2)]),
            pd.DataFrame([position("SAME", score=90, price=2, contracts=1)]),
            15000,
        )
        self.assertEqual(result.candidates.iloc[0]["portfolio_action"], "ADD")
        self.assertEqual(result.candidates.iloc[0]["contracts"], 2)

    def test_oversized_multicontract_position_is_reduced(self):
        result = arbitrate_portfolio(
            pd.DataFrame(),
            pd.DataFrame([position("LARGE", score=90, price=10, contracts=2)]),
            15000,
        )
        self.assertEqual(result.positions.iloc[0]["portfolio_action"], "REDUCE")
        self.assertEqual(result.positions.iloc[0]["portfolio_target_contracts"], 1)

    def test_high_quality_affordable_candidate_receives_multiple_contracts(self):
        result = arbitrate_portfolio(
            pd.DataFrame([candidate("SCALE", score=95, price=2)]),
            pd.DataFrame(), 15000,
        )
        self.assertEqual(result.candidates.iloc[0]["contracts"], 3)
        self.assertEqual(result.candidates.iloc[0]["portfolio_target_contracts"], 3)

    def test_immaterial_candidate_passes_when_three_contracts_are_still_too_small(self):
        result = arbitrate_portfolio(
            pd.DataFrame([candidate("TINY", score=95, price=.50)]),
            pd.DataFrame(), 15000,
        )
        self.assertEqual(result.candidates.iloc[0]["portfolio_action"], "PASS")
        self.assertIn("material", result.candidates.iloc[0]["portfolio_action_reason"])

    def test_active_position_limit_bounds_manual_workload(self):
        rows = [candidate(f"SLOT{i}", score=110 - i, price=2) for i in range(14)]
        result = arbitrate_portfolio(pd.DataFrame(rows), pd.DataFrame(), 15000)
        self.assertLessEqual(result.summary["active_positions"], 10)
        self.assertTrue(
            result.candidates["portfolio_action_reason"].str.contains(
                "active-position limit"
            ).any()
        )


if __name__ == "__main__":
    unittest.main()
