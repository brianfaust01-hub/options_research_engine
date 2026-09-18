"""Forward, sampled option paths. No orders, policy changes, or inferred fills."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import gzip
import json
from pathlib import Path
import time
from uuid import uuid4
from zoneinfo import ZoneInfo

from option_observation_collector import ROOT, normalize_quote, tracked_contracts, timestamp

OUTPUT = ROOT / "data" / "processed" / "intraday_option_paths"
CADENCE_SECONDS = 60


def session_bounds(now):
    """Conservative equity-option regular hours: holidays/early closes/DST."""
    local = now.astimezone(ZoneInfo("America/New_York"))
    if local.weekday() >= 5 or not 9 <= local.hour <= 16:
        return None
    import pandas_market_calendars as calendars
    schedule = calendars.get_calendar("NYSE").schedule(local.date(), local.date())
    if schedule.empty:
        return None
    row = schedule.iloc[0]
    return row.market_open.to_pydatetime(), row.market_close.to_pydatetime()


def save_bundle(path, payload):
    # Exclusive compressed artifacts; interrupted files are reported by readers.
    with path.open("xb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as compressed:
            compressed.write(json.dumps(payload, allow_nan=False, separators=(",", ":")).encode())


def collect_intraday(journal, output=OUTPUT, *, fetch=None, now=None,
                     bounds=None, budget_seconds=30, batch_size=50, clock=time.monotonic):
    if budget_seconds <= 0 or batch_size <= 0:
        raise ValueError("Positive collection bounds required")
    fixed = now is not None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Timezone-aware receipt time required")
    bounds = session_bounds(now) if bounds is None else bounds
    if bounds is None or not bounds[0] <= now < bounds[1]:
        return {"status": "MARKET_CLOSED", "api_requests": 0}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # OS lock released on process exit, including crashes. File presence is not a lock.
    import msvcrt
    with (output / "collector.lock").open("a+b") as lock:
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return {"status": "ALREADY_RUNNING", "api_requests": 0}
        try:
            return _collect(journal, output, fetch, now, fixed, bounds,
                            budget_seconds, batch_size, clock)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _collect(journal, output, fetch, now, fixed, bounds, budget, batch_size, clock):
    contracts, missing = tracked_contracts(journal, now, lookback_days=60)
    symbols = sorted(contracts)
    # Rotate starting batch to avoid starvation without rescanning all history.
    batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]
    if batches:
        start = int(now.timestamp() // CADENCE_SECONDS) % len(batches)
        batches = batches[start:] + batches[:start]
    if fetch is None:
        from schwab.market_data_client import get_option_quotes
        fetch = get_option_quotes
    started = clock()
    observations, counts, requests = [], {}, 0
    for batch in batches:
        remaining = budget - (clock() - started)
        response, failure = {}, None
        if remaining <= 0:
            failure = "NOT_SAMPLED_BUDGET"
        else:
            requests += 1
            try:
                response = fetch(batch, timeout_seconds=min(5, remaining))
                if not isinstance(response, dict):
                    raise ValueError("Invalid response")
            except Exception as exc:
                failure = "FETCH_FAILED"
                print("Intraday quote batch failed: " + type(exc).__name__)
        receipt = now if fixed else datetime.now(timezone.utc)
        for symbol in batch:
            item = {"contract_symbol": symbol, "observed_at": receipt.isoformat(),
                    **normalize_quote(response.get(symbol), receipt)}
            # Intraday freshness is stricter than the legacy daily collector.
            if item["quote_status"] == "OBSERVED" and item["quote_age_seconds"] < 0:
                failure_status = "INVALID_QUOTE_TIME"
            elif item["quote_status"] == "OBSERVED" and item["quote_age_seconds"] > 60:
                failure_status = "STALE_INTRADAY_QUOTE"
            else:
                failure_status = failure
            if receipt >= bounds[1]:
                failure_status = "OUTSIDE_SESSION_RECEIPT"
            if failure_status:
                item.update(quote_status=failure_status, iv_status=failure_status,
                            eligible_for_sampled_returns=False)
            item["intraday_exit_path_status"] = "SAMPLED_ONLY_NOT_TICK_COMPLETE"
            counts[item["quote_status"]] = counts.get(item["quote_status"], 0) + 1
            observations.append(item)
    summary = {"schema_version": 1, "started_at": now.isoformat(),
        "session_open": bounds[0].isoformat(), "session_close": bounds[1].isoformat(),
        "cadence_seconds": CADENCE_SECONDS, "source": "SCHWAB_OPTION_QUOTES",
        "contracts_tracked": len(symbols), "missing_symbols": missing,
        "api_requests": requests, "quote_status_counts": counts,
        "status": "NO_CONTRACTS" if not symbols else "COMPLETE" if
                  counts.get("OBSERVED", 0) == len(symbols) and not missing else "PARTIAL",
        "elapsed_seconds": clock() - started, "production_policy_changed": False,
        "eligible_for_empirical_calibration": False,
        "limitations": ["Between-sample threshold crossings and fills are unknown",
            "Absent slots are gaps, never interpolated", "Entry coverage is not backdated",
            "No automatic export to option_exit_paths.csv"],
        "contracts": list(contracts.values()), "observations": observations}
    day = output / now.strftime("%Y-%m-%d")
    day.mkdir(exist_ok=True)
    artifact = day / f"sample_{now.strftime('%H%M%S')}_{uuid4().hex[:12]}.json.gz"
    save_bundle(artifact, summary)
    return {k: v for k, v in summary.items() if k not in {"contracts", "observations"}}


def sampled_path(points, *, entry_at, entry_price, stop_price=None, target_price=None):
    """Ordered bid-liquidation returns, with explicit unobserved intervals.

    Caller must supply an attributed entry time/price, not a midnight date or
    assumed broker fill. First observed hit is NOT true first event ordering.
    """
    if entry_at.tzinfo is None or entry_price <= 0:
        raise ValueError("Attributed aware entry time and positive entry price required")
    usable = sorted((p for p in points if p.get("quote_status") == "OBSERVED"
        and timestamp(p.get("observed_at")) is not None
        and timestamp(p["observed_at"]) >= entry_at
        and timestamp(p.get("quote_at")) is not None
        and timestamp(p["quote_at"]) >= entry_at), key=lambda p: timestamp(p["observed_at"]))
    path, gaps, previous, hit = [], [], entry_at, None
    for point in usable:
        observed = timestamp(point["observed_at"])
        seconds = (observed - previous).total_seconds()
        if seconds > CADENCE_SECONDS * 1.5:
            gaps.append({"from": previous.isoformat(), "to": observed.isoformat(), "seconds": seconds})
        bid = point["bid"]
        event = "STOP_OBSERVED" if stop_price is not None and bid <= stop_price else (
                "TARGET_OBSERVED" if target_price is not None and bid >= target_price else None)
        if hit is None and event:
            hit = {"event": event, "observed_at": observed.isoformat(), "bid": bid}
        path.append({"observed_at": observed.isoformat(), "bid": bid,
                     "return": bid / entry_price - 1})
        previous = observed
    return {"points": path, "gaps": gaps, "first_observed_hit": hit,
        "status": "NO_USABLE_QUOTES" if not path else "GAPPED_SAMPLED_PATH" if gaps else "SAMPLED_PATH",
        "true_first_event": "INDETERMINATE_BETWEEN_SAMPLES",
        "eligible_for_empirical_calibration": False}


def session_health(output, session_date, *, now=None):
    """Read-only expected-slot audit: absent/corrupt/partial data never pass."""
    from datetime import date
    import pandas_market_calendars as calendars
    day = date.fromisoformat(session_date)
    schedule = calendars.get_calendar("NYSE").schedule(day, day)
    if schedule.empty:
        return {"status": "NON_SESSION", "session_date": session_date}
    opening = schedule.iloc[0].market_open.to_pydatetime()
    closing = schedule.iloc[0].market_close.to_pydatetime()
    now = now or datetime.now(timezone.utc)
    end = min(closing, now)
    expected = set(range(int(opening.timestamp() // 60), int(end.timestamp() // 60)))
    slots, complete, usable, corrupt, symbol_counts = set(), set(), set(), [], {}
    for artifact in sorted((Path(output) / session_date).glob("sample_*.json.gz")):
        try:
            with gzip.open(artifact, "rt", encoding="utf-8") as handle:
                bundle = json.load(handle)
            slot = int(timestamp(bundle["started_at"]).timestamp() // 60)
            if slot not in expected:
                continue
            slots.add(slot)
            if bundle["status"] == "COMPLETE":
                complete.add(slot)
            for point in bundle["observations"]:
                if point["quote_status"] == "OBSERVED":
                    usable.add(slot)
                    symbol_counts.setdefault(point["contract_symbol"], set()).add(slot)
        except (OSError, EOFError, ValueError, TypeError, KeyError, AttributeError):
            corrupt.append(artifact.name)
    return {"session_date": session_date, "expected_elapsed_slots": len(expected),
        "recorded_slots": len(slots), "fully_observed_slots": len(complete),
        "slots_with_any_usable_quotes": len(usable),
        "absent_slots": [datetime.fromtimestamp(s * 60, timezone.utc).isoformat()
                         for s in sorted(expected - slots)],
        "partial_or_empty_slots": len(slots - complete), "corrupt_artifacts": corrupt,
        "contract_usable_slot_counts": {symbol: len(s) for symbol, s in symbol_counts.items()},
        "status": "NOT_STARTED" if not expected else "NO_COVERAGE" if not slots else
                  "GAPPED_OR_PARTIAL" if expected != complete or corrupt else "SAMPLED_ONLY",
        "eligible_for_empirical_calibration": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, default=ROOT / "data" / "trade_journal.csv")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--health-date", help="Read-only YYYY-MM-DD slot audit; no API calls")
    args = parser.parse_args()
    try:
        if args.health_date:
            print(json.dumps(session_health(args.output_dir, args.health_date)))
            return 0
        result = collect_intraday(args.journal, args.output_dir)
        print(json.dumps(result))
        return 1 if result["status"] == "PARTIAL" else 0
    except Exception as exc:
        # Never print API responses, token values, or credential-bearing URLs.
        print("Intraday collection failed: " + type(exc).__name__)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
