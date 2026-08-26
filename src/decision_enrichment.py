"""Shadow time-edge, earnings-risk, and risk-weighted sizing enrichment."""

from __future__ import annotations

from datetime import date, datetime
from math import floor
from typing import Callable
from functools import lru_cache

import pandas as pd
import yfinance as yf

from config import DATA_DIR, PAPER_PORTFOLIO_VALUE


SHADOW_PROFILE_RISK = {
    "conservative": (0.0050, 0.10),
    "balanced": (0.0075, 0.15),
    "aggressive": (0.0100, 0.20),
}


def _number(value, default=0.0) -> float:
    try:
        return default if value is None or pd.isna(value) else float(value)
    except (TypeError, ValueError):
        return default


def _time_edge(trade: pd.Series, research: dict) -> dict:
    momentum = _number(research.get("MomentumScore"))
    trend = _number(research.get("TrendScore"))
    conviction = _number(trade.get("directional_conviction"))
    signal_score = momentum * 0.40 + trend * 0.30 + conviction * 0.30
    is_put = "PUT" in str(trade.get("option_strategy", "")).upper()
    acceleration = _number(research.get("PriceAccelerationATR"))
    if is_put:
        acceleration *= -1
    acceleration_score = min(100.0, max(0.0, 50 + acceleration * 25))
    volume_ratio = _number(research.get("VolumeRatio20"))
    volume_score = min(100.0, max(0.0, volume_ratio * 50))
    fresh_signal = bool(
        research.get("FreshBreakdown20", False)
        if is_put else research.get("FreshBreakout20", False)
    )
    signal_age = int(_number(research.get("SignalAgeDays"), 20))
    freshness_score = 100.0 if fresh_signal else 60.0 if signal_age <= 3 else 30.0
    score = round(min(100.0, max(0.0, (
        signal_score * 0.70
        + acceleration_score * 0.15
        + volume_score * 0.10
        + freshness_score * 0.05
    ))), 1)
    if score >= 80:
        window = 5
        grade = "A"
    elif score >= 70:
        window = 7
        grade = "B"
    else:
        window = 14
        grade = "C"
    return {
        "time_edge_score": score,
        "time_edge_grade": grade,
        "expected_move_window_days": window,
        "time_edge_data_quality": "COMPLETE",
        "time_edge_reason": (
            f"Momentum {momentum:.0f}; trend {trend:.0f}; "
            f"directional conviction {conviction:.0f}; acceleration "
            f"{acceleration:.2f} ATR; volume {volume_ratio:.2f}x; "
            f"signal age {signal_age}d; fresh breakout/down {fresh_signal}"
        ),
    }


def _shadow_sizing(trade: pd.Series) -> dict:
    entry = _number(trade.get("execution_entry_price")) or _number(trade.get("premium"))
    institutional = _number(trade.get("institutional_trade_score"), 75.0)
    execution = _number(trade.get("execution_score"), 70.0)
    spread = max(0.0, _number(trade.get("spread_pct")))
    conviction_multiplier = min(1.25, max(0.60, 0.60 + (institutional - 70) * 0.026))
    execution_multiplier = min(1.0, max(0.70, execution / 100))
    if spread > 0.05:
        execution_multiplier *= 0.80
    planned_loss_pct = max(0.10, spread * 2)
    stressed_loss_pct = max(0.20, spread * 3, planned_loss_pct * 2)
    output = {
        "shadow_conviction_multiplier": round(conviction_multiplier, 3),
        "shadow_execution_multiplier": round(execution_multiplier, 3),
        "shadow_planned_loss_pct": round(planned_loss_pct, 4),
        "shadow_stressed_loss_pct": round(stressed_loss_pct, 4),
    }
    contract_cost = entry * 100
    for name, (risk_pct, premium_cap_pct) in SHADOW_PROFILE_RISK.items():
        risk_budget = PAPER_PORTFOLIO_VALUE * risk_pct * conviction_multiplier * execution_multiplier
        by_risk = floor(risk_budget / (contract_cost * stressed_loss_pct)) if contract_cost > 0 else 0
        by_premium = floor((PAPER_PORTFOLIO_VALUE * premium_cap_pct) / contract_cost) if contract_cost > 0 else 0
        contracts = max(0, min(by_risk, by_premium))
        output[f"shadow_{name}_contracts"] = contracts
        output[f"shadow_{name}_capital"] = round(contracts * contract_cost, 2)
        output[f"shadow_{name}_stressed_loss"] = round(
            contracts * contract_cost * stressed_loss_pct, 2
        )
    return output


@lru_cache(maxsize=1024)
def get_next_earnings_date(ticker: str) -> date | None:
    cache_directory = DATA_DIR / "cache" / "yfinance"
    cache_directory.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(cache_directory.resolve()))
    calendar = yf.Ticker(ticker).calendar
    if calendar is None:
        return None
    value = calendar.get("Earnings Date") if isinstance(calendar, dict) else None
    if isinstance(calendar, pd.DataFrame) and "Earnings Date" in calendar.index:
        value = calendar.loc["Earnings Date"].iloc[0]
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


_default_earnings_provider = get_next_earnings_date


def enrich_decisions(
    trades_df: pd.DataFrame,
    research_df: pd.DataFrame,
    as_of: date | None = None,
    earnings_provider: Callable[[str], date | None] | None = None,
) -> pd.DataFrame:
    """Add shadow fields and apply the approved earnings-window guard."""
    result = trades_df.copy()
    as_of = as_of or date.today()
    earnings_provider = earnings_provider or _default_earnings_provider
    research_lookup = {
        str(row.get("Ticker", row.get("ticker", ""))).upper(): row.to_dict()
        for _, row in research_df.iterrows()
    }
    enrichment = []
    for _, trade in result.iterrows():
        ticker = str(trade.get("ticker", "")).upper()
        values = _time_edge(trade, research_lookup.get(ticker, {}))
        values.update(_shadow_sizing(trade))
        values.update({
            "earnings_date": None,
            "days_to_earnings": None,
            "trading_days_to_earnings": None,
            "earnings_status": "NOT_CHECKED",
            "earnings_within_thesis_window": False,
            "earnings_allocation_override": False,
        })
        enrichment.append(values)
    for column in enrichment[0].keys() if enrichment else []:
        result[column] = [row[column] for row in enrichment]
    result["shadow_time_adjusted_score"] = (
        pd.to_numeric(result.get("portfolio_score"), errors="coerce").fillna(0) * 0.90
        + pd.to_numeric(result["time_edge_score"], errors="coerce").fillna(0) * 0.10
    ).round(1)

    target_count = int(result["allocation_decision"].eq("Allocate").sum())
    ranked = result[pd.to_numeric(result.get("allocation_rank"), errors="coerce").notna()].copy()
    ranked = ranked.sort_values("allocation_rank")
    if target_count:
        result.loc[ranked.index, "allocation_decision"] = "Watch"
        result.loc[ranked.index, "PortfolioStatus"] = "NOT_ALLOCATED"
    selected = 0
    for index in ranked.index:
        if selected >= target_count:
            break
        ticker = str(result.at[index, "ticker"]).upper()
        try:
            earnings_date = earnings_provider(ticker)
        except Exception:
            earnings_date = None
        if earnings_date is None:
            result.at[index, "earnings_status"] = "UNKNOWN"
            within = False
        else:
            days = (earnings_date - as_of).days
            trading_days = max(0, len(pd.bdate_range(as_of, earnings_date)) - 1)
            window = int(result.at[index, "expected_move_window_days"])
            within = 0 <= days and trading_days <= window
            result.at[index, "earnings_date"] = earnings_date.isoformat()
            result.at[index, "days_to_earnings"] = days
            result.at[index, "trading_days_to_earnings"] = trading_days
            result.at[index, "earnings_status"] = "CONFIRMED"
            result.at[index, "earnings_within_thesis_window"] = within
        if within:
            result.at[index, "earnings_allocation_override"] = True
            continue
        result.at[index, "allocation_decision"] = "Allocate"
        result.at[index, "PortfolioStatus"] = "OPEN"
        selected += 1
    return result
