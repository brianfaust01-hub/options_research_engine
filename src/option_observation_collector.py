"""Forward-only research observations; never changes recommendations or orders.

One daily sample is NOT an intraday stop/target execution path. Quotes and IV
share exact-contract lineage, while missing/stale observations remain explicit.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "data" / "processed" / "option_observations"
SCHEMA_VERSION = 1


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def timestamp(value):
    try:
        if number(value) is not None:
            return datetime.fromtimestamp(float(value) / 1000, timezone.utc)
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.replace(tzinfo=timezone.utc) if result.tzinfo is None else result
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def tracked_contracts(journal_path, now, lookback_days=60):
    """Preserve allocated AND unallocated exact symbols; never synthesize one."""
    contracts = {}
    missing = 0
    with Path(journal_path).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            date = timestamp(row.get("RecommendationDate"))
            if date is None or not now - timedelta(days=lookback_days) <= date <= now:
                continue
            strategy = row.get("option_strategy", "").strip().casefold()
            if strategy not in {"long call", "long put"}:
                continue
            symbol = row.get("contract_symbol", "").strip()
            if not symbol or symbol.casefold() == "nan":
                missing += 1
                continue
            expiry = timestamp(row.get("expiration"))
            if expiry is None or expiry.date() < now.date():
                continue
            item = contracts.setdefault(symbol, {"contract_symbol": symbol,
                "ticker": row.get("Ticker") or row.get("ticker"),
                "expiration": row.get("expiration"), "strategy": strategy,
                "recommendations": []})
            item["recommendations"].append({
                "recommendation_id": row.get("RecommendationID"),
                "recommendation_date": row.get("RecommendationDate"),
                "policy_era_id": row.get("PolicyEraID"),
                "allocation_decision": row.get("allocation_decision"),
            })
    return contracts, missing


def normalize_quote(security, observed_at):
    security = security if isinstance(security, dict) else {}
    quote = security.get("quote", {})
    quote = quote if isinstance(quote, dict) else {}
    bid, ask = number(quote.get("bidPrice")), number(quote.get("askPrice"))
    quote_at = timestamp(quote.get("quoteTime"))
    age = (observed_at - quote_at).total_seconds() if quote_at else None
    if not quote:
        status = "MISSING_QUOTE"
    elif bid is None or ask is None or bid < 0 or ask <= 0 or ask < bid:
        status = "INVALID_MARKET"
    elif quote_at is None:
        status = "UNKNOWN_QUOTE_TIME"
    elif age < -60:
        status = "INVALID_QUOTE_TIME"
    elif age > 900:
        status = "STALE_QUOTE"
    elif security.get("realtime") is not True:
        status = "DELAYED_OR_UNKNOWN_FEED"
    else:
        status = "OBSERVED"
    raw_iv = number(quote.get("volatility"))
    valid_iv = raw_iv is not None and 0 < raw_iv < 1000
    return {"quote_status": status, "bid": bid, "ask": ask,
        "mark": number(quote.get("mark")), "last": number(quote.get("lastPrice")),
        "quote_at": quote_at.isoformat() if quote_at else None,
        "quote_age_seconds": age, "realtime": security.get("realtime"),
        "iv_raw_percent": raw_iv, "iv_decimal": raw_iv / 100 if valid_iv else None,
        "iv_status": "OBSERVED" if valid_iv and status == "OBSERVED" else
            "INVALID_OR_MISSING_IV" if not valid_iv else status,
        "delta": number(quote.get("delta")), "gamma": number(quote.get("gamma")),
        "theta": number(quote.get("theta")), "vega": number(quote.get("vega")),
        "open_interest": number(quote.get("openInterest")),
        "volume": number(quote.get("totalVolume")),
        "eligible_for_sampled_returns": status == "OBSERVED",
        "intraday_exit_path_status": "INSUFFICIENT_SAMPLING",
    }


def save_new(path, payload):
    """Exclusive immutable artifacts: never overwrite a previous observation."""
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)


def collect(journal_path, output_dir=DEFAULT_OUTPUT, *, fetch=None, now=None,
            batch_size=50, budget_seconds=30, clock=time.monotonic):
    if batch_size <= 0 or budget_seconds <= 0:
        raise ValueError("Batch size and collection budget must be positive")
    fixed_time = now is not None
    now = now or datetime.now(timezone.utc)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    coverage_path = output_dir / "coverage.json"
    coverage = {"schema_version": SCHEMA_VERSION, "collection_started_at": now.isoformat(),
        "source": "SCHWAB_OPTION_QUOTES", "cadence": "DAILY_AFTER_EMAIL_PLUS_MANUAL",
        "iv_series_definition": "EXACT_CONTRACT_IV_NOT_CONSTANT_MATURITY_UNDERLYING_IV",
        "iv_rank_status": "UNAVAILABLE_PENDING_HISTORY_AND_BENCHMARK",
        "historical_backfill": False, "production_policy_changed": False,
        "limitations": ["Daily snapshots cannot establish intraday stop/target order",
            "Marks and last trades are not fills; bid/ask observations are not guarantees",
            "Pre-coverage recommendations have incomplete entry-to-exit quote paths"]}
    if not coverage_path.exists():
        try:
            save_new(coverage_path, coverage)
        except FileExistsError:
            pass
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    contracts, missing_symbols = tracked_contracts(journal_path, now)
    last_observed = {}
    # Least-recently sampled first prevents a time budget starving old contracts.
    for path in sorted(output_dir.glob("sample_*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        for item in bundle["observations"]:
            if item["quote_status"] == "OBSERVED":
                last_observed[item["contract_symbol"]] = item["observed_at"]
    symbols = sorted(contracts, key=lambda symbol: (last_observed.get(symbol, ""), symbol))
    if fetch is None:
        from schwab.market_data_client import get_option_quotes
        fetch = get_option_quotes
    started = clock()
    run_id = f"{now.strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:12]}"
    counts = {}
    for offset in range(0, len(symbols), batch_size):
        batch = symbols[offset:offset + batch_size]
        remaining = budget_seconds - (clock() - started)
        status = None
        response = {}
        if remaining <= 0:
            status = "NOT_SAMPLED_BUDGET"
        else:
            try:
                response = fetch(batch, timeout_seconds=min(5, remaining))
                if not isinstance(response, dict):
                    raise ValueError("Invalid quote response")
            except Exception as exc:
                # Exception text may include response bodies or credentials.
                status = "FETCH_FAILED"
                print(f"Option observation batch failed: {type(exc).__name__}")
        # Actual receipt time matters; tests can supply a fixed clock.
        receipt = now if fixed_time else datetime.now(timezone.utc)
        observations = []
        for symbol in batch:
            item = {**contracts[symbol], "observed_at": receipt.isoformat(),
                "coverage_started_at": coverage["collection_started_at"],
                "source": "SCHWAB_OPTION_QUOTES",
                **normalize_quote(response.get(symbol, {}), receipt)}
            for recommendation in item["recommendations"]:
                recommendation["coverage_status"] = (
                    "PRE_COLLECTION_RECOMMENDATION" if timestamp(recommendation["recommendation_date"])
                    < timestamp(coverage["collection_started_at"]) else "FORWARD_COLLECTION")
            if status:
                item.update(quote_status=status, iv_status=status,
                            eligible_for_sampled_returns=False)
            counts[item["quote_status"]] = counts.get(item["quote_status"], 0) + 1
            observations.append(item)
        save_new(output_dir / f"sample_{run_id}_{offset:06d}.json", {
            "schema_version": SCHEMA_VERSION, "run_id": run_id,
            "observations": observations})
    summary = {"schema_version": SCHEMA_VERSION, "run_id": run_id,
        "started_at": now.isoformat(), "coverage_started_at": coverage["collection_started_at"],
        "contracts_tracked": len(symbols), "missing_symbol_observations": missing_symbols,
        "quote_status_counts": counts, "elapsed_seconds": clock() - started,
        "status": "NO_CONTRACTS" if not symbols else
                  "COMPLETE" if counts.get("OBSERVED", 0) == len(symbols) and not missing_symbols
                  else "PARTIAL", "production_policy_changed": False}
    save_new(output_dir / f"run_{run_id}.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, default=ROOT / "data" / "trade_journal.csv")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print("Option research collection: " + json.dumps(collect(args.journal, args.output_dir)))


if __name__ == "__main__":
    main()
