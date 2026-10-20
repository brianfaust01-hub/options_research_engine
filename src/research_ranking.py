"""Versioned, research-only shadow ranking for investment theses."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import pandas as pd

POLICY_VERSION = "RRS-SHADOW-2026-10-10-v1"
POLICY_EFFECTIVE_DATE = pd.Timestamp("2026-10-10")
# v1 tests a research-only "confidence plus headroom" hypothesis. Strong
# consensus is rewarded, while already-mature directional trend/momentum reduce
# remaining runway. Other research fields are captured but deliberately not
# forced into the candidate after the intuitive all-positive formula failed.
WEIGHTS = {"consensus_confidence": 1 / 3, "trend_headroom": 1 / 3,
           "momentum_headroom": 1 / 3}

def _number(value):
    try: number = float(value)
    except (TypeError, ValueError): return None
    return None if pd.isna(number) else max(0.0, min(100.0, number))

def _direction(value) -> str:
    text = str(value or "").strip().upper()
    if "CALL" in text or text == "BULLISH": return "BULLISH"
    if "PUT" in text or text == "BEARISH": return "BEARISH"
    return "UNKNOWN"

def calculate_shadow_research_ranking(row: dict, mode: str = "FORWARD_SHADOW") -> dict:
    direction = _direction(row.get("Direction", row.get("direction", row.get("option_strategy"))))
    trend = _number(row.get("TrendScore"))
    momentum = _number(row.get("MomentumScore"))
    momentum_direction = _direction(row.get("MomentumDirection"))
    consensus = _number(row.get("ResearchScore", row.get("research_score", row.get("StrategyScore"))))
    conviction = _number(row.get("DirectionalConviction", row.get("directional_conviction")))
    time_edge = _number(row.get("time_edge_score", row.get("TimeEdgeScore")))
    directional_trend = trend if direction == "BULLISH" else (100.0 - trend if trend is not None and direction == "BEARISH" else None)
    momentum_alignment = momentum if momentum is not None and momentum_direction == direction else (0.0 if momentum is not None and direction != "UNKNOWN" else None)
    trend_headroom = None if directional_trend is None else 100.0 - directional_trend
    momentum_headroom = None if momentum_alignment is None else 100.0 - momentum_alignment
    components = {"consensus_confidence": consensus, "trend_headroom": trend_headroom,
                  "momentum_headroom": momentum_headroom}
    complete = all(value is not None for value in components.values())
    score = round(sum(components[name] * WEIGHTS[name] for name in WEIGHTS), 2) if complete else None
    return {"ResearchRankingScore": score, "ResearchRankingPolicyVersion": POLICY_VERSION,
            "ResearchRankingMode": mode, "ResearchRankingInputsComplete": complete,
            "ResearchRankingConsensusConfidence": consensus,
            "ResearchRankingDirectionalTrend": directional_trend,
            "ResearchRankingMomentumAlignment": momentum_alignment,
            "ResearchRankingTrendHeadroom": trend_headroom,
            "ResearchRankingMomentumHeadroom": momentum_headroom,
            "ResearchRankingDirectionalConviction": conviction,
            "ResearchRankingTimeEdge": time_edge,
            "ResearchRankingMarketContext": _number(row.get("market_score", row.get("MarketScore"))),
            "ResearchRankingBreadthContext": _number(row.get("breadth_score", row.get("BreadthScore")))}

def build_shadow_ledger(journal: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, series in journal.iterrows():
        source = series.to_dict()
        recommendation_date = pd.to_datetime(source.get("RecommendationDate"), errors="coerce")
        mode = (
            "FORWARD_SHADOW"
            if pd.notna(recommendation_date) and recommendation_date.normalize() >= POLICY_EFFECTIVE_DATE
            else "RETROSPECTIVE_SHADOW"
        )
        rows.append({"RecommendationID": source.get("RecommendationID"),
                     "RecommendationDate": source.get("RecommendationDate"),
                     "Ticker": source.get("ticker", source.get("Ticker")),
                     "Direction": source.get("Direction", source.get("direction")),
                     "_LegacyResearchScore": _number(source.get("ResearchScore", source.get("research_score"))),
                     **calculate_shadow_research_ranking(source, mode)})
    ledger = pd.DataFrame(rows)
    if ledger.empty:
        return ledger
    ledger["_RecommendationDay"] = pd.to_datetime(
        ledger["RecommendationDate"], errors="coerce", format="mixed"
    ).dt.normalize()
    valid = ledger["ResearchRankingScore"].notna() & ledger["_RecommendationDay"].notna()
    ledger["ShadowResearchRank"] = pd.NA
    ledger["ShadowResearchPercentile"] = pd.NA
    ledger.loc[valid, "ShadowResearchRank"] = ledger.loc[valid].groupby(
        "_RecommendationDay"
    )["ResearchRankingScore"].rank(method="first", ascending=False)
    ledger.loc[valid, "ShadowResearchPercentile"] = ledger.loc[valid].groupby(
        "_RecommendationDay"
    )["ResearchRankingScore"].rank(method="average", pct=True, ascending=True)
    ledger["ShadowResearchShortlistTop8"] = pd.to_numeric(
        ledger["ShadowResearchRank"], errors="coerce"
    ).le(8)
    shortlist = ledger["ShadowResearchShortlistTop8"] & ledger["_LegacyResearchScore"].notna()
    ledger["ShadowResearchTwoStageRank"] = pd.NA
    ledger.loc[shortlist, "ShadowResearchTwoStageRank"] = ledger.loc[shortlist].groupby(
        "_RecommendationDay"
    )["_LegacyResearchScore"].rank(method="first", ascending=False)
    two_stage_rank = pd.to_numeric(ledger["ShadowResearchTwoStageRank"], errors="coerce")
    ledger["ShadowResearchTwoStageTop3"] = two_stage_rank.le(3)
    ledger["ShadowResearchTwoStageTop5"] = two_stage_rank.le(5)
    return ledger.drop(columns=["_LegacyResearchScore", "_RecommendationDay"])

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--journal", type=Path, default=Path("data/trade_journal.csv"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/research_ranking_shadow.csv"))
    args = parser.parse_args()
    ledger = build_shadow_ledger(pd.read_csv(args.journal, low_memory=False))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_csv(args.output, index=False)
    print(json.dumps({"policy_version": POLICY_VERSION, "rows": len(ledger),
                      "complete": int(ledger["ResearchRankingInputsComplete"].sum()),
                      "incomplete": int((~ledger["ResearchRankingInputsComplete"]).sum()),
                      "production_policy_changed": False, "output": str(args.output)}))

if __name__ == "__main__": main()
