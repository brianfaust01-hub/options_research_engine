"""Read-only interaction analysis for the six-week configuration checkpoint.

This module deliberately evaluates coarse two-field configuration profiles.
It is not a production scorer and never changes configuration or history.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from itertools import combinations
from pathlib import Path

import pandas as pd

from config import (
    DIRECTIONAL_CONFIDENCE_FIX_EFFECTIVE_DATE,
    POLICY_ERA_BASELINE_DATE,
    POLICY_ERA_ID,
)
from hindsight_analytics import (
    _bucket_score,
    _column,
    _episode_representatives,
    _numeric_bands,
    build_thesis_episodes,
)


RETURN_COLUMN = "Horizon7DDirectionalReturnPct"
MIN_TOTAL_SAMPLE = 12
MIN_HALF_SAMPLE = 4


def _configuration_bands(frame: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "research_score": _column(frame, "ResearchScore", "research_score").map(_bucket_score),
        "time_edge": _column(frame, "TimeEdgeScore", "time_edge_score").map(_bucket_score),
        "execution_score": _column(frame, "ExecutionScore", "execution_score").map(_bucket_score),
        "contract_score": _column(frame, "ContractScore", "contract_score").map(_bucket_score),
        "horizon_fit_score": _column(frame, "HorizonFitScore", "horizon_fit_score").map(_bucket_score),
        "absolute_delta": _numeric_bands(
            pd.to_numeric(_column(frame, "BrokerDelta", "broker_delta"), errors="coerce").abs(),
            [-math.inf, .25, .35, .50, .60, math.inf],
            ["<0.25", "0.25-0.35", "0.35-0.50", "0.50-0.60", ">0.60"],
        ),
        "implied_volatility": _numeric_bands(
            _column(frame, "ImpliedVolatility", "implied_volatility"),
            [-math.inf, .20, .40, .60, .80, 1.20, math.inf],
            ["<20%", "20-40%", "40-60%", "60-80%", "80-120%", ">120%"],
        ),
        "theta_drag_pct_per_day": _numeric_bands(
            _column(frame, "ThetaDragPctPerDay", "theta_drag_pct_per_day"),
            [-math.inf, .01, .02, .03, .05, math.inf],
            ["<1%", "1-2%", "2-3%", "3-5%", ">5%"],
        ),
        "gamma_per_premium": _numeric_bands(
            _column(frame, "GammaPerPremium", "gamma_per_premium"),
            [-math.inf, .005, .01, .02, .04, math.inf],
            ["<0.005", "0.005-0.01", "0.01-0.02", "0.02-0.04", ">0.04"],
        ),
        "vega_per_premium": _numeric_bands(
            _column(frame, "VegaPerPremium", "vega_per_premium"),
            [-math.inf, .02, .05, .10, .20, math.inf],
            ["<0.02", "0.02-0.05", "0.05-0.10", "0.10-0.20", ">0.20"],
        ),
    }


def post_fix_episode_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Return matured, executable, deduplicated post-fix seven-day episodes."""
    dates = pd.to_datetime(_column(raw, "RecommendationDate"), errors="coerce", format="mixed")
    direction = _column(raw, "Direction").isin(["BULLISH", "BEARISH"])
    policy = _column(raw, "PolicyEraID").fillna("").astype(str).str.strip().eq(POLICY_ERA_ID)
    action = _column(raw, "Action", "action").fillna("").astype(str).str.casefold()
    opportunity = _column(raw, "OpportunityType", "opportunity_type").fillna("").astype(str).str.casefold()
    strategy = _column(raw, "OptionStrategy", "option_strategy").fillna("").astype(str).str.casefold()
    executable = (
        action.eq("evaluate options")
        & opportunity.str.contains("candidate", regex=False)
        & strategy.isin(["long call", "long put"])
    )
    eligible = raw[
        direction
        & policy
        & dates.ge(pd.Timestamp(POLICY_ERA_BASELINE_DATE))
        & executable
    ].copy()
    episodes = build_thesis_episodes(eligible)
    representatives = _episode_representatives(episodes, RETURN_COLUMN).copy()
    representative_dates = pd.to_datetime(
        _column(representatives, "RecommendationDate"), errors="coerce", format="mixed"
    )
    representatives = representatives[
        representative_dates.ge(pd.Timestamp(DIRECTIONAL_CONFIDENCE_FIX_EFFECTIVE_DATE))
    ].copy()
    representatives["_Date"] = pd.to_datetime(
        _column(representatives, "RecommendationDate"), errors="coerce", format="mixed"
    ).dt.normalize()
    representatives["_Return"] = pd.to_numeric(representatives[RETURN_COLUMN], errors="coerce")
    representatives["_Direction"] = _column(representatives, "Direction").fillna("UNKNOWN")
    direction_mean = representatives.groupby("_Direction")["_Return"].transform("mean")
    representatives["_AdjustedReturn"] = representatives["_Return"] - direction_mean
    return representatives


def analyze_combinations(
    episodes: pd.DataFrame,
    min_total: int = MIN_TOTAL_SAMPLE,
    min_half: int = MIN_HALF_SAMPLE,
) -> dict:
    """Evaluate observed two- and three-field intersections for discovery."""
    if episodes.empty:
        return {"episode_count": 0, "qualified": [], "stable": []}
    dates = sorted(episodes["_Date"].dropna().unique())
    split_date = pd.Timestamp(dates[max(0, len(dates) // 2 - 1)])
    working = episodes.copy()
    working["_Half"] = working["_Date"].le(split_date).map({True: "EARLY", False: "LATE"})
    bands = _configuration_bands(working)
    quality_efficiency = (
        bands["research_score"].eq("90-99")
        & bands["theta_drag_pct_per_day"].eq("<1%")
    )
    contract_efficiency = (
        bands["absolute_delta"].eq("0.35-0.50")
        & bands["implied_volatility"].eq("20-40%")
    )
    baseline_allocated = _column(working, "AllocationDecision", "allocation_decision") \
        .fillna("").astype(str).str.casefold().eq("allocate")
    rows: list[dict] = []
    for order in (2, 3):
      order_minimum = min_total if order == 2 else max(10, min_total - 2)
      for fields in combinations(bands, order):
        assignments = {f"_Band{index}": bands[field] for index, field in enumerate(fields)}
        grouped = working.assign(**assignments)
        band_columns = list(assignments)
        known = pd.Series(True, index=grouped.index)
        for column in band_columns:
            known &= grouped[column].ne("Unknown")
        grouped = grouped[known]
        for band_values, subset in grouped.groupby(band_columns):
            if order == 2:
                band_values = tuple(band_values)
            if len(subset) < order_minimum:
                continue
            early = subset[subset["_Half"] == "EARLY"]
            late = subset[subset["_Half"] == "LATE"]
            early_mean = early["_AdjustedReturn"].mean() if len(early) else None
            late_mean = late["_AdjustedReturn"].mean() if len(late) else None
            date_counts = subset.groupby("_Date").size()
            adjusted = subset["_AdjustedReturn"]
            lower, upper = adjusted.quantile([.05, .95])
            winsorized_adjusted = adjusted.clip(lower=lower, upper=upper).mean()
            stable = (
                len(early) >= min_half
                and len(late) >= min_half
                and early_mean is not None and early_mean > 0
                and late_mean is not None and late_mean > 0
                and float(date_counts.max() / len(subset)) <= .35
            )
            discovery_candidate = (
                len(early) >= 3 and len(late) >= 3
                and early_mean is not None and early_mean > 0
                and late_mean is not None and late_mean > 0
                and winsorized_adjusted > 0
                and float(date_counts.max() / len(subset)) <= .50
            )
            positive = subset.loc[subset["_Return"] > 0, "_Return"].sum()
            negative = -subset.loc[subset["_Return"] < 0, "_Return"].sum()
            row = {
                "order": order,
                "episodes": int(len(subset)),
                "win_rate": float(subset["_Return"].gt(0).mean()),
                "average_return": float(subset["_Return"].mean()),
                "direction_adjusted_average_return": float(subset["_AdjustedReturn"].mean()),
                "winsorized_adjusted_average_return": float(winsorized_adjusted),
                "median_return": float(subset["_Return"].median()),
                "profit_factor": None if negative == 0 else float(positive / negative),
                "early_episodes": int(len(early)),
                "early_adjusted_average_return": None if early_mean is None else float(early_mean),
                "late_episodes": int(len(late)),
                "late_adjusted_average_return": None if late_mean is None else float(late_mean),
                "bullish_count": int(subset["_Direction"].eq("BULLISH").sum()),
                "bearish_count": int(subset["_Direction"].eq("BEARISH").sum()),
                "distinct_dates": int(subset["_Date"].nunique()),
                "max_date_share": float(date_counts.max() / len(subset)),
                "stable_positive": bool(stable),
                "discovery_candidate": bool(discovery_candidate),
                "allocated_matches": int(baseline_allocated.loc[subset.index].sum()),
            }
            for index, (field, band) in enumerate(zip(fields, band_values), start=1):
                row[f"field_{index}"] = field
                row[f"band_{index}"] = str(band)
            rows.append(row)
    rows.sort(key=lambda row: (
        not row["discovery_candidate"],
        -row["winsorized_adjusted_average_return"],
        -row["episodes"],
    ))
    allocated = working[baseline_allocated]
    named_hypotheses = {
        "quality_efficiency": _screen_metrics(working[quality_efficiency]),
        "contract_efficiency": _screen_metrics(working[contract_efficiency]),
        "quality_or_contract_efficiency": _screen_metrics(
            working[quality_efficiency | contract_efficiency]
        ),
        "quality_and_contract_efficiency": _screen_metrics(
            working[quality_efficiency & contract_efficiency]
        ),
    }
    return {
        "episode_count": int(len(working)),
        "date_count": int(working["_Date"].nunique()),
        "split_date": split_date.date().isoformat(),
        "minimum_total_sample": min_total,
        "minimum_half_sample": min_half,
        "qualified": rows,
        "stable": [row for row in rows if row["stable_positive"]],
        "discovery_candidates": [row for row in rows if row["discovery_candidate"]],
        "population_average_return": float(working["_Return"].mean()),
        "population_win_rate": float(working["_Return"].gt(0).mean()),
        "allocated_episode_count": int(len(allocated)),
        "allocated_average_return": None if allocated.empty else float(allocated["_Return"].mean()),
        "allocated_win_rate": None if allocated.empty else float(allocated["_Return"].gt(0).mean()),
        "named_hypotheses": named_hypotheses,
    }


def _pct(value) -> str:
    return "n/a" if value is None or pd.isna(value) else f"{100 * value:+.1f}%"


def _screen_metrics(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {"episodes": 0, "win_rate": None, "average_return": None, "profit_factor": None}
    positive = frame.loc[frame["_Return"] > 0, "_Return"].sum()
    negative = -frame.loc[frame["_Return"] < 0, "_Return"].sum()
    return {
        "episodes": int(len(frame)),
        "win_rate": float(frame["_Return"].gt(0).mean()),
        "average_return": float(frame["_Return"].mean()),
        "profit_factor": None if negative == 0 else float(positive / negative),
        "bullish_count": int(frame["_Direction"].eq("BULLISH").sum()),
        "bearish_count": int(frame["_Direction"].eq("BEARISH").sum()),
    }


def render_report(result: dict, source: Path) -> str:
    lines = [
        "# Project Stonks — Configuration Combination Analysis",
        "",
        f"**Source:** `{source.name}`  ",
        f"**Generated:** {datetime.now().isoformat(timespec='seconds')}  ",
        f"**Eligible post-fix matured episodes:** {result['episode_count']}  ",
        f"**Chronological split:** through {result.get('split_date', 'n/a')} vs later dates  ",
        "**Decision status:** research only; no production configuration changed",
        "",
        "## Method",
        "",
        "Each row is an observed intersection of trade-configuration bands. Returns are adjusted by subtracting the mean return for the episode's call/put direction, so direction is a control rather than the optimization target. The strict table uses pairwise profiles with at least 12 episodes overall, at least four in each chronological half, positive adjusted return in both halves, and no single recommendation date contributing more than 35% of the sample. The discovery table also explores bounded three-field profiles under the looser rules stated there.",
        "",
        "## Stable Positive Pairwise Profiles",
        "",
        "| Configuration profile | N | Win rate | Raw avg | Adjusted avg | Early adj | Late adj | Call / Put | Dates |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in [item for item in result.get("stable", []) if item["order"] == 2][:20]:
        profile = _profile_label(row)
        lines.append(
            f"| {profile} | {row['episodes']} | {_pct(row['win_rate'])} | "
            f"{_pct(row['average_return'])} | {_pct(row['direction_adjusted_average_return'])} | "
            f"{_pct(row['early_adjusted_average_return'])} | {_pct(row['late_adjusted_average_return'])} | "
            f"{row['bullish_count']} / {row['bearish_count']} | {row['distinct_dates']} |"
        )
    if not result.get("stable"):
        lines.append("| No profile met every stability rule | | | | | | | | |")
    lines.extend([
        "",
        "## Broader Challenger Discovery",
        "",
        f"The full post-fix population is {_pct(result.get('population_win_rate'))} wins with {_pct(result.get('population_average_return'))} average return. The actual allocated cohort contains {result.get('allocated_episode_count')} matured episodes with {_pct(result.get('allocated_win_rate'))} wins and {_pct(result.get('allocated_average_return'))} average return.",
        "",
        "The profiles below use a broader discovery standard: positive direction-adjusted return in both chronological halves, positive 5%/95% winsorized adjusted return, at least three observations per half, and no date above 50% of the profile. They are candidates for the frozen challenger—not production rules.",
        "",
        "| Configuration profile | N | Win rate | Raw avg | Profit factor | Winsorized adj | Early adj | Late adj | Allocated matches |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for row in _nonredundant_candidates(result.get("discovery_candidates", []), limit=20):
        lines.append(
            f"| {_profile_label(row)} | {row['episodes']} | {_pct(row['win_rate'])} | "
            f"{_pct(row['average_return'])} | {row['profit_factor']:.2f} | "
            f"{_pct(row['winsorized_adjusted_average_return'])} | "
            f"{_pct(row['early_adjusted_average_return'])} | {_pct(row['late_adjusted_average_return'])} | "
            f"{row['allocated_matches']} |"
        )
    hypotheses = result.get("named_hypotheses", {})
    combined = hypotheses.get("quality_or_contract_efficiency", {})
    lines.extend([
        "",
        "## Interpretable Composite Hypothesis",
        "",
        "A coherent challenger could retain a recommendation when either (a) Research Score is 90-99 and theta drag is below 1% per day, or (b) absolute delta is 0.35-0.50 and IV is 20-40%. This is a union of a thesis-quality/decay profile and a contract-efficiency profile; it is not a sum of isolated bonuses.",
        "",
        f"That union identifies {combined.get('episodes', 0)} episodes: {_pct(combined.get('win_rate'))} wins, {_pct(combined.get('average_return'))} average return, {combined.get('profit_factor', 0):.2f} profit factor, and {combined.get('bullish_count', 0)} calls / {combined.get('bearish_count', 0)} puts.",
    ])
    lines.extend([
        "",
        "## Interpretation Guardrails",
        "",
        "- These are interaction hypotheses, not independently additive weights.",
        "- A profile observed in only calls or only puts remains direction-composition-limited even after return adjustment; it is not cross-direction confirmation.",
        "- Overlapping rows often describe the same episodes; do not count them as separate confirmations.",
        "- Three-field profiles are exploratory at the current sample size. They may define a challenger hypothesis, but cannot be treated as independently validated until more forward evidence accumulates.",
        "- The checkpoint challenger should use the smallest coherent combination that survives outlier, regime, ticker, and matched-shadow validation.",
        "- No result authorizes an automatic production scoring or allocation change.",
        "",
    ])
    return "\n".join(lines)


def _profile_label(row: dict) -> str:
    return " + ".join(
        f"{row[f'field_{index}']}={row[f'band_{index}']}"
        for index in range(1, row["order"] + 1)
    )


def _nonredundant_candidates(rows: list[dict], limit: int) -> list[dict]:
    """Prefer distinct episode profiles over repeated correlated descriptions."""
    selected: list[dict] = []
    signatures: set[tuple[tuple[str, str], ...]] = set()
    for row in rows:
        signature = tuple(sorted(
            (row[f"field_{index}"], row[f"band_{index}"])
            for index in range(1, row["order"] + 1)
        ))
        if signature in signatures:
            continue
        signatures.add(signature)
        selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    raw = pd.read_csv(args.source, low_memory=False)
    result = analyze_combinations(post_fix_episode_frame(raw))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    markdown_path = args.output_dir / f"config_combination_analysis_{stamp}.md"
    json_path = args.output_dir / f"config_combination_analysis_{stamp}.json"
    markdown_path.write_text(render_report(result, args.source), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"Combination report: {markdown_path}")
    print(f"Combination data: {json_path}")


if __name__ == "__main__":
    main()
