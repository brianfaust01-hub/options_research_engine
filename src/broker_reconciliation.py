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
    rows = list(csv.reader(Path(path).open(encoding="utf-8-sig", newline="")))
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only broker reconciliation")
    parser.add_argument("statement")
    parser.add_argument("--portfolio", default="data/paper_portfolio.csv")
    parser.add_argument("--output", help="Optional new JSON report path")
    parser.add_argument("--apply-confirmed-closures", action="store_true")
    args = parser.parse_args()
    report = build_report(args.statement, args.portfolio)
    rendered = json.dumps(report, indent=2)
    if args.output:
        output = Path(args.output)
        if output.exists():
            raise FileExistsError(f"Refusing to overwrite {output}")
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
