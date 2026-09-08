from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import paper_portfolio  # noqa: E402


class PaperPortfolioSchemaTests(unittest.TestCase):
    def test_empty_timestamp_columns_accept_review_timestamp(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "paper_portfolio.csv"
            pd.DataFrame([{
                "PositionID": "P1",
                "Ticker": "ABC",
                "Status": "OPEN",
                "PeakPremiumDate": None,
                "RecommendedStopDate": None,
                "ProfitProtectionStatus": None,
            }]).to_csv(path, index=False)

            with patch.object(paper_portfolio, "PORTFOLIO_PATH", path):
                portfolio = paper_portfolio.load_portfolio()

            timestamp = "2026-09-08T10:53:43"
            portfolio.loc[portfolio["PositionID"].eq("P1"), "PeakPremiumDate"] = timestamp
            portfolio.loc[
                portfolio["PositionID"].eq("P1"), "RecommendedStopDate"
            ] = timestamp
            portfolio.loc[
                portfolio["PositionID"].eq("P1"), "ProfitProtectionStatus"
            ] = "RAISE STOP"

            self.assertEqual(portfolio.loc[0, "PeakPremiumDate"], timestamp)
            self.assertEqual(portfolio.loc[0, "RecommendedStopDate"], timestamp)
            self.assertEqual(portfolio.loc[0, "ProfitProtectionStatus"], "RAISE STOP")


if __name__ == "__main__":
    unittest.main()
