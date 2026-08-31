"""Portfolio-level capital competition and daily recycling.

This layer consumes already-scored candidates and re-underwritten positions.
It does not weaken upstream qualification, liquidity, execution, or exit rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor
from typing import Any

import pandas as pd

from config import (
    MAX_AGGREGATE_STOP_LOSS_PCT,
    MAX_CAPITAL_UTILIZATION_PCT,
    MAX_POSITION_SIZE_PCT,
    MAX_SECTOR_EXPOSURE_PCT,
    MAX_THEME_EXPOSURE_PCT,
    MIN_EXECUTION_SCORE,
    PORTFOLIO_INCUMBENT_ADVANTAGE,
    PORTFOLIO_MIN_FORWARD_SCORE,
)
from portfolio_exposure import classify_ticker


@dataclass(frozen=True)
class ArbitrationResult:
    candidates: pd.DataFrame
    positions: pd.DataFrame
    summary: dict[str, Any]


def _number(value, default=None):
    try:
        return default if value is None or pd.isna(value) else float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    number = _number(value)
    return default if number is None else int(number)


def _text(value, default=""):
    try:
        return default if value is None or pd.isna(value) else str(value).strip()
    except (TypeError, ValueError):
        return default


def _boolean(value, default=False):
    try:
        return default if value is None or pd.isna(value) else bool(value)
    except (TypeError, ValueError):
        return default


def _candidate_asset(index, row, nav):
    contracts = _integer(row.get("contracts"))
    entry = _number(row.get("execution_entry_price")) or _number(row.get("premium"))
    value = (entry or 0) * 100 * contracts
    # Portfolio Score is the approved production ranking signal. Time Edge and
    # other shadow fields remain persisted evidence until separately promoted.
    score = _number(row.get("portfolio_score"), 0.0)
    stop_price = _number(row.get("stop_loss_price"))
    stop_pct = _number(row.get("stop_loss_pct"), 0.20)
    expected_loss = (
        max(0.0, entry - stop_price) * 100 * contracts
        if entry and stop_price is not None
        else value * stop_pct
    )
    ticker = _text(row.get("ticker")).upper()
    exposure = classify_ticker(ticker)
    reasons = []
    if _text(row.get("action")) != "Evaluate Options":
        reasons.append("not an executable option candidate")
    if contracts <= 0 or entry is None or entry <= 0:
        reasons.append("invalid contract quantity or entry price")
    if score < PORTFOLIO_MIN_FORWARD_SCORE:
        reasons.append(
            f"forward score {score:.1f} below {PORTFOLIO_MIN_FORWARD_SCORE:.1f} threshold"
        )
    execution = _number(row.get("execution_score"), 0.0)
    if execution < MIN_EXECUTION_SCORE:
        reasons.append(f"execution score {execution:.1f} below {MIN_EXECUTION_SCORE}")
    if _boolean(row.get("earnings_allocation_override", False)):
        reasons.append("earnings inside thesis window")
    if _text(row.get("earnings_status"), "NOT_CHECKED") == "NOT_CHECKED":
        reasons.append("outside bounded arbitration candidate pool")
    if value > nav * MAX_POSITION_SIZE_PCT + 0.01:
        reasons.append("single-position exposure limit")
    return {
        "kind": "candidate", "index": index, "ticker": ticker,
        "score": score, "adjusted_score": score, "value": value,
        "expected_loss": expected_loss, "contracts": contracts,
        "sector": exposure["sector"], "theme": exposure["theme"],
        "eligible": not reasons, "base_reasons": reasons,
    }


def _position_asset(index, row, nav):
    contracts = _integer(row.get("contracts"))
    current = _number(row.get("current_price")) or _number(row.get("entry_price"))
    value_per_contract = (current or 0) * 100
    max_contracts = floor(nav * MAX_POSITION_SIZE_PCT / value_per_contract) \
        if value_per_contract > 0 else 0
    target_contracts = min(contracts, max_contracts)
    value = value_per_contract * target_contracts
    score = _number(row.get("latest_allocation_score"), 0.0)
    stop = _number(row.get("stop_loss"))
    expected_loss = (
        max(0.0, current - stop) * 100 * target_contracts
        if current and stop is not None else value * 0.20
    )
    ticker = _text(row.get("ticker")).upper()
    exposure = classify_ticker(ticker)
    forced_close = _text(row.get("position_recommendation")).upper() in {"SELL", "CLOSE"}
    eligible = (
        not forced_close and target_contracts > 0
        and score >= PORTFOLIO_MIN_FORWARD_SCORE
    )
    reasons = []
    if forced_close:
        reasons.append(_text(row.get("position_reason"), "existing exit rule"))
    elif score < PORTFOLIO_MIN_FORWARD_SCORE:
        reasons.append(
            f"re-underwritten score {score:.1f} below {PORTFOLIO_MIN_FORWARD_SCORE:.1f} threshold"
        )
    if target_contracts < contracts:
        reasons.append("single-position exposure requires reduction")
    return {
        "kind": "position", "index": index, "ticker": ticker,
        "score": score, "adjusted_score": score + PORTFOLIO_INCUMBENT_ADVANTAGE,
        "value": value, "full_value": value_per_contract * contracts,
        "expected_loss": expected_loss, "contracts": target_contracts,
        "original_contracts": contracts, "sector": exposure["sector"],
        "theme": exposure["theme"], "eligible": eligible,
        "base_reasons": reasons, "forced_close": forced_close,
    }


def _constraint_reason(asset, used, stop_risk, ticker_values, sector_values, theme_values, nav):
    if used + asset["value"] > nav * MAX_CAPITAL_UTILIZATION_PCT + 0.01:
        return "insufficient capital under utilization limit"
    if stop_risk + asset["expected_loss"] > nav * MAX_AGGREGATE_STOP_LOSS_PCT + 0.01:
        return "aggregate expected loss at stops would exceed limit"
    if ticker_values.get(asset["ticker"], 0) + asset["value"] > nav * MAX_POSITION_SIZE_PCT + 0.01:
        return f"single-position exposure limit: {asset['ticker']}"
    sector = asset["sector"]
    if sector != "Unknown" and sector_values.get(sector, 0) + asset["value"] > nav * MAX_SECTOR_EXPOSURE_PCT + 0.01:
        return f"sector concentration limit: {sector}"
    theme = asset["theme"]
    if theme != "Unknown" and theme_values.get(theme, 0) + asset["value"] > nav * MAX_THEME_EXPOSURE_PCT + 0.01:
        return f"theme/correlation proxy limit: {theme}"
    return None


def arbitrate_portfolio(
    candidates: pd.DataFrame,
    positions: pd.DataFrame,
    account_nav: float,
) -> ArbitrationResult:
    """Construct the highest-scored feasible portfolio from holdings and candidates."""
    if account_nav <= 0:
        raise ValueError("account_nav must be positive")
    candidates = candidates.copy()
    positions = positions.copy()
    candidate_assets = [
        _candidate_asset(index, row, account_nav)
        for index, row in candidates.iterrows()
    ]
    position_assets = [
        _position_asset(index, row, account_nav)
        for index, row in positions.iterrows()
    ]
    assets = sorted(
        [asset for asset in candidate_assets + position_assets if asset["eligible"]],
        key=lambda asset: (asset["adjusted_score"], asset["score"]),
        reverse=True,
    )
    selected = set()
    rejected = {}
    used = 0.0
    stop_risk = 0.0
    ticker_values: dict[str, float] = {}
    sector_values: dict[str, float] = {}
    theme_values: dict[str, float] = {}
    for asset in assets:
        reason = _constraint_reason(
            asset, used, stop_risk, ticker_values, sector_values, theme_values, account_nav
        )
        key = (asset["kind"], asset["index"])
        if reason:
            rejected[key] = reason
            continue
        selected.add(key)
        used += asset["value"]
        stop_risk += asset["expected_loss"]
        ticker_values[asset["ticker"]] = ticker_values.get(asset["ticker"], 0) + asset["value"]
        if asset["sector"] != "Unknown":
            sector_values[asset["sector"]] = sector_values.get(asset["sector"], 0) + asset["value"]
        if asset["theme"] != "Unknown":
            theme_values[asset["theme"]] = theme_values.get(asset["theme"], 0) + asset["value"]

    for column, default in {
        "portfolio_action": "PASS", "portfolio_action_reason": "",
        "portfolio_forward_score": 0.0, "portfolio_target_value": 0.0,
        "portfolio_expected_loss_at_stop": 0.0,
    }.items():
        candidates[column] = default
    open_tickers = {asset["ticker"] for asset in position_assets}
    for asset in candidate_assets:
        key = ("candidate", asset["index"])
        candidates.at[asset["index"], "portfolio_forward_score"] = asset["score"]
        candidates.at[asset["index"], "portfolio_target_value"] = asset["value"] if key in selected else 0.0
        candidates.at[asset["index"], "portfolio_expected_loss_at_stop"] = asset["expected_loss"] if key in selected else 0.0
        if key in selected:
            action = "ADD" if asset["ticker"] in open_tickers else "OPEN"
            reason = "selected as a superior qualified use of portfolio capital"
            candidates.at[asset["index"], "allocation_decision"] = "Allocate"
            # Preserve legacy OPEN/NOT_ALLOCATED status semantics; the richer
            # OPEN versus ADD decision lives in portfolio_action.
            candidates.at[asset["index"], "PortfolioStatus"] = "OPEN"
        else:
            action = "PASS"
            reasons = asset["base_reasons"] or [rejected.get(key, "lower-ranked than feasible portfolio assets")]
            reason = "; ".join(reasons)
            candidates.at[asset["index"], "allocation_decision"] = "Watch" if asset["eligible"] else "No Allocation"
            candidates.at[asset["index"], "PortfolioStatus"] = "NOT_ALLOCATED"
        candidates.at[asset["index"], "portfolio_action"] = action
        candidates.at[asset["index"], "portfolio_action_reason"] = reason

    for column, default in {
        "portfolio_action": "CLOSE", "portfolio_action_reason": "",
        "portfolio_forward_score": 0.0, "portfolio_target_contracts": 0,
        "portfolio_target_value": 0.0, "portfolio_expected_loss_at_stop": 0.0,
    }.items():
        positions[column] = default
    recycled = 0.0
    value_closed = 0.0
    closed_count = reduced_count = 0
    unrealized_pnl = 0.0
    deployed_cost = 0.0
    for asset in position_assets:
        key = ("position", asset["index"])
        row = positions.loc[asset["index"]]
        pnl = _number(row.get("pnl_dollars"), 0.0)
        entry = _number(row.get("entry_price"), 0.0) * 100 * asset["original_contracts"]
        unrealized_pnl += pnl
        deployed_cost += entry
        positions.at[asset["index"], "portfolio_forward_score"] = asset["score"]
        if key in selected:
            target = asset["contracts"]
            action = "REDUCE" if target < asset["original_contracts"] else "HOLD"
            reason = (
                "reduced to satisfy single-position exposure"
                if action == "REDUCE" else
                "re-underwritten position remains competitive with new opportunities"
            )
            if action == "REDUCE":
                reduced_count += 1
                recycled += asset["full_value"] - asset["value"]
            positions.at[asset["index"], "portfolio_target_contracts"] = target
            positions.at[asset["index"], "portfolio_target_value"] = asset["value"]
            positions.at[asset["index"], "portfolio_expected_loss_at_stop"] = asset["expected_loss"]
        else:
            action = "CLOSE"
            closed_count += 1
            close_value = asset.get("full_value", 0.0)
            recycled += close_value
            value_closed += close_value
            reason = "; ".join(asset["base_reasons"] or [
                rejected.get(key, "capital has a superior qualified use")
            ])
        positions.at[asset["index"], "portfolio_action"] = action
        positions.at[asset["index"], "portfolio_action_reason"] = reason
        positions.at[asset["index"], "position_recommendation"] = action
        positions.at[asset["index"], "position_reason"] = reason

    utilization = used / account_nav
    intentional_cash = max(0.0, account_nav - used)
    rejected_reasons = [reason for reason in rejected.values()]
    cash_reason = (
        "fully deployed within configured constraints"
        if intentional_cash < 0.01 else
        "remaining cash is intentional: "
        + (rejected_reasons[0] if rejected_reasons else "no additional qualified portfolio asset")
    )
    opened = candidates["portfolio_action"].isin(["OPEN", "ADD"])
    value_opened = float(candidates.loc[opened, "portfolio_target_value"].sum())
    summary = {
        "account_nav": round(account_nav, 2),
        "capital_deployed": round(used, 2),
        "capital_utilization_pct": utilization,
        "intentional_cash": round(intentional_cash, 2),
        "intentional_cash_pct": intentional_cash / account_nav,
        "intentional_cash_reason": cash_reason,
        "expected_loss_at_stops": round(stop_risk, 2),
        "expected_loss_at_stops_pct": stop_risk / account_nav,
        "return_on_deployed_capital_pct": unrealized_pnl / deployed_cost if deployed_cost else 0.0,
        "return_on_total_nav_pct": unrealized_pnl / account_nav,
        "capital_recycled": round(recycled, 2),
        "turnover_pct": (recycled + value_opened) / account_nav,
        "positions_opened": int(opened.sum()),
        "value_opened": round(value_opened, 2),
        "positions_closed": closed_count,
        "value_closed": round(value_closed, 2),
        "positions_reduced": reduced_count,
    }
    for key, value in summary.items():
        candidates[f"portfolio_{key}"] = value
        if not positions.empty:
            positions[f"portfolio_{key}"] = value
    return ArbitrationResult(candidates=candidates, positions=positions, summary=summary)
