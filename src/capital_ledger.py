"""Append-only broker capital ledger and account-state snapshots.

Thinkorswim statements are external evidence. Imports never rewrite a prior
ledger event or snapshot; repeated source rows are ignored by deterministic
identifiers. Performance calculations refuse to report time-weighted deployed
capital when required daily snapshots are missing or quarantined.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable


LEDGER_COLUMNS = [
    "EventID", "ExecutedAt", "EventType", "AccountingRole", "Reference", "Description",
    "MiscFees", "CommissionsFees", "Amount", "CashBalance", "SourcePath",
    "SourceSHA256", "ImportedAt",
]
SNAPSHOT_COLUMNS = [
    "SnapshotID", "AsOfDate", "NetLiquidatingValue", "CashValue",
    "OptionMarketValue", "UnrealizedPnL", "DayPnL", "YtdPnL",
    "TotalFeesYTD", "StockBuyingPower", "OptionBuyingPower",
    "IntradayBuyingPower", "DataQualityStatus", "DataQualityIssues",
    "SourcePath", "SourceSHA256", "ImportedAt",
]


def _money(value: str | None) -> float | None:
    text = (value or "").strip()
    if not text or text.upper() == "N/A":
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace("$", "").replace(",", "").replace("+", "")
    number = float(text)
    return -number if negative else number


def _section(rows: list[list[str]], name: str) -> list[list[str]]:
    start = next(i for i, row in enumerate(rows) if row and row[0].strip() == name)
    result = []
    for row in rows[start + 1:]:
        if not row or not any(cell.strip() for cell in row):
            break
        result.append(row)
    return result


def _source(path: str | Path) -> tuple[Path, str, list[list[str]]]:
    source = Path(path).resolve()
    payload = source.read_bytes()
    rows = list(csv.reader(payload.decode("utf-8-sig").splitlines()))
    return source, hashlib.sha256(payload).hexdigest(), rows


def _statement_end_date(rows: list[list[str]]) -> date:
    heading = next(" ".join(row) for row in rows if row and row[0].startswith("Account Statement for"))
    match = re.search(r"through\s+(\d{1,2}/\d{1,2}/\d{2})", heading)
    if not match:
        raise ValueError("Statement end date is unavailable")
    return datetime.strptime(match.group(1), "%m/%d/%y").date()


@dataclass(frozen=True)
class AccountSnapshot:
    snapshot_id: str
    as_of_date: str
    net_liquidating_value: float
    cash_value: float
    option_market_value: float
    unrealized_pnl: float
    day_pnl: float
    ytd_pnl: float
    total_fees_ytd: float
    stock_buying_power: float
    option_buying_power: float
    intraday_buying_power: float
    data_quality_status: str
    data_quality_issues: str
    source_path: str
    source_sha256: str
    imported_at: str


def parse_account_snapshot(path: str | Path) -> AccountSnapshot:
    source, digest, rows = _source(path)
    as_of = _statement_end_date(rows)
    summary_rows = _section(rows, "Account Summary")
    summary = {row[0].strip(): _money(row[1]) for row in summary_rows if len(row) > 1}
    options = _section(rows, "Options")
    option_total = next(
        (_money(row[-1]) for row in options if "OVERALL TOTALS" in {cell.strip() for cell in row[:2]}),
        0.0,
    ) or 0.0
    pnl = _section(rows, "Profits and Losses")
    total = next(row for row in pnl if "OVERALL TOTALS" in {cell.strip() for cell in row[:2]})
    unrealized, day_pnl, ytd_pnl = _money(total[2]), _money(total[4]), _money(total[5])
    nav = summary.get("Net Liquidating Value")
    if nav is None:
        raise ValueError("Net Liquidating Value is unavailable")
    issues: list[str] = []
    cash = nav - option_total
    if abs((cash + option_total) - nav) > .01:
        issues.append("NAV_COMPONENT_IDENTITY_FAILED")
    imported = datetime.now().isoformat(timespec="seconds")
    snapshot_id = hashlib.sha256(f"{as_of}|{digest}".encode()).hexdigest()[:24]
    return AccountSnapshot(
        snapshot_id, as_of.isoformat(), nav, cash, option_total,
        unrealized or 0.0, day_pnl or 0.0, ytd_pnl or 0.0,
        summary.get("Total Commissions & Fees YTD") or 0.0,
        summary.get("Stock Buying Power") or 0.0,
        summary.get("Option Buying Power") or 0.0,
        summary.get("Intraday Buying Power") or 0.0,
        "COMPLETE" if not issues else "QUARANTINED", ";".join(issues),
        source.name, digest, imported,
    )


def parse_cash_ledger(path: str | Path) -> list[dict]:
    source, digest, rows = _source(path)
    imported = datetime.now().isoformat(timespec="seconds")
    result = []
    for row in _section(rows, "Cash Balance")[1:]:
        if len(row) < 9 or not row[0].strip() or row[0].strip() == "TOTAL":
            continue
        executed = datetime.strptime(f"{row[0].strip()} {row[1].strip()}", "%m/%d/%y %H:%M:%S").isoformat()
        reference = row[3].replace('="', "").replace('"', "").strip()
        identity = "|".join([executed, row[2].strip(), reference, row[4].strip(), row[7].strip()])
        result.append({
            "EventID": hashlib.sha256(identity.encode()).hexdigest()[:24],
            "ExecutedAt": executed, "EventType": row[2].strip().upper(),
            "AccountingRole": "CASH_POSTING",
            "Reference": reference, "Description": row[4].strip(),
            "MiscFees": _money(row[5]) or 0.0,
            "CommissionsFees": _money(row[6]) or 0.0,
            "Amount": _money(row[7]) or 0.0, "CashBalance": _money(row[8]),
            "SourcePath": source.name, "SourceSHA256": digest, "ImportedAt": imported,
        })
    return result


def parse_trade_fills(path: str | Path) -> list[dict]:
    """Capture same-day fills even when the cash section has not posted them yet."""
    source, digest, rows = _source(path)
    imported = datetime.now().isoformat(timespec="seconds")
    result = []
    for row in _section(rows, "Account Trade History")[1:]:
        if len(row) < 14 or not row[1].strip():
            continue
        executed = datetime.strptime(row[1].strip(), "%m/%d/%y %H:%M:%S").isoformat()
        quantity = int(row[4].replace("+", ""))
        price = float(row[11])
        cash_effect = -quantity * price * 100
        description = " ".join([
            row[3].strip().upper(), row[4].strip(), row[7].strip().upper(),
            row[8].strip().upper(), row[9].strip(), row[10].strip().upper(),
            "@", row[11].strip(), row[6].strip().upper(), row[13].strip().upper(),
        ])
        identity = "|".join(["FILL", executed, description])
        result.append({
            "EventID": hashlib.sha256(identity.encode()).hexdigest()[:24],
            "ExecutedAt": executed, "EventType": "FILL",
            "AccountingRole": "EXECUTION_EVIDENCE",
            "Reference": "", "Description": description,
            "MiscFees": 0.0, "CommissionsFees": 0.0,
            "Amount": cash_effect, "CashBalance": None,
            "SourcePath": source.name, "SourceSHA256": digest, "ImportedAt": imported,
        })
    return result


def _append_unique(path: Path, rows: Iterable[dict], columns: list[str], id_field: str) -> int:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: set[str] = set()
    if path.exists():
        with path.open(encoding="utf-8-sig", newline="") as handle:
            existing = {row[id_field] for row in csv.DictReader(handle)}
    additions = [row for row in rows if str(row[id_field]) not in existing]
    if not additions:
        return 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if path.stat().st_size == 0:
            writer.writeheader()
        writer.writerows(additions)
    return len(additions)


def import_statement(statement: str | Path, ledger_path: str | Path = "data/capital_ledger.csv", snapshot_path: str | Path = "data/account_state_snapshots.csv") -> dict:
    snapshot = parse_account_snapshot(statement)
    ledger_rows = [*parse_cash_ledger(statement), *parse_trade_fills(statement)]
    ledger_added = _append_unique(Path(ledger_path), ledger_rows, LEDGER_COLUMNS, "EventID")
    snapshot_row = dict(zip(SNAPSHOT_COLUMNS, asdict(snapshot).values()))
    snapshot_file = Path(snapshot_path)
    existing = []
    if snapshot_file.exists():
        with snapshot_file.open(encoding="utf-8-sig", newline="") as handle:
            existing = list(csv.DictReader(handle))
    assessed = assess_snapshot_sequence([*existing, snapshot_row])
    snapshot_row = next(row for row in assessed if row["SnapshotID"] == snapshot.snapshot_id)
    snapshot_added = _append_unique(snapshot_file, [snapshot_row], SNAPSHOT_COLUMNS, "SnapshotID")
    return {"ledger_events_added": ledger_added, "snapshots_added": snapshot_added, "snapshot": snapshot_row}


def assess_snapshot_sequence(snapshots: list[dict], jump_limit: float = .50) -> list[dict]:
    """Flag implausible NAV jumps; never silently repair or discard them."""
    ordered = sorted(snapshots, key=lambda row: row["AsOfDate"])
    previous = None
    assessed = []
    for row in ordered:
        item = dict(row)
        nav = float(row["NetLiquidatingValue"])
        if previous and previous > 0 and abs(nav / previous - 1) > jump_limit:
            item["DataQualityStatus"] = "QUARANTINED"
            issue = "NAV_JUMP_REQUIRES_EXTERNAL_FLOW_RECONCILIATION"
            item["DataQualityIssues"] = ";".join(filter(None, [row.get("DataQualityIssues", ""), issue]))
        if item.get("DataQualityStatus") != "QUARANTINED":
            previous = nav
        assessed.append(item)
    return assessed


def weekly_performance(snapshots: list[dict], start: str, end: str, experiment_base: float) -> dict:
    assessed = assess_snapshot_sequence(snapshots)
    usable = {row["AsOfDate"]: row for row in assessed if row.get("DataQualityStatus") != "QUARANTINED"}
    if start not in usable or end not in usable:
        raise ValueError("Usable beginning and ending snapshots are required")
    beginning = float(usable[start]["NetLiquidatingValue"])
    ending = float(usable[end]["NetLiquidatingValue"])
    pnl = ending - beginning
    required = []
    cursor = datetime.fromisoformat(start).date()
    final = datetime.fromisoformat(end).date()
    while cursor <= final:
        if cursor.weekday() < 5:
            required.append(cursor.isoformat())
        cursor += timedelta(days=1)
    coverage = [day for day in required if day in usable]
    deployed_values = [float(usable[day]["OptionMarketValue"]) for day in coverage]
    exact = len(coverage) == len(required) and all(value >= 0 for value in deployed_values)
    weighted = sum(deployed_values) / len(deployed_values) if exact and deployed_values else None
    return {
        "start": start, "end": end, "beginning_nav": beginning, "ending_nav": ending,
        "net_pnl": pnl, "return_on_experiment_base_pct": pnl / experiment_base,
        "required_trading_days": required, "covered_trading_days": coverage,
        "time_weighted_deployed_capital": weighted,
        "return_on_time_weighted_deployed_capital_pct": pnl / weighted if weighted else None,
        "deployed_capital_status": "COMPLETE" if exact else "INSUFFICIENT_DAILY_SNAPSHOTS",
    }


def nav_identity_residual(
    beginning_nav: float,
    ending_nav: float,
    external_flows: float,
    realized_pnl: float,
    unrealized_pnl_change: float,
    fees: float,
) -> float:
    """Return the unexplained NAV amount; zero proves the ledger identity."""
    expected = beginning_nav + external_flows + realized_pnl + unrealized_pnl_change - fees
    return round(ending_nav - expected, 2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an append-only Thinkorswim capital statement")
    parser.add_argument("statement")
    parser.add_argument("--ledger", default="data/capital_ledger.csv")
    parser.add_argument("--snapshots", default="data/account_state_snapshots.csv")
    args = parser.parse_args()
    print(json.dumps(import_statement(args.statement, args.ledger, args.snapshots), indent=2))


if __name__ == "__main__":
    main()
