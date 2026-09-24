from pathlib import Path
import sys
import unittest

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from decision_enrichment import enrich_decisions
from portfolio_allocator import allocate_portfolio
from portfolio_arbitrator import arbitrate_portfolio
from portfolio_exposure import add_exposure_fields, summarize_allocated_exposure
from weekly_scan import build_trade_frame


class EmptyCandidatePipelineTests(unittest.TestCase):
    def test_zero_recommendations_complete_candidate_pipeline(self):
        context = {"market_regime": "Neutral", "risk_mode": "Selective",
                   "allocation_bias": "Balanced", "market_score": 50}
        trades = build_trade_frame([])
        trades = allocate_portfolio(trades, context)
        trades = add_exposure_fields(trades)
        trades = enrich_decisions(trades, pd.DataFrame())
        arbitration = arbitrate_portfolio(
            candidates=trades, positions=pd.DataFrame(), account_nav=15000,
            market_context=context,
            market_breadth={"breadth_regime": "Neutral", "breadth_score": 50},
        )
        result = arbitration.candidates
        for column in ("ticker", "sector", "allocation_decision", "action",
                       "time_edge_score", "portfolio_action"):
            self.assertIn(column, result.columns)
        self.assertTrue(result.empty)
        self.assertEqual(arbitration.summary["positions_opened"], 0)
        self.assertEqual(summarize_allocated_exposure(result)["warnings"], [])


if __name__ == "__main__":
    unittest.main()
