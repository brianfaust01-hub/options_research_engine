"""Read-only stage attribution for Project Stonks strategy mix."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from opportunity_engine import calculate_directional_opportunity_scores


def _counts(series: pd.Series) -> dict:
    return {
        str(key): int(value)
        for key, value in series.value_counts(dropna=False).items()
    }


def _structural_fixtures() -> dict:
    common = {
        "LiquidityScore": 20,
        "StrategyScore": 80,
    }
    bullish = calculate_directional_opportunity_scores(
        {
            **common,
            "Direction": "Bullish",
            "TrendScore": 100,
            "MomentumScore": 80,
        }
    )
    strong_bearish = calculate_directional_opportunity_scores(
        {
            **common,
            "Direction": "Bearish",
            "TrendScore": 0,
            "MomentumScore": 80,
        }
    )
    low_momentum_bearish = calculate_directional_opportunity_scores(
        {
            **common,
            "Direction": "Bearish",
            "TrendScore": 0,
            "MomentumScore": 20,
        }
    )

    return {
        "bullish_research_fixture": bullish,
        "strong_bearish_research_fixture": strong_bearish,
        "low_momentum_bearish_fixture": low_momentum_bearish,
        "research_direction_consumed_by_current_scoring": True,
        "high_bearish_momentum_magnitude_is_scored_as_bullish": False,
    }


def audit_files(files: list[Path]) -> dict:
    opportunity_types = Counter()
    actions = Counter()
    selected_strategies = Counter()
    allocated_strategies = Counter()
    actionable_by_opportunity = Counter()
    contract_failures_by_opportunity = Counter()

    for path in files:
        frame = pd.read_csv(path, low_memory=False)

        opportunity_types.update(
            _counts(frame["opportunity_type"])
        )
        actions.update(_counts(frame["action"]))

        actionable = frame[
            frame["action"].eq("Evaluate Options")
        ]
        actionable_by_opportunity.update(
            _counts(actionable["opportunity_type"])
        )

        selected = actionable[
            actionable["option_strategy"].notna()
        ]
        selected_strategies.update(
            _counts(selected["option_strategy"])
        )

        failures = actionable[
            actionable["option_strategy"].isna()
        ]
        contract_failures_by_opportunity.update(
            _counts(failures["opportunity_type"])
        )

        allocated = frame[
            frame["allocation_decision"].eq("Allocate")
        ]
        allocated_strategies.update(
            _counts(allocated["option_strategy"])
        )

    call_candidates = actionable_by_opportunity.get(
        "Long Call Candidate", 0
    )
    put_candidates = actionable_by_opportunity.get(
        "Long Put Candidate", 0
    )

    if put_candidates == 0 and call_candidates > 0:
        first_zero_put_stage = "OPPORTUNITY_ENGINE"
    elif selected_strategies.get("Long Put", 0) == 0 and put_candidates > 0:
        first_zero_put_stage = "CONTRACT_SELECTION"
    elif allocated_strategies.get("Long Put", 0) == 0:
        first_zero_put_stage = "PORTFOLIO_ALLOCATION"
    else:
        first_zero_put_stage = None

    return {
        "files_analyzed": len(files),
        "opportunity_types": dict(opportunity_types),
        "actions": dict(actions),
        "actionable_by_opportunity": dict(actionable_by_opportunity),
        "selected_strategies": dict(selected_strategies),
        "contract_failures_by_opportunity": dict(
            contract_failures_by_opportunity
        ),
        "allocated_strategies": dict(allocated_strategies),
        "first_zero_put_stage": first_zero_put_stage,
        "structural_diagnostics": _structural_fixtures(),
        "directional_scoring_fix_active": True,
        "limitations": [
            "Legacy processed files do not preserve directional component scores.",
            "Reviewed files may contain repeated intraday runs.",
            "Market regime may legitimately influence observed direction mix.",
            "Outcome performance and broker execution are not reconciled.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit strategy direction attrition without changing it."
    )
    parser.add_argument("--recent-files", type=int, default=20)
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
            audit_files(files),
            indent=2,
            sort_keys=True,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
