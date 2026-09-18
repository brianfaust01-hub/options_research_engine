from datetime import datetime, timedelta, timezone
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from option_observation_collector import collect, normalize_quote, tracked_contracts
from daily_run import collect_research_observations

NOW = datetime(2026, 9, 18, 14, 30, tzinfo=timezone.utc)


def security(bid=1.2, ask=1.3, age=0, **extra):
    return {"realtime": True, "quote": {"bidPrice": bid, "askPrice": ask,
        "quoteTime": (NOW - timedelta(seconds=age)).timestamp() * 1000,
        "volatility": 39.5, **extra}}


class OptionObservationTests(unittest.TestCase):
    def journal(self, root):
        path = root / "journal.csv"
        rows = [{"RecommendationID": str(i), "RecommendationDate": "2026-09-17T14:00:00+00:00",
            "Ticker": ticker, "option_strategy": strategy,
            "contract_symbol": symbol, "expiration": "2026-11-20",
            "allocation_decision": decision, "PolicyEraID": "PE-2026-09-08"}
            for i, ticker, strategy, symbol, decision in [
                (1, "A", "Long Call", "A     261120C00100000", "Allocate"),
                (2, "B", "Long Put", "B     261120P00100000", "No Allocation"),
                (3, "B", "Long Put", "B     261120P00100000", "Watch"),
                (4, "C", "Long Call", "", "No Allocation")]]
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_market_freshness_and_iv_units(self):
        good = normalize_quote(security(), NOW)
        self.assertEqual(good["quote_status"], "OBSERVED")
        self.assertAlmostEqual(good["iv_decimal"], .395)
        self.assertEqual(good["intraday_exit_path_status"], "INSUFFICIENT_SAMPLING")
        for raw, expected in [({}, "MISSING_QUOTE"),
                (security(bid=2), "INVALID_MARKET"),
                (security(age=901), "STALE_QUOTE"),
                (security(quoteTime=None), "UNKNOWN_QUOTE_TIME"),
                (security(age=-120), "INVALID_QUOTE_TIME")]:
            result = normalize_quote(raw, NOW)
            self.assertEqual(result["quote_status"], expected)
            self.assertFalse(result["eligible_for_sampled_returns"])
        delayed = security()
        delayed["realtime"] = False
        self.assertEqual(normalize_quote(delayed, NOW)["quote_status"], "DELAYED_OR_UNKNOWN_FEED")

    def test_nonfinite_and_sentinel_iv_are_not_observations(self):
        for iv in [None, -999, 9999, float("nan")]:
            self.assertIsNone(normalize_quote(security(volatility=iv), NOW)["iv_decimal"])

    def test_lineage_unallocated_and_immutable_forward_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = self.journal(root)
            before = journal.read_bytes()
            calls = []
            def fetch(symbols, timeout_seconds):
                calls.append((symbols, timeout_seconds))
                return {symbol: security() for symbol in symbols}
            out = root / "observations"
            summary = collect(journal, out, now=NOW, fetch=fetch)
            self.assertEqual(summary["contracts_tracked"], 2)
            self.assertEqual(summary["missing_symbol_observations"], 1)
            self.assertEqual(summary["status"], "PARTIAL")
            bundle = json.loads(next(out.glob("sample_*.json")).read_text())
            puts = [r for r in bundle["observations"] if r["strategy"] == "long put"][0]
            self.assertEqual(len(puts["recommendations"]), 2)
            self.assertEqual(puts["recommendations"][0]["coverage_status"], "PRE_COLLECTION_RECOMMENDATION")
            original = {p.name: p.read_bytes() for p in out.iterdir()}
            collect(journal, out, now=NOW + timedelta(days=1), fetch=fetch)
            for name, content in original.items():
                self.assertEqual((out / name).read_bytes(), content)
            self.assertEqual(before, journal.read_bytes())
            self.assertEqual(calls[0][0][0], "A     261120C00100000")

    def test_budget_and_missing_quotes_are_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = self.journal(root)
            tick = iter([0, 0, 40, 40])
            result = collect(journal, root / "out", now=NOW, fetch=lambda *a, **k: {},
                batch_size=1, clock=lambda: next(tick))
            self.assertEqual(result["quote_status_counts"], {
                "MISSING_QUOTE": 1, "NOT_SAMPLED_BUDGET": 1})

    def test_failures_persist_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def fetch(*args, **kwargs):
                raise RuntimeError("secret-response")
            with patch("builtins.print") as output:
                result = collect(self.journal(root), root / "out", now=NOW, fetch=fetch)
            self.assertEqual(result["quote_status_counts"], {"FETCH_FAILED": 2})
            self.assertNotIn("secret-response", str(output.call_args_list))

    def test_expired_and_future_recommendations_not_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = self.journal(Path(tmp))
            contracts, _ = tracked_contracts(journal, NOW - timedelta(days=3))
            self.assertFalse(contracts)
            contracts, _ = tracked_contracts(journal, NOW + timedelta(days=70))
            self.assertFalse(contracts)

    def test_parent_timeout_does_not_fail_daily_run(self):
        import subprocess
        with patch("daily_run.subprocess.run", side_effect=subprocess.TimeoutExpired("collector", 45)):
            with patch("builtins.print") as output:
                collect_research_observations()
            self.assertIn("45 seconds", str(output.call_args_list))

    def test_adapter_preserves_exact_symbols_and_timeout(self):
        from schwab.market_data_client import get_option_quotes
        symbol = "A     261120C00100000"
        with patch("schwab.market_data_client.get_access_token", return_value="fixture"):
            with patch("schwab.market_data_client.requests.get") as request:
                request.return_value.json.return_value = {symbol: security()}
                self.assertIn(symbol, get_option_quotes([symbol], timeout_seconds=2))
                self.assertEqual(request.call_args.kwargs["params"]["symbols"], symbol)
                self.assertEqual(request.call_args.kwargs["timeout"], 2)

    def test_collection_happens_after_email_without_research_rerun(self):
        import daily_run
        events = []
        with patch("daily_run.subprocess.run") as scan, \
             patch("daily_run.latest_file", return_value=Path("fixture.csv")), \
             patch("daily_run.build_daily_report", return_value=Path("fixture.md")), \
             patch("daily_run.send_email_report", side_effect=lambda *a, **k: events.append("email")), \
             patch("daily_run.collect_research_observations", side_effect=lambda: events.append("collect")), \
             patch("builtins.print"):
            scan.return_value.returncode = 0
            daily_run.main()
            self.assertEqual(events, ["email", "collect"])
            self.assertEqual(scan.call_count, 1)


if __name__ == "__main__":
    unittest.main()
