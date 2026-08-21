from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from data_quality import assess_observation  # noqa: E402
from hindsight_data_audit import find_case_collisions  # noqa: E402
from opportunity_engine import evaluate_opportunities  # noqa: E402
from research_engine import evaluate_strategies  # noqa: E402
from snapshot_writer import write_observation_snapshot  # noqa: E402
from trade_constructor import construct_trade  # noqa: E402
from trade_journal import _build_completed_observation  # noqa: E402


class HindsightIntegrityTests(unittest.TestCase):
    def _research_row(self) -> pd.Series:
        return pd.Series(
            {
                "Ticker": "TEST",
                "Close": 100.0,
                "SMA_20": 98.0,
                "SMA_50": 95.0,
                "SMA_200": 90.0,
                "Above_SMA_20": True,
                "Above_SMA_50": True,
                "Above_SMA_200": True,
                "RSI_14": 55.0,
                "MACD_Bullish": True,
                "Avg_Volume_20": 6_000_000,
            }
        )

    def test_research_score_is_explicit_alias_without_behavior_change(self):
        result = evaluate_strategies(self._research_row())

        self.assertIn(result["MomentumDirection"], {"Bullish", "Bearish"})

        self.assertEqual(result["ResearchScore"], result["StrategyScore"])

    def test_trade_carries_opportunity_context_for_pass_record(self):
        row = self._research_row()
        for key, value in {
                "StrategyScore": 50,
                "ResearchScore": 50,
                "TrendScore": 60,
                "MomentumScore": 45,
                "LiquidityScore": 10,
                "StrategyReasons": "fixture",
                "HoldingPeriodDays": 45,
                "OpportunityType": "No Clear Edge",
                "Action": "Pass",
                "OpportunityScore": 40,
                "BullishScore": 40,
                "BearishScore": 20,
                "DirectionalConviction": 20,
        }.items():
            row[key] = value

        trade = construct_trade(row)

        self.assertEqual(trade.research_score, 50)
        self.assertEqual(trade.opportunity_score, 40)
        self.assertEqual(trade.bullish_score, 40)
        self.assertEqual(trade.bearish_score, 20)
        self.assertEqual(trade.directional_conviction, 20)

    def test_opportunity_engine_propagates_scores_into_trade(self):
        row = self._research_row()

        for key, value in {
            "StrategyScore": 40,
            "ResearchScore": 40,
            "TrendScore": 40,
            "MomentumScore": 40,
            "LiquidityScore": 10,
            "StrategyReasons": "fixture",
            "HoldingPeriodDays": 45,
        }.items():
            row[key] = value

        trade = evaluate_opportunities(row)

        self.assertEqual(trade.action, "Pass")
        self.assertEqual(trade.research_score, 40)
        self.assertEqual(trade.opportunity_score, 45)
        self.assertEqual(trade.bullish_score, 0)
        self.assertEqual(trade.bearish_score, 45)
        self.assertEqual(trade.directional_conviction, 45)

    def test_completed_observation_is_canonical_and_complete(self):
        observation = _build_completed_observation(
            trade_row={
                "ticker": "TEST",
                "action": "Pass",
                "research_score": 50,
                "opportunity_score": 40,
                "bullish_score": 40,
                "bearish_score": 20,
                "directional_conviction": 20,
            },
            research_row={"Ticker": "TEST", "Close": 100.0},
            market_context={},
            market_breadth={},
            recommendation_date="2026-08-21T00:00:00",
        )

        self.assertEqual(observation["ResearchScore"], 50)
        self.assertEqual(observation["OpportunityScore"], 40)
        self.assertEqual(observation["DataQualityStatus"], "COMPLETE")
        self.assertEqual(observation["DataQualityIssues"], [])

    def test_incomplete_observation_is_preserved_and_classified(self):
        assessed = assess_observation(
            {"ticker": "LEGACY", "action": "Pass"}
        )

        self.assertEqual(assessed["DataQualityStatus"], "PARTIAL")
        self.assertIn(
            "MISSING_ResearchScore",
            assessed["DataQualityIssues"],
        )
        self.assertEqual(assessed["ticker"], "LEGACY")

    def test_snapshot_v4_records_quality_without_mutating_input(self):
        observation = {"ticker": "LEGACY", "action": "Pass"}

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "snapshot_writer.SNAPSHOT_DIRECTORY",
                Path(directory),
            ):
                result = write_observation_snapshot(observation)

            snapshot = json.loads(
                Path(result["file_path"]).read_text(encoding="utf-8")
            )

        self.assertEqual(result["schema_version"], "4.0")
        self.assertEqual(snapshot["data_quality_status"], "PARTIAL")
        self.assertEqual(observation, {"ticker": "LEGACY", "action": "Pass"})

    def test_case_aliases_are_reported_without_rewriting_schema(self):
        collisions = find_case_collisions(
            ["ticker", "action", "Ticker"]
        )

        self.assertEqual(collisions, [["Ticker", "ticker"]])

    def test_controlled_v4_observation_end_to_end(self):
        row = pd.Series(
            {
                "Ticker": "CONTROLLED",
                "Close": 90.0,
                "SMA_20": 95.0,
                "SMA_50": 100.0,
                "SMA_200": 110.0,
                "Above_SMA_20": False,
                "Above_SMA_50": False,
                "Above_SMA_200": False,
                "RSI_14": 55.0,
                "MACD_Bullish": False,
                "Avg_Volume_20": 6_000_000,
            }
        )

        for key, value in evaluate_strategies(row).items():
            row[key] = value

        trade = evaluate_opportunities(row)
        self.assertEqual(trade.action, "Watch")

        observation = _build_completed_observation(
            trade_row=asdict(trade),
            research_row=row.to_dict(),
            market_context={
                "market_regime": "Controlled Test",
                "risk_mode": "Test",
            },
            market_breadth={
                "breadth_score": 0,
                "breadth_regime": "Controlled Test",
                "breadth_reasons": ["temporary fixture"],
            },
            recommendation_date="2026-08-21T00:00:00",
        )

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "snapshot_writer.SNAPSHOT_DIRECTORY",
                Path(directory),
            ):
                result = write_observation_snapshot(observation)

            snapshot = json.loads(
                Path(result["file_path"]).read_text(encoding="utf-8")
            )

        stored = snapshot["observation"]

        for field in (
            "ResearchScore",
            "OpportunityScore",
            "BullishScore",
            "BearishScore",
            "DirectionalConviction",
        ):
            self.assertIsNotNone(stored[field])

        self.assertEqual(snapshot["schema_version"], "4.0")
        self.assertEqual(snapshot["data_quality_status"], "COMPLETE")
        self.assertEqual(stored["DataQualityStatus"], "COMPLETE")
        self.assertEqual(stored["DataQualityIssues"], [])
        self.assertEqual(
            stored["RecommendationTruthSource"],
            "PROJECT_STONKS_SYSTEM",
        )
        self.assertEqual(
            stored["BrokerReconciliationStatus"],
            "NOT_RECONCILED",
        )


if __name__ == "__main__":
    unittest.main()
