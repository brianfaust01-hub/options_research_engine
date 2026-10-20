import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from research_score_calibration import audit_research_score, merge_research_components


class ResearchScoreCalibrationTests(unittest.TestCase):
    def fixture(self):
        rows = []
        for index, score in enumerate([60, 70, 80, 90] * 3):
            rows.append({
                "RecommendationID": f"r{index}",
                "_Date": pd.Timestamp("2026-09-24") + pd.Timedelta(days=index // 4),
                "_Direction": "BULLISH" if index % 2 else "BEARISH",
                "_Return": (score - 75) / 100,
                "ResearchScore": score,
                "AllocationDecision": "Allocate" if score == 90 else "No Allocation",
            })
        return pd.DataFrame(rows)

    def test_score_audit_detects_ranking_signal(self):
        result = audit_research_score(self.fixture())
        self.assertEqual(result["episode_count"], 12)
        self.assertGreater(result["research_score_spearman_return"], .9)
        self.assertGreater(result["research_score_win_auc"], .9)
        self.assertEqual(result["within_date_quartiles"][-1]["quartile"], "Q4 highest")

    def test_component_join_preserves_episode_count(self):
        episodes = self.fixture()[["RecommendationID", "_Date", "_Direction", "_Return", "ResearchScore", "AllocationDecision"]]
        journal = pd.DataFrame({
            "RecommendationID": ["r0", "r1"],
            "TrendScore": [20, 80],
        })
        merged = merge_research_components(episodes, journal)
        self.assertEqual(len(merged), len(episodes))
        self.assertEqual(int(merged["TrendScore"].notna().sum()), 2)


if __name__ == "__main__":
    unittest.main()
