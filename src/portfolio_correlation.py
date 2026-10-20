"""Decision-time portfolio correlation evidence.

This module measures direction-aware underlying-return correlation for research
and later allocation replay.  It does not change production allocation.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


LOOKBACK_DAYS = 60
MIN_OVERLAP_DAYS = 40
PAIR_COLUMNS = [
    "LeftKind", "LeftTicker", "LeftRecommendationID", "LeftDirection",
    "RightKind", "RightTicker", "RightRecommendationID", "RightDirection",
    "LookbackDays", "OverlapDays", "UnderlyingReturnCorrelation",
    "DirectionAdjustedCorrelation", "EvidenceStatus",
]


def _direction(strategy) -> int:
    return -1 if "put" in str(strategy).casefold() else 1


def _close_returns(price_data: pd.DataFrame, ticker: str) -> pd.Series:
    try:
        close = pd.to_numeric(price_data[str(ticker).upper()]["Close"], errors="coerce")
    except (KeyError, TypeError):
        return pd.Series(dtype=float)
    return close.dropna().pct_change(fill_method=None).dropna().tail(LOOKBACK_DAYS)


def build_correlation_evidence(
    candidates: pd.DataFrame,
    positions: pd.DataFrame,
    price_data: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return candidate summary fields and a long-form pair ledger."""
    executable = candidates[
        candidates.get("action", pd.Series(index=candidates.index, dtype=object))
        .fillna("").eq("Evaluate Options")
    ].copy()
    holdings = positions.copy()
    assets = []
    for kind, frame in (("CANDIDATE", executable), ("HOLDING", holdings)):
        for index, row in frame.iterrows():
            ticker = str(row.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            strategy = row.get("option_strategy")
            assets.append({
                "kind": kind,
                "index": index,
                "ticker": ticker,
                "direction": _direction(strategy),
                "strategy": strategy,
                "recommendation_id": row.get("RecommendationID"),
                "returns": _close_returns(price_data, ticker),
            })

    pairs = []
    for left_offset, left in enumerate(assets):
        for right in assets[left_offset + 1:]:
            if left["kind"] == right["kind"] == "HOLDING":
                continue
            joined = pd.concat(
                [left["returns"].rename("left"), right["returns"].rename("right")],
                axis=1, join="inner",
            ).dropna()
            underlying = joined["left"].corr(joined["right"]) if len(joined) >= MIN_OVERLAP_DAYS else None
            signed = (
                float(underlying) * left["direction"] * right["direction"]
                if underlying is not None and pd.notna(underlying) else None
            )
            pairs.append({
                "LeftKind": left["kind"], "LeftTicker": left["ticker"],
                "LeftRecommendationID": left["recommendation_id"],
                "LeftDirection": left["direction"],
                "RightKind": right["kind"], "RightTicker": right["ticker"],
                "RightRecommendationID": right["recommendation_id"],
                "RightDirection": right["direction"],
                "LookbackDays": LOOKBACK_DAYS, "OverlapDays": int(len(joined)),
                "UnderlyingReturnCorrelation": None if underlying is None or pd.isna(underlying) else float(underlying),
                "DirectionAdjustedCorrelation": signed,
                "EvidenceStatus": "MEASURED" if signed is not None else "INSUFFICIENT_OVERLAP",
            })

    pair_frame = pd.DataFrame(pairs, columns=PAIR_COLUMNS)
    enriched = candidates.copy()
    defaults = {
        "correlation_policy_version": "CORRELATION-EVIDENCE-v1",
        "correlation_lookback_days": LOOKBACK_DAYS,
        "correlation_holding_count": 0,
        "max_abs_correlation_to_holdings": None,
        "max_direction_adjusted_correlation_to_holdings": None,
        "mean_direction_adjusted_correlation_to_holdings": None,
        "most_correlated_holding": None,
        "correlation_evidence_status": "NO_HOLDINGS",
    }
    for column, value in defaults.items():
        enriched[column] = value

    for asset in [item for item in assets if item["kind"] == "CANDIDATE"]:
        relevant = pair_frame[
            (
                (pair_frame["LeftKind"].eq("CANDIDATE"))
                & (pair_frame["LeftTicker"].eq(asset["ticker"]))
                & (pair_frame["RightKind"].eq("HOLDING"))
            ) | (
                (pair_frame["RightKind"].eq("CANDIDATE"))
                & (pair_frame["RightTicker"].eq(asset["ticker"]))
                & (pair_frame["LeftKind"].eq("HOLDING"))
            )
        ].copy()
        measured = relevant[relevant["EvidenceStatus"].eq("MEASURED")].copy()
        enriched.at[asset["index"], "correlation_holding_count"] = int(len(measured))
        if measured.empty:
            enriched.at[asset["index"], "correlation_evidence_status"] = (
                "INSUFFICIENT_OVERLAP" if not relevant.empty else "NO_HOLDINGS"
            )
            continue
        values = measured["DirectionAdjustedCorrelation"].astype(float)
        peak_index = values.abs().idxmax()
        peak = measured.loc[peak_index]
        holding = peak["RightTicker"] if peak["RightKind"] == "HOLDING" else peak["LeftTicker"]
        enriched.at[asset["index"], "max_abs_correlation_to_holdings"] = float(values.abs().max())
        enriched.at[asset["index"], "max_direction_adjusted_correlation_to_holdings"] = float(values.max())
        enriched.at[asset["index"], "mean_direction_adjusted_correlation_to_holdings"] = float(values.mean())
        enriched.at[asset["index"], "most_correlated_holding"] = holding
        enriched.at[asset["index"], "correlation_evidence_status"] = "MEASURED"
    return enriched, pair_frame


def write_correlation_evidence(frame: pd.DataFrame, path: str | Path) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)
    return output
