"""Read-only attribution and counterfactual audit for portfolio allocation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from config import MAX_ALLOCATED_TRADES
from portfolio_allocator import (
    DEFAULT_MAX_RECOMMENDATIONS,
    explain_allocation_ineligibility,
)


def _number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def audit_files(
    files: list[Path],
    counterfactual_limit: int = MAX_ALLOCATED_TRADES,
) -> dict:
    rejection_reasons = Counter()
    strategy_counts = Counter()
    counterfactual_strategy_counts = Counter()
    run_summaries = []
    counterfactual_rows = []

    for path in files:
        frame = pd.read_csv(path, low_memory=False)
        rank = _number(frame.get("allocation_rank"))
        ranked = frame[rank.notna()].copy()
        ranked["_rank"] = rank[rank.notna()]

        for _, row in frame.iterrows():
            for reason in explain_allocation_ineligibility(row):
                rejection_reasons[reason] += 1

        for strategy, count in ranked.get(
            "option_strategy",
            pd.Series(dtype="object"),
        ).value_counts(dropna=False).items():
            strategy_counts[str(strategy)] += int(count)

        extra = ranked[
            (ranked["_rank"] > DEFAULT_MAX_RECOMMENDATIONS)
            & (ranked["_rank"] <= counterfactual_limit)
        ].copy()

        for strategy, count in extra.get(
            "option_strategy",
            pd.Series(dtype="object"),
        ).value_counts(dropna=False).items():
            counterfactual_strategy_counts[str(strategy)] += int(count)

        for _, row in extra.iterrows():
            counterfactual_rows.append(
                {
                    "source": path.name,
                    "ticker": row.get("ticker"),
                    "rank": int(row["_rank"]),
                    "strategy": row.get("option_strategy"),
                    "portfolio_score": row.get("portfolio_score"),
                    "spread_pct": row.get("spread_pct"),
                    "option_open_interest": row.get(
                        "option_open_interest"
                    ),
                    "sector": row.get("sector"),
                    "industry": row.get("industry"),
                }
            )

        allocated = ranked[
            ranked.get("allocation_decision").eq("Allocate")
        ]
        run_summaries.append(
            {
                "source": path.name,
                "ranked_candidates": len(ranked),
                "allocated_candidates": len(allocated),
                "counterfactual_candidates": len(extra),
            }
        )

    counterfactual_frame = pd.DataFrame(counterfactual_rows)

    def statistic(column: str, function: str):
        if counterfactual_frame.empty or column not in counterfactual_frame:
            return None

        values = _number(counterfactual_frame[column]).dropna()

        if values.empty:
            return None

        return float(getattr(values, function)())

    return {
        "configuration": {
            "allocator_default_limit": DEFAULT_MAX_RECOMMENDATIONS,
            "configured_limit": MAX_ALLOCATED_TRADES,
            "limits_disagree": (
                DEFAULT_MAX_RECOMMENDATIONS != MAX_ALLOCATED_TRADES
            ),
            "production_behavior_changed": False,
        },
        "files_analyzed": len(files),
        "runs": run_summaries,
        "ranked_strategy_mix": dict(strategy_counts),
        "counterfactual": {
            "limit": counterfactual_limit,
            "candidates": counterfactual_rows,
            "strategy_mix": dict(counterfactual_strategy_counts),
            "average_portfolio_score": statistic(
                "portfolio_score", "mean"
            ),
            "maximum_spread_pct": statistic("spread_pct", "max"),
            "minimum_open_interest": statistic(
                "option_open_interest", "min"
            ),
        },
        "ineligibility_reasons": dict(rejection_reasons),
        "limitations": [
            "Sector and industry values may be unknown.",
            "Existing holdings and cross-position correlation are not yet incorporated.",
            "Repeated intraday runs are separate observations, not independent samples.",
            "Broker execution has not been reconciled.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit allocation capacity without changing decisions."
    )
    parser.add_argument("--recent-files", type=int, default=20)
    parser.add_argument(
        "--counterfactual-limit",
        type=int,
        default=MAX_ALLOCATED_TRADES,
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    args = parser.parse_args()
    files = sorted(
        (
            args.project_root
            / "data"
            / "processed"
        ).glob("trade_recommendations_*.csv")
    )[-args.recent_files:]
    print(
        json.dumps(
            audit_files(files, args.counterfactual_limit),
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
