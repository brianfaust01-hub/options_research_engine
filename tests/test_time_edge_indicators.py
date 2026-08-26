from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from indicators import calculate_indicators_for_ticker  # noqa: E402


class TimeEdgeIndicatorTests(unittest.TestCase):
    def test_speed_inputs_are_captured_for_hindsight(self):
        index = pd.bdate_range("2025-10-01", periods=220)
        close = pd.Series(np.linspace(80, 120, 220), index=index)
        close.iloc[-1] += 4
        frame = pd.DataFrame({
            "Close": close,
            "High": close + 1,
            "Low": close - 1,
            "Volume": np.linspace(1_000_000, 2_500_000, 220),
        })
        result = calculate_indicators_for_ticker("FAST", frame)
        for field in (
            "Return1D", "Return3D", "Return5D", "PriceAccelerationATR",
            "VolumeRatio20", "FreshBreakout20", "FreshBreakdown20",
            "SignalAgeDays",
        ):
            self.assertIn(field, result)
        self.assertTrue(result["FreshBreakout20"])
        self.assertGreater(result["PriceAccelerationATR"], 0)


if __name__ == "__main__":
    unittest.main()
