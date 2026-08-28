from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from hindsight_analytics import analyze_hindsight  # noqa: E402
from options_engine import score_contracts  # noqa: E402


class GreekObservationIntegrityTests(unittest.TestCase):
    def _chain(self):
        return pd.DataFrame([{
            "contractSymbol": "TEST", "strike": 100, "bid": 4.8, "ask": 5.2,
            "lastPrice": 5.0, "volume": 100, "openInterest": 1000,
            "impliedVolatility": .42, "schwabDelta": .47, "schwabGamma": .08,
            "schwabTheta": -.10, "schwabVega": .25, "schwabRho": .04,
        }])

    def test_broker_greeks_are_not_overwritten_by_estimates(self):
        expiration = str(date.today() + timedelta(days=60))
        row = score_contracts(self._chain(), 100.0, "call", expiration).iloc[0]
        self.assertEqual(row["broker_delta"], .47)
        self.assertEqual(row["broker_theta"], -.10)
        self.assertEqual(row["greeks_source"], "SCHWAB")
        self.assertEqual(row["delta"], row["estimated_delta"])
        self.assertEqual(row["theta"], row["estimated_theta"])
        self.assertAlmostEqual(row["theta_drag_pct_per_day"], .02)
        self.assertAlmostEqual(row["gamma_per_premium"], .016)
        self.assertAlmostEqual(row["vega_per_premium"], .05)
        self.assertEqual(row["iv_context_status"], "UNAVAILABLE_NO_HISTORY")

    def test_hindsight_exposes_four_shadow_calibration_horizons(self):
        rows = []
        for index in range(2):
            rows.append({
                "RecommendationID": f"R{index}", "RecommendationDate": "2026-08-01",
                "Ticker": "TEST", "Direction": "BULLISH", "BrokerDelta": .45,
                "ThetaDragPctPerDay": .02, "GammaPerPremium": .01,
                "VegaPerPremium": .05, "ImpliedVolatility": .40,
                "Horizon3DDirectionalReturnPct": .01, "Horizon3DStatus": "COMPLETE",
                "Horizon5DDirectionalReturnPct": .02, "Horizon5DStatus": "COMPLETE",
                "Horizon7DDirectionalReturnPct": .03, "Horizon7DStatus": "COMPLETE",
                "Horizon14DDirectionalReturnPct": .04, "Horizon14DStatus": "COMPLETE",
            })
        summary = analyze_hindsight(pd.DataFrame(rows))
        self.assertEqual(set(summary["greek_calibration_by_horizon"]), {"3D", "5D", "7D", "14D"})
        self.assertEqual(summary["iv_context"]["rank_status"], "UNAVAILABLE_NO_HISTORY")


if __name__ == "__main__":
    unittest.main()
