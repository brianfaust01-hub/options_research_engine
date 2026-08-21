from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from option_selector import select_best_contract  # noqa: E402
from options_engine import (  # noqa: E402
    get_option_chain_snapshot,
    get_target_expirations,
)
from pipeline_metrics import (  # noqa: E402
    get_pipeline_metrics,
    reset_pipeline_metrics,
)


class OptionSelectorLatencyTests(unittest.TestCase):
    def _contracts(self) -> list[dict]:
        return [
            {
                "Expiration": str(date.today() + timedelta(days=45)),
                "Symbol": "TEST_45",
            },
            {
                "Expiration": str(date.today() + timedelta(days=60)),
                "Symbol": "TEST_60",
            },
        ]

    def test_target_expirations_reuse_supplied_chain_snapshot(self):
        with patch(
            "options_engine.get_option_expirations",
            side_effect=AssertionError("unexpected network fetch"),
        ):
            expirations = get_target_expirations(
                "TEST",
                normalized_contracts=self._contracts(),
            )

        self.assertEqual(len(expirations), 2)

    def test_chain_snapshot_preserves_retry_behavior_and_counts_attempts(self):
        reset_pipeline_metrics()

        with (
            patch(
                "options_engine.get_normalized_option_chain",
                side_effect=[TimeoutError("fixture"), self._contracts()],
            ),
            patch("options_engine.time.sleep"),
        ):
            contracts = get_option_chain_snapshot("TEST", "CALL")

        self.assertEqual(contracts, self._contracts())
        self.assertEqual(
            get_pipeline_metrics()["counts"]["option_chain_requests"],
            2,
        )

    @patch("option_selector.get_option_chain_snapshot", return_value=[])
    @patch("option_selector.get_normalized_quote", return_value={"Mark": 100})
    def test_partial_market_data_returns_no_contract(
        self,
        normalized_quote,
        chain_snapshot,
    ):
        selected = select_best_contract(
            "TEST", "Long Put Candidate", 45
        )

        self.assertIsNone(selected)

    @patch("option_selector.score_contracts")
    @patch("option_selector.get_option_chain_snapshot")
    @patch("option_selector.get_normalized_quote")
    def test_selector_fetches_one_chain_snapshot_per_ticker(
        self,
        normalized_quote,
        normalized_chain,
        score_contracts,
    ):
        normalized_quote.return_value = {"Mark": 100.0}
        normalized_chain.return_value = self._contracts()

        def scored_frame(chain, stock_price, option_type, expiration):
            dte = (date.fromisoformat(expiration) - date.today()).days
            return pd.DataFrame(
                [
                    {
                        "contractSymbol": f"TEST_{dte}",
                        "strike": 100.0,
                        "Expiration": expiration,
                        "DTE": dte,
                        "mid": 1.0,
                        "Executable": True,
                        "ContractScore": 90,
                        "PremiumPctOfStock": 0.01,
                    }
                ]
            )

        score_contracts.side_effect = scored_frame

        selected = select_best_contract(
            ticker="TEST",
            opportunity_type="Long Call Candidate",
            expected_holding_days=45,
        )

        self.assertIsNotNone(selected)
        self.assertEqual(normalized_quote.call_count, 1)
        self.assertEqual(normalized_chain.call_count, 1)
        self.assertEqual(score_contracts.call_count, 2)


if __name__ == "__main__":
    unittest.main()
