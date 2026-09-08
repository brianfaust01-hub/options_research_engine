"""Shadow-only, path-dependent empirical stop/target research.

Production exit guidance is intentionally untouched.  The empirical policy
uses completed option-return paths when enough comparable observations exist;
otherwise it records an explicit fallback to the production plan.  It never
uses underlying returns as a substitute for option returns.
"""

from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from config import (
    SHADOW_EXIT_MAX_STOP_LOSS_PCT,
    SHADOW_EXIT_MAX_TARGET_PCT,
    SHADOW_EXIT_MIN_SAMPLE_SIZE,
    SHADOW_EXIT_MIN_STOP_LOSS_PCT,
    SHADOW_EXIT_MIN_TARGET_PCT,
    SHADOW_EXIT_POLICY_ENABLED,
    SHADOW_EXIT_POLICY_VERSION,
    SHADOW_EXIT_SLIPPAGE_PCT,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH_DATA = PROJECT_ROOT / "data" / "processed" / "option_exit_paths.csv"


def _number(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bucket(value: float | None, boundaries: tuple[float, ...]) -> str:
    if value is None:
        return "UNKNOWN"
    for boundary in boundaries:
        if value <= boundary:
            return f"LE_{boundary:g}"
    return f"GT_{boundaries[-1]:g}"


def _parse_path(value: Any) -> list[float]:
    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError:
            return []
    else:
        return []
    path = [_number(item) for item in raw]
    return [item for item in path if item is not None]


@lru_cache(maxsize=1)
def _load_default_records() -> tuple[dict, ...]:
    if not DEFAULT_PATH_DATA.exists():
        return ()
    try:
        frame = pd.read_csv(DEFAULT_PATH_DATA)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return ()
    return tuple(frame.to_dict("records"))


def _context(record: dict) -> tuple[str, str, str, str, str]:
    strategy = str(record.get("option_strategy") or record.get("OptionStrategy") or "UNKNOWN").upper()
    horizon = _number(record.get("expected_move_window_days") or record.get("ExpectedMoveWindowDays"))
    dte = _number(record.get("dte") or record.get("DTE"))
    iv = _number(record.get("implied_volatility") or record.get("ImpliedVolatility"))
    delta = _number(record.get("broker_delta") or record.get("BrokerDelta"))
    return (
        strategy,
        _bucket(horizon, (5, 7, 14)),
        _bucket(dte, (45, 60, 90)),
        _bucket(iv, (.30, .60, .80)),
        _bucket(abs(delta) if delta is not None else None, (.35, .55, .75)),
    )


def _comparable_paths(records: Iterable[dict], candidate: dict) -> tuple[list[list[float]], str]:
    usable = [(record, _parse_path(record.get("option_return_path") or record.get("OptionReturnPath"))) for record in records]
    usable = [(record, path) for record, path in usable if path]
    target = _context(candidate)
    levels = (
        (5, "strategy+horizon+dte+iv+delta"),
        (3, "strategy+horizon+dte"),
        (2, "strategy+horizon"),
        (1, "strategy"),
        (0, "all-option-paths"),
    )
    for fields, label in levels:
        paths = [path for record, path in usable if _context(record)[:fields] == target[:fields]]
        if len(paths) >= SHADOW_EXIT_MIN_SAMPLE_SIZE:
            return paths, label
    return [path for _, path in usable], "insufficient"


def _replay(path: list[float], stop_pct: float, target_pct: float) -> tuple[float, str]:
    for option_return in path:
        if option_return <= -stop_pct:
            return -stop_pct - SHADOW_EXIT_SLIPPAGE_PCT, "STOP_FIRST"
        if option_return >= target_pct:
            return target_pct - SHADOW_EXIT_SLIPPAGE_PCT, "TARGET_FIRST"
    return path[-1] - SHADOW_EXIT_SLIPPAGE_PCT, "TIME_EXIT"


def build_shadow_exit_plan(
    *,
    production_plan: dict,
    entry_price: float | None,
    option_strategy: str | None,
    dte: int | None,
    expected_move_window_days: int | None,
    implied_volatility: float | None,
    broker_delta: float | None,
    records: Iterable[dict] | None = None,
) -> dict:
    """Return research-only exit estimates; never production instructions."""
    fallback_stop = _number(production_plan.get("stop_loss_pct"))
    fallback_target = _number(production_plan.get("profit_target_pct"))
    base = {
        "shadow_exit_policy_version": SHADOW_EXIT_POLICY_VERSION,
        "shadow_exit_policy_status": "DISABLED" if not SHADOW_EXIT_POLICY_ENABLED else "INSUFFICIENT_OPTION_PATHS",
        "shadow_exit_sample_size": 0,
        "shadow_exit_match_level": "none",
        "shadow_stop_loss_pct": fallback_stop,
        "shadow_profit_target_pct": fallback_target,
        "shadow_stop_loss_price": round(entry_price * (1 - fallback_stop), 2) if entry_price and fallback_stop is not None else None,
        "shadow_profit_target_price": round(entry_price * (1 + fallback_target), 2) if entry_price and fallback_target is not None else None,
        "shadow_expected_return_pct": None,
        "shadow_target_first_rate": None,
        "shadow_stop_first_rate": None,
        "shadow_time_exit_rate": None,
    }
    if not SHADOW_EXIT_POLICY_ENABLED or entry_price is None or entry_price <= 0:
        return base

    source = tuple(records) if records is not None else _load_default_records()
    paths, match_level = _comparable_paths(source, {
        "option_strategy": option_strategy,
        "expected_move_window_days": expected_move_window_days,
        "dte": dte,
        "implied_volatility": implied_volatility,
        "broker_delta": broker_delta,
    })
    base["shadow_exit_sample_size"] = len(paths)
    base["shadow_exit_match_level"] = match_level
    if len(paths) < SHADOW_EXIT_MIN_SAMPLE_SIZE:
        return base

    stop_grid = [value / 100 for value in range(
        round(SHADOW_EXIT_MIN_STOP_LOSS_PCT * 100),
        round(SHADOW_EXIT_MAX_STOP_LOSS_PCT * 100) + 1,
    )]
    target_grid = [value / 100 for value in range(
        round(SHADOW_EXIT_MIN_TARGET_PCT * 100),
        round(SHADOW_EXIT_MAX_TARGET_PCT * 100) + 1,
        5,
    )]
    candidates = []
    for stop_pct in stop_grid:
        for target_pct in target_grid:
            outcomes = [_replay(path, stop_pct, target_pct) for path in paths]
            returns = [result[0] for result in outcomes]
            events = [result[1] for result in outcomes]
            expected_return = sum(returns) / len(returns)
            downside = sorted(returns)[max(0, int(len(returns) * .10) - 1)]
            objective = expected_return + .25 * downside
            candidates.append((objective, expected_return, stop_pct, target_pct, events))
    _, expected_return, stop_pct, target_pct, events = max(candidates, key=lambda item: item[:2])
    count = len(events)
    base.update({
        "shadow_exit_policy_status": "CALIBRATED_SHADOW_ONLY",
        "shadow_stop_loss_pct": stop_pct,
        "shadow_profit_target_pct": target_pct,
        "shadow_stop_loss_price": round(entry_price * (1 - stop_pct), 2),
        "shadow_profit_target_price": round(entry_price * (1 + target_pct), 2),
        "shadow_expected_return_pct": expected_return,
        "shadow_target_first_rate": events.count("TARGET_FIRST") / count,
        "shadow_stop_first_rate": events.count("STOP_FIRST") / count,
        "shadow_time_exit_rate": events.count("TIME_EXIT") / count,
    })
    return base
