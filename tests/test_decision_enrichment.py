from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from decision_enrichment import enrich_decisions  # noqa: E402


class DecisionEnrichmentTests(unittest.TestCase):
    def _trades(self):
        return pd.DataFrame([{
            "ticker": "FAST", "allocation_decision": "Allocate",
            "PortfolioStatus": "OPEN", "portfolio_score": 90,
            "allocation_rank": 1,
            "institutional_trade_score": 92, "execution_score": 95,
            "directional_conviction": 90, "execution_entry_price": 2,
            "premium": 1.95, "spread_pct": .02,
        }])

    def _research(self):
        return pd.DataFrame([{
            "Ticker": "FAST", "MomentumScore": 90, "TrendScore": 90,
            "PriceAccelerationATR": 2.0, "VolumeRatio20": 2.0,
            "FreshBreakout20": True, "FreshBreakdown20": False,
            "SignalAgeDays": 1,
        }])

    def test_fast_trade_gets_shadow_profiles_without_changing_contracts(self):
        result = enrich_decisions(
            self._trades(), self._research(), as_of=date(2026, 8, 25),
            earnings_provider=lambda _: date(2026, 10, 20),
        )
        self.assertEqual(result.loc[0, "expected_move_window_days"], 5)
        self.assertGreater(result.loc[0, "shadow_aggressive_contracts"], 0)
        self.assertEqual(result.loc[0, "allocation_decision"], "Allocate")
        self.assertEqual(result.loc[0, "earnings_status"], "CONFIRMED")

    def test_earnings_inside_thesis_window_blocks_allocation(self):
        result = enrich_decisions(
            self._trades(), self._research(), as_of=date(2026, 8, 25),
            earnings_provider=lambda _: date(2026, 8, 28),
        )
        self.assertTrue(result.loc[0, "earnings_allocation_override"])
        self.assertEqual(result.loc[0, "allocation_decision"], "Watch")
        self.assertEqual(result.loc[0, "PortfolioStatus"], "NOT_ALLOCATED")

    def test_unknown_earnings_is_explicit_but_does_not_guess(self):
        result = enrich_decisions(
            self._trades(), self._research(), as_of=date(2026, 8, 25),
            earnings_provider=lambda _: None,
        )
        self.assertEqual(result.loc[0, "earnings_status"], "UNKNOWN")
        self.assertEqual(result.loc[0, "allocation_decision"], "Allocate")

    def test_blocked_trade_promotes_next_ranked_candidate(self):
        trades = pd.concat([
            self._trades(),
            self._trades().assign(
                ticker="NEXT", allocation_decision="Watch",
                PortfolioStatus="NOT_ALLOCATED", allocation_rank=2,
                portfolio_score=85,
            ),
        ], ignore_index=True)
        research = pd.concat([
            self._research(),
            self._research().assign(Ticker="NEXT"),
        ], ignore_index=True)
        dates = {"FAST": date(2026, 8, 28), "NEXT": date(2026, 11, 1)}
        result = enrich_decisions(
            trades, research, as_of=date(2026, 8, 25),
            earnings_provider=lambda ticker: dates[ticker],
        )
        self.assertEqual(result.loc[0, "allocation_decision"], "Watch")
        self.assertEqual(result.loc[1, "allocation_decision"], "Allocate")


if __name__ == "__main__":
    unittest.main()
