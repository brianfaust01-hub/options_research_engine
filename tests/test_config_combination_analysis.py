import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from config_combination_analysis import analyze_combinations


class ConfigCombinationAnalysisTests(unittest.TestCase):
    def test_requires_positive_early_and_late_evidence(self):
        rows = []
        for index in range(16):
            rows.append({
                "_Date": pd.Timestamp("2026-09-24") + pd.Timedelta(days=index),
                "_Return": .03 if index % 3 else -.01,
                "_AdjustedReturn": .02 if index % 3 else -.005,
                "_Direction": "BULLISH" if index % 2 else "BEARISH",
                "ResearchScore": 75,
                "TimeEdgeScore": 85,
                "ExecutionScore": 82,
                "ContractScore": 75,
                "HorizonFitScore": 85,
                "BrokerDelta": .55,
                "ImpliedVolatility": .30,
                "ThetaDragPctPerDay": .008,
                "GammaPerPremium": .015,
                "VegaPerPremium": .07,
            })
        result = analyze_combinations(pd.DataFrame(rows))
        matching = [
            row for row in result["stable"]
            if row["order"] == 2
            and row["field_1"] == "absolute_delta"
            and row["field_2"] == "theta_drag_pct_per_day"
        ]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["episodes"], 16)
        self.assertGreater(matching[0]["early_adjusted_average_return"], 0)
        self.assertGreater(matching[0]["late_adjusted_average_return"], 0)

    def test_rejects_profile_that_only_works_in_early_half(self):
        rows = []
        for index in range(16):
            rows.append({
                "_Date": pd.Timestamp("2026-09-24") + pd.Timedelta(days=index),
                "_Return": .02 if index < 8 else -.02,
                "_AdjustedReturn": .02 if index < 8 else -.02,
                "_Direction": "BEARISH",
                "ResearchScore": 75,
                "TimeEdgeScore": 85,
                "ExecutionScore": 82,
                "ContractScore": 75,
                "HorizonFitScore": 85,
                "BrokerDelta": .55,
                "ImpliedVolatility": .30,
                "ThetaDragPctPerDay": .008,
                "GammaPerPremium": .015,
                "VegaPerPremium": .07,
            })
        result = analyze_combinations(pd.DataFrame(rows))
        self.assertFalse(result["stable"])


if __name__ == "__main__":
    unittest.main()
