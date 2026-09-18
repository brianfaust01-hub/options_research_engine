import csv
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from intraday_option_paths import collect_intraday, sampled_path, session_bounds, session_health

NOW = datetime(2026, 9, 18, 14, 30, tzinfo=timezone.utc)
BOUNDS = (NOW.replace(hour=13, minute=30), NOW.replace(hour=20, minute=0))


def quote(age=0, bid=1.2):
    return {"realtime": True, "quote": {"bidPrice": bid, "askPrice": bid + .1,
        "quoteTime": (NOW - timedelta(seconds=age)).timestamp() * 1000, "volatility": 40}}


class IntradayTests(unittest.TestCase):
    def journal(self, root):
        path = root / "journal.csv"
        rows = [{"RecommendationID": str(i), "RecommendationDate": "2026-09-18T14:00:00+00:00",
            "Ticker": "TEST", "option_strategy": direction, "contract_symbol": symbol,
            "expiration": "2026-11-20", "allocation_decision": allocation,
            "PolicyEraID": "PE-2026-09-08", "PolicyEvidenceFingerprint": "abc",
            "execution_entry_price": "1.3"}
            for i, direction, symbol, allocation in [(1, "Long Call", "TEST  261120C00100000", "Allocate"),
                (2, "Long Put", "TEST  261120P00100000", "No Allocation")]]
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return path

    def read(self, output):
        with gzip.open(next(output.glob("*/*.json.gz")), "rt") as handle:
            return json.load(handle)

    def test_forward_compressed_lineage_immutable_no_input_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = self.journal(root)
            original = journal.read_bytes()
            calls = []
            def fetch(symbols, timeout_seconds):
                calls.append((symbols, timeout_seconds))
                return {symbol: quote() for symbol in symbols}
            out = root / "out"
            result = collect_intraday(journal, out, now=NOW, bounds=BOUNDS, fetch=fetch)
            self.assertEqual(result["status"], "COMPLETE")
            bundle = self.read(out)
            self.assertEqual(len(bundle["contracts"]), 2)
            self.assertEqual(bundle["contracts"][0]["recommendations"][0]["policy_evidence_fingerprint"], "abc")
            self.assertFalse(bundle["eligible_for_empirical_calibration"])
            artifact = next(out.glob("*/*.json.gz"))
            before = artifact.read_bytes()
            collect_intraday(journal, out, now=NOW, bounds=BOUNDS, fetch=fetch)
            self.assertEqual(artifact.read_bytes(), before)
            self.assertEqual(journal.read_bytes(), original)
            self.assertLessEqual(calls[0][1], 5)

    def test_calendar_holiday_weekend_early_close_and_dst(self):
        for moment in [datetime(2026, 9, 7, 15, tzinfo=timezone.utc),
                       datetime(2026, 9, 19, 15, tzinfo=timezone.utc)]:
            self.assertIsNone(session_bounds(moment))
        early = session_bounds(datetime(2026, 11, 27, 16, tzinfo=timezone.utc))
        self.assertEqual(early[1].hour, 18)  # 13:00 Eastern
        summer = session_bounds(NOW)
        winter = session_bounds(datetime(2026, 12, 1, 16, tzinfo=timezone.utc))
        self.assertEqual(summer[0].hour, 13)
        self.assertEqual(winter[0].hour, 14)

    def test_closed_session_never_fetches_or_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "absent"
            result = collect_intraday("missing.csv", out, now=BOUNDS[1], bounds=BOUNDS,
                fetch=lambda *a, **k: self.fail("No off-hours fetch"))
            self.assertEqual(result["status"], "MARKET_CLOSED")
            self.assertFalse(out.exists())

    def test_stale_future_missing_and_failed_quotes_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = self.journal(root)
            for index, age in enumerate([61, -1]):
                out = root / str(index)
                result = collect_intraday(journal, out, now=NOW, bounds=BOUNDS,
                    fetch=lambda symbols, **k: {s: quote(age) for s in symbols})
                self.assertEqual(result["status"], "PARTIAL")
                self.assertFalse(self.read(out)["observations"][0]["eligible_for_sampled_returns"])
            def failure(*args, **kwargs):
                raise TimeoutError("credential-bearing fixture detail must not escape")
            with patch("builtins.print") as printed:
                collect_intraday(journal, root / "failed", now=NOW, bounds=BOUNDS, fetch=failure)
            self.assertNotIn("credential-bearing", str(printed.call_args_list))
            self.assertEqual(self.read(root / "failed")["observations"][0]["quote_status"], "FETCH_FAILED")

    def test_budget_rotation_and_gap_health(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = self.journal(root)
            times = iter([0, 0, 31, 31])
            result = collect_intraday(journal, root / "out", now=NOW, bounds=BOUNDS,
                batch_size=1, clock=lambda: next(times), fetch=lambda s, **k: {s[0]: quote()})
            self.assertEqual(result["quote_status_counts"]["NOT_SAMPLED_BUDGET"], 1)
            health = session_health(root / "out", "2026-09-18", now=NOW + timedelta(minutes=1))
            self.assertGreater(len(health["absent_slots"]), 0)
            self.assertEqual(health["partial_or_empty_slots"], 1)
            (root / "out" / "2026-09-18" / "sample_corrupt.json.gz").write_bytes(b"bad")
            self.assertEqual(len(session_health(root / "out", "2026-09-18", now=NOW + timedelta(minutes=1))["corrupt_artifacts"]), 1)

    def test_paths_use_bid_ordered_returns_not_fills_or_true_first_event(self):
        def point(seconds, bid, status="OBSERVED"):
            return {"observed_at": (NOW + timedelta(seconds=seconds)).isoformat(),
                "quote_at": (NOW + timedelta(seconds=seconds)).isoformat(),
                "bid": bid, "quote_status": status}
        result = sampled_path([point(240, 1.5), point(60, .8), point(120, 2, "STALE_QUOTE")],
            entry_at=NOW, entry_price=1, stop_price=.9, target_price=1.4)
        self.assertEqual(result["first_observed_hit"]["event"], "STOP_OBSERVED")
        self.assertAlmostEqual(result["points"][0]["return"], -.2)
        self.assertEqual(len(result["gaps"]), 1)
        self.assertFalse(result["eligible_for_empirical_calibration"])
        self.assertEqual(result["true_first_event"], "INDETERMINATE_BETWEEN_SAMPLES")


if __name__ == "__main__":
    unittest.main()
