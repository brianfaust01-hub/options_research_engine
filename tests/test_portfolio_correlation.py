from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from portfolio_correlation import build_correlation_evidence, write_correlation_evidence


class PortfolioCorrelationTests(unittest.TestCase):
    def setUp(self):
        dates = pd.bdate_range("2026-01-01", periods=70)
        changes = np.linspace(.001, .01, len(dates) - 1)
        base = pd.Series(100 * np.r_[1.0, (1 + changes).cumprod()], index=dates)
        inverse = pd.Series(100 * np.r_[1.0, (1 - changes).cumprod()], index=dates)
        self.prices = pd.concat({
            "AAA": pd.DataFrame({"Close": base}),
            "BBB": pd.DataFrame({"Close": base * 2}),
            "CCC": pd.DataFrame({"Close": inverse}),
        }, axis=1)

    def test_direction_adjustment_and_holding_summary(self):
        candidates = pd.DataFrame([
            {"ticker": "AAA", "action": "Evaluate Options", "option_strategy": "Long Call", "RecommendationID": "A"},
            {"ticker": "CCC", "action": "Evaluate Options", "option_strategy": "Long Put", "RecommendationID": "C"},
        ])
        positions = pd.DataFrame([
            {"ticker": "BBB", "option_strategy": "Long Call"},
        ])
        enriched, pairs = build_correlation_evidence(candidates, positions, self.prices)
        self.assertEqual(len(pairs), 3)
        self.assertEqual(enriched.loc[0, "correlation_evidence_status"], "MEASURED")
        self.assertAlmostEqual(enriched.loc[0, "max_abs_correlation_to_holdings"], 1.0)
        self.assertEqual(enriched.loc[0, "most_correlated_holding"], "BBB")
        self.assertGreater(enriched.loc[1, "max_direction_adjusted_correlation_to_holdings"], 0.9)

    def test_writer_preserves_long_form_evidence(self):
        frame = pd.DataFrame([{"LeftTicker": "AAA", "RightTicker": "BBB", "OverlapDays": 60}])
        with tempfile.TemporaryDirectory(dir=ROOT / ".test-tmp") as directory:
            output = write_correlation_evidence(frame, Path(directory) / "pairs.csv")
            self.assertTrue(output.exists())
            self.assertEqual(pd.read_csv(output).iloc[0]["OverlapDays"], 60)

    def test_single_candidate_without_holdings_is_explicit(self):
        candidates = pd.DataFrame([
            {"ticker": "AAA", "action": "Evaluate Options", "option_strategy": "Long Call"},
        ])
        enriched, pairs = build_correlation_evidence(
            candidates, pd.DataFrame(), self.prices
        )
        self.assertTrue(pairs.empty)
        self.assertEqual(enriched.loc[0, "correlation_evidence_status"], "NO_HOLDINGS")
