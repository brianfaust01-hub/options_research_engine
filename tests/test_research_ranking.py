import sys, unittest
from pathlib import Path
import pandas as pd
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path: sys.path.insert(0, str(SRC_ROOT))
from research_ranking import POLICY_VERSION, build_shadow_ledger, calculate_shadow_research_ranking

class ResearchRankingTests(unittest.TestCase):
    def test_bearish_components_are_directionally_normalized(self):
        result = calculate_shadow_research_ranking({"Direction": "Bearish", "ResearchScore": 85,
            "TrendScore": 0, "MomentumScore": 80, "MomentumDirection": "Bearish",
            "DirectionalConviction": 90, "time_edge_score": 70, "market_score": 100})
        self.assertTrue(result["ResearchRankingInputsComplete"])
        self.assertEqual(result["ResearchRankingDirectionalTrend"], 100)
        self.assertEqual(result["ResearchRankingScore"], 35.0)
        self.assertEqual(result["ResearchRankingPolicyVersion"], POLICY_VERSION)

    def test_missing_input_fails_closed(self):
        result = calculate_shadow_research_ranking({"Direction": "Bullish", "ResearchScore": 90})
        self.assertFalse(result["ResearchRankingInputsComplete"])
        self.assertIsNone(result["ResearchRankingScore"])

    def test_retrospective_ledger_does_not_mutate_source(self):
        source = pd.DataFrame([{"RecommendationID": "r1", "RecommendationDate": "2026-09-24",
            "ticker": "XYZ", "Direction": "Bullish",
            "ResearchScore": 90, "TrendScore": 100, "MomentumScore": 80,
            "MomentumDirection": "Bullish", "DirectionalConviction": 90, "time_edge_score": 70}])
        ledger = build_shadow_ledger(source)
        self.assertNotIn("ResearchRankingScore", source.columns)
        self.assertEqual(ledger.loc[0, "ResearchRankingMode"], "RETROSPECTIVE_SHADOW")
        self.assertEqual(ledger.loc[0, "ShadowResearchRank"], 1)
        self.assertTrue(ledger.loc[0, "ShadowResearchTwoStageTop3"])

if __name__ == "__main__": unittest.main()
