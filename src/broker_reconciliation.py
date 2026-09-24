"""Read-only Thinkorswim trade-history reconciliation.

Broker executions are external evidence.  This module normalizes them and
compares them with Project Stonks' paper portfolio without changing either
source.  Any later correction must be a separate, explicit operation.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class BrokerTrade:
    executed_at: str
    side: str
    quantity: int
    position_effect: str
    ticker: str
    expiration: str
    strike: float
    option_type: str
    price: float
    order_type: str

    @property
    def contract_key(self) -> tuple[str, str, float, str]:
        return self.ticker, self.expiration, self.strike, self.option_type


def _date(value: str) -> str:
    return datetime.strptime(value.strip(), "%m/%d/%y %H:%M:%S").isoformat()


def _expiration(value: str) -> str:
    return datetime.strptime(value.strip(), "%d %b %y").date().isoformat()


def load_thinkorswim_trades(path: str | Path) -> list[BrokerTrade]:
    """Load only the Account Trade History section from a statement export."""
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    start = next(
        index for index, row in enumerate(rows)
        if row and row[0].strip() == "Account Trade History"
    )
    trades: list[BrokerTrade] = []
    for row in rows[start + 2:]:
        if not row or not any(cell.strip() for cell in row):
            break
        if len(row) < 14 or not row[1].strip():
            continue
        trades.append(BrokerTrade(
            executed_at=_date(row[1]),
            side=row[3].strip().upper(),
            quantity=abs(int(row[4].replace("+", ""))),
            position_effect=row[6].strip().upper(),
            ticker=row[7].strip().upper(),
            expiration=_expiration(row[8]),
            strike=float(row[9]),
            option_type=row[10].strip().upper(),
            price=float(row[11]),
            order_type=row[13].strip().upper(),
        ))
    return sorted(trades, key=lambda trade: trade.executed_at)


def load_current_option_positions(path: str | Path) -> list[dict]:
    """Parse the statement's authoritative current option-position section."""
    payload = Path(path).read_bytes()
    rows = list(csv.reader(payload.decode("utf-8-sig").splitlines()))
    start = next(i for i, row in enumerate(rows) if row and row[0].strip() == "Options")
    result = []
    for row in rows[start + 2:]:
        if not row or not any(cell.strip() for cell in row):
            break
        if "OVERALL TOTALS" in {cell.strip() for cell in row[:2]}:
            continue
        if len(row) < 9 or not row[0].strip():
            continue
        result.append({
            "ticker": row[0].strip().upper(), "option_code": row[1].strip(),
            "expiration": _expiration(row[2]), "strike": float(row[3]),
            "option_type": row[4].strip().upper(),
            "quantity": abs(int(row[5].replace("+", ""))),
            "entry_price": float(row[6]), "mark": float(row[7]),
            "mark_value": float(row[8].replace("$", "").replace(",", "")),
        })
    return result


def _contract_key(row: dict) -> tuple[str, str, float, str]:
    strategy = str(row.get("OptionStrategy") or row.get("option_strategy") or "").upper()
    return (str(row.get("Ticker") or row.get("ticker") or "").upper(),
            str(row.get("Expiration") or row.get("expiration") or "")[:10],
            float(row.get("Strike") or row.get("strike")),
            "PUT" if "PUT" in strategy else "CALL")


def sync_current_positions(statement_path: str | Path, portfolio_path: str | Path,
                           journal_path: str | Path) -> dict:
    """Atomically align mutable paper state to broker positions and fills.

    Recommendation history is read only. An absent current position is closed
    only when the same statement contains an exact-contract closing fill.
    """
    statement = Path(statement_path)
    portfolio_path = Path(portfolio_path)
    journal_path = Path(journal_path)
    source_hash = hashlib.sha256(statement.read_bytes()).hexdigest()
    positions = load_current_option_positions(statement)
    current = {_contract_key({"Ticker": row["ticker"], "Expiration": row["expiration"],
        "Strike": row["strike"], "OptionStrategy": row["option_type"]}): row for row in positions}
    trades = load_thinkorswim_trades(statement)
    closes: dict[tuple, list[BrokerTrade]] = defaultdict(list)
    opens: dict[tuple, list[BrokerTrade]] = defaultdict(list)
    for trade in trades:
        (opens if trade.position_effect == "TO OPEN" else closes)[trade.contract_key].append(trade)

    portfolio = pd.read_csv(portfolio_path, dtype={"PositionID": "string", "RecommendationID": "string"})
    updated = portfolio.copy(deep=True)
    for column in updated.columns:
        if column in {"Status", "ExitDate", "ExitReason", "LastReviewed", "PeakPremiumDate",
                      "RecommendedStopDate", "ProfitProtectionStatus", "RecommendationID"}:
            updated[column] = updated[column].astype("object")
    closed, refreshed, created = [], [], []
    open_indices = list(updated.index[updated["Status"].astype(str).str.upper() == "OPEN"])
    existing_keys = {}
    for index in open_indices:
        row = updated.loc[index].to_dict()
        key = _contract_key(row)
        existing_keys[key] = index
        broker = current.get(key)
        if broker:
            updated.loc[index, "Contracts"] = broker["quantity"]
            updated.loc[index, "CurrentPremium"] = broker["mark"]
            updated.loc[index, "PnLPct"] = broker["mark"] / float(row["EntryPremium"]) - 1
            updated.loc[index, "LastReviewed"] = datetime.now().isoformat(timespec="seconds")
            refreshed.append(str(row["PositionID"]))
            continue
        exact_closes = closes.get(key, [])
        if not exact_closes:
            raise ValueError(f"Open system position absent from broker without closing fill: {row['PositionID']}")
        closing = exact_closes[-1]
        updated.loc[index, "Status"] = "CLOSED"
        updated.loc[index, "ExitDate"] = closing.executed_at
        updated.loc[index, "ExitReason"] = "BROKER_RECONCILED_CLOSE"
        updated.loc[index, "ExitPremium"] = closing.price
        updated.loc[index, "CurrentPremium"] = closing.price
        updated.loc[index, "PnLPct"] = closing.price / float(row["EntryPremium"]) - 1
        updated.loc[index, "LastReviewed"] = closing.executed_at
        closed.append(str(row["PositionID"]))

    csv.field_size_limit(10_000_000)
    with journal_path.open(encoding="utf-8-sig", newline="") as handle:
        journal = list(csv.DictReader(handle))
    allocated = [row for row in journal if str(row.get("allocation_decision", "")).casefold() == "allocate"]
    numeric_ids = [int(str(value)[1:]) for value in updated["PositionID"] if str(value).startswith("P")]
    next_id = max(numeric_ids, default=0) + 1
    for key, broker in current.items():
        if key in existing_keys:
            continue
        opening = opens.get(key, [])[-1] if opens.get(key) else None
        if opening is None:
            raise ValueError(f"Broker position has no opening fill in statement and no system row: {key}")
        matches = [row for row in allocated if _contract_key(row) == key
                   and str(row.get("RecommendationDate", "")) <= opening.executed_at]
        recommendation = matches[-1] if matches else {}
        if not recommendation:
            raise ValueError(f"Broker position has no allocated recommendation: {key}")
        base = {column: None for column in updated.columns}
        entry = opening.price
        now = datetime.now().isoformat(timespec="seconds")
        base.update({
            "PositionID": f"P{next_id:06d}",
            "RecommendationID": recommendation.get("RecommendationID"),
            "Ticker": key[0], "OptionStrategy": "Long Put" if key[3] == "PUT" else "Long Call",
            "Expiration": key[1], "Strike": key[2], "Contracts": broker["quantity"],
            "EntryPremium": entry, "EntryDate": opening.executed_at, "Status": "OPEN",
            "CurrentPremium": broker["mark"], "PnLPct": broker["mark"] / entry - 1,
            "LastReviewed": now,
            "CurrentDTE": (datetime.fromisoformat(key[1]).date() - datetime.now().date()).days,
            "PeakPremium": max(entry, broker["mark"]), "PeakPremiumDate": now,
            "RecommendedStop": recommendation.get("stop_loss_price") or None,
            "RecommendedStopDate": recommendation.get("RecommendationDate") or None,
            "ProfitProtectionStatus": "KEEP STOP", "LockedProfitPct": 0.0,
        })
        updated = pd.concat([updated, pd.DataFrame([base], columns=updated.columns)], ignore_index=True)
        created.append(base["PositionID"])
        next_id += 1

    open_after = updated[updated["Status"].astype(str).str.upper() == "OPEN"]
    final = {_contract_key(row): int(float(row["Contracts"])) for row in open_after.to_dict("records")}
    expected = {key: value["quantity"] for key, value in current.items()}
    if final != expected:
        raise ValueError("Post-sync position contract/quantity reconciliation failed")
    temporary = portfolio_path.with_suffix(".syncing.csv")
    try:
        updated.to_csv(temporary, index=False)
        pd.read_csv(temporary)
        os.replace(temporary, portfolio_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"source": statement.name, "source_sha256": source_hash,
            "closed_position_ids": closed, "refreshed_position_ids": refreshed,
            "created_position_ids": created, "open_positions": len(final),
            "open_contracts": sum(final.values()), "status": "RECONCILED"}


def pair_round_trips(trades: list[BrokerTrade]) -> list[dict]:
    """Pair long-option executions FIFO, preserving every broker fill."""
    opens: dict[tuple, deque[BrokerTrade]] = defaultdict(deque)
    results: list[dict] = []
    for trade in trades:
        if trade.position_effect == "TO OPEN":
            for _ in range(trade.quantity):
                opens[trade.contract_key].append(trade)
        elif trade.position_effect == "TO CLOSE":
            for _ in range(trade.quantity):
                opening = opens[trade.contract_key].popleft() if opens[trade.contract_key] else None
                results.append({
                    "ticker": trade.ticker,
                    "expiration": trade.expiration,
                    "strike": trade.strike,
                    "option_type": trade.option_type,
                    "quantity": 1,
                    "opened_at": opening.executed_at if opening else None,
                    "entry_price": opening.price if opening else None,
                    "closed_at": trade.executed_at,
                    "exit_price": trade.price,
                    "gross_pnl": round((trade.price - opening.price) * 100, 2) if opening else None,
                    "entry_order_type": opening.order_type if opening else None,
                    "exit_order_type": trade.order_type,
                    "match_status": "BROKER_ROUND_TRIP" if opening else "UNMATCHED_CLOSE",
                })
    for queue in opens.values():
        for opening in queue:
            results.append({
                "ticker": opening.ticker, "expiration": opening.expiration,
                "strike": opening.strike, "option_type": opening.option_type,
                "quantity": 1, "opened_at": opening.executed_at,
                "entry_price": opening.price, "closed_at": None, "exit_price": None,
                "gross_pnl": None, "entry_order_type": opening.order_type,
                "exit_order_type": None, "match_status": "BROKER_OPEN",
            })
    return results


def reconcile_portfolio(portfolio: pd.DataFrame, round_trips: list[dict]) -> list[dict]:
    """Compare paper positions to broker contracts; do not mutate the frame."""
    reconciled = []
    for _, position in portfolio.iterrows():
        option_type = "PUT" if "PUT" in str(position["OptionStrategy"]).upper() else "CALL"
        matches = [trade for trade in round_trips if (
            trade["ticker"] == str(position["Ticker"]).upper()
            and trade["expiration"] == str(position["Expiration"])[:10]
            and trade["strike"] == float(position["Strike"])
            and trade["option_type"] == option_type
            and trade["entry_price"] == float(position["EntryPremium"])
        )]
        match = matches[-1] if matches else None
        status = "MATCHED_CLOSED" if match and match["closed_at"] else "MATCHED_OPEN" if match else "NO_BROKER_MATCH"
        reconciled.append({
            "position_id": position["PositionID"],
            "ticker": position["Ticker"],
            "system_status": position["Status"],
            "reconciliation_status": status,
            "broker_trade": match,
            "requires_portfolio_review": status == "MATCHED_CLOSED" and position["Status"] == "OPEN",
        })
    return reconciled


def build_report(statement_path: str | Path, portfolio_path: str | Path) -> dict:
    trades = load_thinkorswim_trades(statement_path)
    round_trips = pair_round_trips(trades)
    portfolio = pd.read_csv(portfolio_path)
    reconciliation = reconcile_portfolio(portfolio, round_trips)
    matched_ids = {item["broker_trade"]["opened_at"] for item in reconciliation if item["broker_trade"]}
    return {
        "schema_version": "1.0",
        "truth_source": "THINKORSWIM_ACCOUNT_STATEMENT",
        "source_path": str(Path(statement_path).resolve()),
        "broker_execution_count": len(trades),
        "broker_round_trip_count": sum(item["match_status"] == "BROKER_ROUND_TRIP" for item in round_trips),
        "broker_open_count": sum(item["match_status"] == "BROKER_OPEN" for item in round_trips),
        "portfolio_reconciliation": reconciliation,
        "unmatched_broker_round_trips": [item for item in round_trips if item.get("opened_at") not in matched_ids],
        "attribution_status": "REQUIRES_USER_REVIEW",
    }


def apply_confirmed_closures(report: dict, portfolio_path: str | Path) -> int:
    """Apply only reviewed, exact-contract broker closures atomically."""
    portfolio_path = Path(portfolio_path)
    portfolio = pd.read_csv(portfolio_path)
    updated = portfolio.copy(deep=True)
    for column in ("Status", "ExitDate", "ExitReason", "LastReviewed"):
        if column in updated.columns:
            updated[column] = updated[column].astype("object")
    applied = 0
    for item in report["portfolio_reconciliation"]:
        if not item["requires_portfolio_review"]:
            continue
        broker = item["broker_trade"]
        mask = updated["PositionID"].astype(str) == str(item["position_id"])
        if int(mask.sum()) != 1:
            raise ValueError(f"Expected exactly one portfolio row for {item['position_id']}")
        if str(updated.loc[mask, "Status"].iloc[0]).upper() != "OPEN":
            raise ValueError(f"Position {item['position_id']} is no longer OPEN")
        entry = float(updated.loc[mask, "EntryPremium"].iloc[0])
        updated.loc[mask, "Status"] = "CLOSED"
        updated.loc[mask, "ExitDate"] = broker["closed_at"]
        updated.loc[mask, "ExitReason"] = "BROKER_RECONCILED_CLOSE"
        updated.loc[mask, "ExitPremium"] = broker["exit_price"]
        updated.loc[mask, "CurrentPremium"] = broker["exit_price"]
        updated.loc[mask, "PnLPct"] = (float(broker["exit_price"]) - entry) / entry
        updated.loc[mask, "LastReviewed"] = broker["closed_at"]
        applied += 1
    temporary = portfolio_path.with_suffix(".reconciling.csv")
    try:
        updated.to_csv(temporary, index=False)
        pd.read_csv(temporary)
        os.replace(temporary, portfolio_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return applied


def build_attribution_report(report: dict, review: dict) -> dict:
    """Layer reviewed source/cause attribution onto immutable broker truth."""
    allocated = set(review.get("confirmed_project_allocations", []))
    recommended = set(review.get("project_recommendation_only", []))
    threshold = float(review["execution_error_loss_threshold"])
    attributed = []
    matched_by_open = {
        item["broker_trade"]["opened_at"]: item
        for item in report["portfolio_reconciliation"]
        if item.get("broker_trade")
    }
    trades = [
        item["broker_trade"] for item in report["portfolio_reconciliation"]
        if item.get("broker_trade")
    ] + report["unmatched_broker_round_trips"]
    for trade in trades:
        opened_at = trade.get("opened_at")
        if opened_at in matched_by_open or opened_at in allocated:
            source = "PROJECT_STONKS_ALLOCATED"
            confidence = "CONFIRMED"
        elif opened_at in recommended:
            source = "PROJECT_STONKS_RECOMMENDATION_ALLOCATION_UNKNOWN"
            confidence = "PARTIAL"
        else:
            source = "UNCLASSIFIED"
            confidence = "UNRESOLVED"
        return_pct = (
            float(trade["exit_price"]) / float(trade["entry_price"]) - 1
            if trade.get("entry_price") and trade.get("exit_price") is not None
            else None
        )
        execution_error = return_pct is not None and return_pct < threshold
        attributed.append({
            **trade,
            "return_pct": return_pct,
            "trade_source": source,
            "source_confidence": confidence,
            "outcome_attribution": (
                "USER_REVIEWED_EXECUTION_PROCESS_ERROR"
                if execution_error else "NOT_CLASSIFIED_AS_EXECUTION_ERROR"
            ),
        })
    return {
        "schema_version": "2.0",
        "base_reconciliation_source": report.get("source_path"),
        "review_basis": review,
        "trade_count": len(attributed),
        "project_allocated_count": sum(t["trade_source"] == "PROJECT_STONKS_ALLOCATED" for t in attributed),
        "execution_error_count": sum(t["outcome_attribution"] == "USER_REVIEWED_EXECUTION_PROCESS_ERROR" for t in attributed),
        "unclassified_count": sum(t["trade_source"] == "UNCLASSIFIED" for t in attributed),
        "trades": attributed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only broker reconciliation")
    parser.add_argument("statement")
    parser.add_argument("--portfolio", default="data/paper_portfolio.csv")
    parser.add_argument("--output", help="Optional new JSON report path")
    parser.add_argument("--apply-confirmed-closures", action="store_true")
    parser.add_argument("--sync-current", action="store_true",
                        help="Reconcile exact current positions and broker-confirmed closes")
    parser.add_argument("--journal", default="data/trade_journal.csv")
    parser.add_argument("--review", help="Optional reviewed attribution JSON")
    args = parser.parse_args()
    report = build_report(args.statement, args.portfolio)
    if args.review:
        review = json.loads(Path(args.review).read_text(encoding="utf-8"))
        report = build_attribution_report(report, review)
    if args.apply_confirmed_closures and args.sync_current:
        raise ValueError("Choose one state-application mode")
    if args.output and Path(args.output).exists():
        raise FileExistsError(f"Refusing to overwrite {args.output}")
    if args.sync_current:
        report["current_state_sync"] = sync_current_positions(
            args.statement, args.portfolio, args.journal)
    rendered = json.dumps(report, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if args.apply_confirmed_closures:
        if not args.output:
            raise ValueError("--output is required before applying closures")
        count = apply_confirmed_closures(report, args.portfolio)
        print(f"Applied {count} broker-confirmed closures.")


if __name__ == "__main__":
    main()
