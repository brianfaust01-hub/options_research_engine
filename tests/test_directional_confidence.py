import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from research_engine import evaluate_strategies
from strategies.market_regime import evaluate_market_regime
from strategies.trend import evaluate_trend


class DirectionalConfidenceTests(unittest.TestCase):
    @staticmethod
    def _row(*, bullish: bool):
        return {
            "Close": 105.0 if bullish else 95.0,
            "SMA_20": 100.0,
            "SMA_50": 100.0,
            "SMA_200": 100.0,
            "Above_SMA_20": bullish,
            "Above_SMA_50": bullish,
            "Above_SMA_200": bullish,
            "MACD_Bullish": bullish,
            "RSI_14": 55.0 if bullish else 45.0,
            "Avg_Volume_20": 5_000_000,
        }

    def test_strong_bearish_trend_has_high_bearish_confidence(self):
        result = evaluate_trend(self._row(bullish=False))

        self.assertEqual(result.signal, "Bearish")
        self.assertEqual(result.trend, 0)
        self.assertEqual(result.confidence, 100)

    def test_strong_bearish_regime_has_high_bearish_confidence(self):
        result = evaluate_market_regime(self._row(bullish=False))

        self.assertEqual(result.signal, "Bearish")
        self.assertEqual(result.risk, 0)
        self.assertEqual(result.confidence, 100)

    def test_consensus_confidence_is_high_in_both_directions(self):
        bullish = evaluate_strategies(self._row(bullish=True))
        bearish = evaluate_strategies(self._row(bullish=False))

        self.assertEqual(bullish["Direction"], "Bullish")
        self.assertEqual(bearish["Direction"], "Bearish")
        self.assertGreaterEqual(bullish["StrategyScore"], 70)
        self.assertGreaterEqual(bearish["StrategyScore"], 70)
        self.assertEqual(bullish["ResearchScore"], bullish["StrategyScore"])
        self.assertEqual(bearish["ResearchScore"], bearish["StrategyScore"])


if __name__ == "__main__":
    unittest.main()
