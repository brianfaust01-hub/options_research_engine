"""Research-only model discovery with recommendation-date holdouts."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

from config_combination_analysis import post_fix_episode_frame

BASE_FEATURES = [
    "consensus", "directional_trend", "momentum_alignment", "conviction",
    "time_edge", "directional_sma20", "directional_sma50",
    "directional_sma200", "directional_macd", "directional_rsi",
    "atr_pct", "log_volume",
]

def prepare_frame(hindsight: pd.DataFrame, journal: pd.DataFrame) -> pd.DataFrame:
    episodes = post_fix_episode_frame(hindsight)
    fields = ["RecommendationID", "TrendScore", "MomentumScore", "MomentumDirection",
              "DirectionalConviction", "time_edge_score", "Close", "SMA_20", "SMA_50",
              "SMA_200", "RSI_14", "MACD", "MACD_Signal", "ATR_14", "Avg_Volume_20"]
    source = journal[[field for field in fields if field in journal]].drop_duplicates("RecommendationID", keep="last")
    frame = episodes.merge(source, on="RecommendationID", how="left", suffixes=("", "_journal"))
    direction_sign = frame["_Direction"].map({"BULLISH": 1.0, "BEARISH": -1.0})
    close = pd.to_numeric(frame["Close"], errors="coerce")
    frame["consensus"] = pd.to_numeric(frame["ResearchScore"], errors="coerce")
    trend = pd.to_numeric(frame["TrendScore"], errors="coerce")
    frame["directional_trend"] = np.where(direction_sign.eq(1), trend, 100 - trend)
    momentum = pd.to_numeric(frame["MomentumScore"], errors="coerce")
    momentum_direction = frame["MomentumDirection"].astype(str).str.upper()
    frame["momentum_alignment"] = np.where(momentum_direction.eq(frame["_Direction"]), momentum, 0)
    frame["conviction"] = pd.to_numeric(frame["DirectionalConviction"], errors="coerce")
    frame["time_edge"] = pd.to_numeric(frame["TimeEdgeScore"], errors="coerce")
    for days in (20, 50, 200):
        sma = pd.to_numeric(frame[f"SMA_{days}"], errors="coerce")
        frame[f"directional_sma{days}"] = direction_sign * (close / sma - 1)
    frame["directional_macd"] = direction_sign * (
        pd.to_numeric(frame["MACD"], errors="coerce")
        - pd.to_numeric(frame["MACD_Signal"], errors="coerce")
    ) / close
    frame["directional_rsi"] = direction_sign * (pd.to_numeric(frame["RSI_14"], errors="coerce") - 50) / 50
    frame["atr_pct"] = pd.to_numeric(frame["ATR_14"], errors="coerce") / close
    frame["log_volume"] = np.log1p(pd.to_numeric(frame["Avg_Volume_20"], errors="coerce"))
    return frame.dropna(subset=BASE_FEATURES + ["_Return", "_Date"])

def _expand(values: np.ndarray, interactions: bool) -> np.ndarray:
    if not interactions:
        return values
    columns = [values]
    columns.extend((values[:, left] * values[:, right])[:, None]
                   for left in range(values.shape[1]) for right in range(left + 1, values.shape[1]))
    return np.hstack(columns)

def _ridge_predict(train_x, train_y, test_x, alpha: float, interactions: bool) -> np.ndarray:
    mean = train_x.mean(axis=0); scale = train_x.std(axis=0); scale[scale == 0] = 1
    train = _expand((train_x - mean) / scale, interactions)
    test = _expand((test_x - mean) / scale, interactions)
    design = np.column_stack([np.ones(len(train)), train])
    penalty = np.eye(design.shape[1]) * alpha; penalty[0, 0] = 0
    coefficients = np.linalg.solve(design.T @ design + penalty, design.T @ train_y)
    return np.column_stack([np.ones(len(test)), test]) @ coefficients

def _logistic_predict(train_x, train_y, test_x, alpha: float, interactions: bool) -> np.ndarray:
    mean = train_x.mean(axis=0); scale = train_x.std(axis=0); scale[scale == 0] = 1
    train = _expand((train_x - mean) / scale, interactions)
    test = _expand((test_x - mean) / scale, interactions)
    design = np.column_stack([np.ones(len(train)), train]); beta = np.zeros(design.shape[1])
    penalty = np.ones(len(beta)) * alpha; penalty[0] = 0
    for _ in range(50):
        linear = np.clip(design @ beta, -30, 30); probability = 1 / (1 + np.exp(-linear))
        weights = np.maximum(probability * (1 - probability), 1e-6)
        gradient = design.T @ (probability - train_y) + penalty * beta
        hessian = design.T @ (design * weights[:, None]) + np.diag(penalty)
        step = np.linalg.solve(hessian, gradient); beta -= step
        if np.max(np.abs(step)) < 1e-7: break
    linear = np.clip(np.column_stack([np.ones(len(test)), test]) @ beta, -30, 30)
    return 1 / (1 + np.exp(-linear))

def _auc(scores, wins):
    positive = np.asarray(scores)[np.asarray(wins)]; negative = np.asarray(scores)[~np.asarray(wins)]
    if not len(positive) or not len(negative): return None
    differences = positive[:, None] - negative[None, :]
    return float(((differences > 0).sum() + .5 * (differences == 0).sum()) / differences.size)

def _selection_metrics(frame: pd.DataFrame, score_col: str, count: int) -> dict:
    selected = frame.sort_values(["_Date", score_col], ascending=[True, False]).groupby("_Date").head(count)
    returns = selected["_Return"]; gains = returns[returns > 0].sum(); losses = -returns[returns < 0].sum()
    return {"episodes": int(len(selected)), "win_rate": float(returns.gt(0).mean()),
            "average_return": float(returns.mean()),
            "profit_factor": None if losses == 0 else float(gains / losses),
            "worst_return": float(returns.min())}

def discover_models(frame: pd.DataFrame) -> dict:
    values = frame[BASE_FEATURES].to_numpy(float); target = frame["_Return"].clip(-.10, .10).to_numpy(float)
    candidates = []
    for interactions in (False, True):
        for alpha in (1.0, 10.0, 100.0):
            for objective in ("return", "win"):
                predictions = pd.Series(index=frame.index, dtype=float)
                for date in sorted(frame["_Date"].unique()):
                    test = frame["_Date"].eq(date).to_numpy(); train = ~test
                    if objective == "return":
                        predicted = _ridge_predict(values[train], target[train], values[test], alpha, interactions)
                    else:
                        predicted = _logistic_predict(values[train], (target[train] > 0).astype(float), values[test], alpha, interactions)
                    predictions.loc[frame.index[test]] = predicted
                name = f"{'ridge' if objective == 'return' else 'logistic'}_{'interactions' if interactions else 'linear'}_a{alpha:g}"
                candidate = frame.copy(); candidate["_ModelScore"] = predictions
                candidates.append({"model": name, "objective": objective, "alpha": alpha, "interactions": interactions,
                    "auc": _auc(predictions, frame["_Return"].gt(0)),
                    "spearman_return": float(predictions.corr(frame["_Return"], method="spearman")),
                    "top3": _selection_metrics(candidate, "_ModelScore", 3),
                    "top5": _selection_metrics(candidate, "_ModelScore", 5),
                    "top10": _selection_metrics(candidate, "_ModelScore", 10)})
    benchmark = frame.copy(); benchmark["_Legacy"] = pd.to_numeric(frame["ResearchScore"])
    benchmark["_V1"] = (frame["consensus"] + (100-frame["directional_trend"]) + (100-frame["momentum_alignment"])) / 3
    baselines = {}
    for name, column in (("legacy", "_Legacy"), ("shadow_v1", "_V1")):
        baselines[name] = {"auc": _auc(benchmark[column], benchmark["_Return"].gt(0)),
            "spearman_return": float(benchmark[column].corr(benchmark["_Return"], method="spearman")),
            "top3": _selection_metrics(benchmark, column, 3), "top5": _selection_metrics(benchmark, column, 5),
            "top10": _selection_metrics(benchmark, column, 10)}
    candidates.sort(key=lambda row: (row["top3"]["average_return"], row["top5"]["average_return"], row["auc"]), reverse=True)
    return {"episodes": len(frame), "dates": int(frame["_Date"].nunique()), "features": BASE_FEATURES,
            "baselines": baselines, "candidates": candidates}

def render(result: dict) -> str:
    lines = ["# Research Ranking Model Discovery", "", "**Method:** leave-one-recommendation-date-out predictions; research-only inputs; clipped-return ridge targets; no production change", "",
             "| Model | AUC | Spearman | Top 3 avg | Top 3 win | Top 5 avg | Top 10 avg |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    rows = [{"model": name, **value} for name, value in result["baselines"].items()] + result["candidates"]
    for row in rows:
        lines.append(f"| {row['model']} | {row['auc']:.3f} | {row['spearman_return']:.3f} | {100*row['top3']['average_return']:+.2f}% | {100*row['top3']['win_rate']:.1f}% | {100*row['top5']['average_return']:+.2f}% | {100*row['top10']['average_return']:+.2f}% |")
    lines += ["", "Models are discovery candidates only. Four independent recommendation dates are insufficient for production promotion.", ""]
    return "\n".join(lines)

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("source",type=Path); parser.add_argument("--journal",type=Path,default=Path("data/trade_journal.csv")); parser.add_argument("--output-dir",type=Path,default=Path("reports")); args=parser.parse_args()
    result=discover_models(prepare_frame(pd.read_csv(args.source,low_memory=False),pd.read_csv(args.journal,low_memory=False)))
    args.output_dir.mkdir(parents=True,exist_ok=True); stamp=datetime.now().strftime("%Y%m%d_%H%M%S")
    md=args.output_dir/f"research_ranking_model_search_{stamp}.md"; js=args.output_dir/f"research_ranking_model_search_{stamp}.json"
    md.write_text(render(result),encoding="utf-8"); js.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(md); print(js)
if __name__ == "__main__": main()
