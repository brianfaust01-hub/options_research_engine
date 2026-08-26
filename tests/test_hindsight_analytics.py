from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hindsight_analytics import (  # noqa: E402
    analyze_hindsight,
    build_thesis_episodes,
    generate_hindsight_analytics,
)
from research_hindsight import _evaluate_fixed_horizon  # noqa: E402


class FixedHorizonTests(unittest.TestCase):
    def test_exact_trading_horizon_and_bearish_direction(self):
        dates = pd.bdate_range("2026-08-03", periods=8)
        prices = pd.Series([100, 99, 98, 97, 96, 95, 94, 93], index=dates)
        spy = pd.Series([100, 100, 101, 101, 102, 102, 103, 103], index=dates)

        result = _evaluate_fixed_horizon(
            ticker_prices=prices,
            spy_prices=spy,
            recommendation_date=pd.Timestamp("2026-08-03"),
            entry_price=100,
            direction="BEARISH",
            trading_days=5,
        )

        self.assertEqual(result["Horizon5DStatus"], "COMPLETE")
        self.assertAlmostEqual(result["Horizon5DDirectionalReturnPct"], .05)
        self.assertEqual(result["Horizon5DThesisResult"], "CORRECT")
        self.assertEqual(result["Horizon5DMagnitudeResult"], "MEANINGFUL_WIN")
        self.assertEqual(result["Horizon5DFirstThresholdEvent"], "FAVORABLE_FIRST")

    def test_incomplete_horizon_is_not_scored(self):
        dates = pd.bdate_range("2026-08-03", periods=3)
        prices = pd.Series([100, 101, 102], index=dates)
        result = _evaluate_fixed_horizon(
            prices, prices, pd.Timestamp("2026-08-03"), 100, "BULLISH", 3
        )
        self.assertEqual(result["Horizon3DStatus"], "IN_PROGRESS")
        self.assertIsNone(result["Horizon3DDirectionalReturnPct"])


class CredibilityAnalyticsTests(unittest.TestCase):
    def _frame(self):
        rows = []
        for recommendation_id, ticker, date, direction, result in [
            ("A1", "AAA", "2026-08-03", "BULLISH", .02),
            ("A2", "AAA", "2026-08-04T10:30:00.123456", "BULLISH", .03),
            ("A3", "AAA", "2026-08-20", "BULLISH", -.02),
            ("B1", "BBB", "2026-08-03", "BEARISH", .01),
        ]:
            rows.append({
                "RecommendationID": recommendation_id,
                "RecommendationDate": date,
                "Ticker": ticker,
                "Direction": direction,
                "Confidence": 85,
                "Horizon7DStatus": "COMPLETE",
                "Horizon7DDirectionalReturnPct": result,
                "Horizon7DAlphaVsSPY": result - .005,
            })
        return pd.DataFrame(rows)

    def test_repeated_thesis_is_one_episode_until_reset(self):
        episodes = build_thesis_episodes(self._frame(), reset_days=7)
        aaa = episodes[episodes["Ticker"] == "AAA"]
        self.assertEqual(aaa["ThesisEpisodeID"].nunique(), 2)
        self.assertEqual(episodes["ThesisEpisodeID"].nunique(), 3)

    def test_mixed_timestamp_formats_preserve_date_cohorts(self):
        result = analyze_hindsight(self._frame())
        self.assertEqual(result["counts"]["recommendation_date_cohorts"], 3)

    def test_raw_and_episode_metrics_are_separate(self):
        result = analyze_hindsight(self._frame())
        self.assertEqual(result["raw_primary"]["evaluated"], 4)
        self.assertEqual(result["episode_primary"]["evaluated"], 3)
        self.assertEqual(result["counts"]["thesis_episodes"], 3)
        self.assertEqual(result["horizons"]["7D"]["win_rate"], .75)
        self.assertEqual(result["horizons"]["7D"]["sample_status"], "PRELIMINARY")

    def test_generation_writes_only_requested_output_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "research_hindsight_fixture.csv"
            processed = root / "processed"
            reports = root / "reports"
            self._frame().to_csv(source, index=False)
            result = generate_hindsight_analytics(source, processed, reports)
            self.assertTrue(Path(result["json_path"]).exists())
            self.assertTrue(Path(result["report_path"]).exists())
            report = Path(result["report_path"]).read_text(encoding="utf-8")
            self.assertIn("Raw vs Deduplicated", report)
            self.assertIn("No production scoring", report)


if __name__ == "__main__":
    unittest.main()
