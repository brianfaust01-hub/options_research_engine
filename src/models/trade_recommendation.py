"""
Project Stonks
Trade Recommendation Model
"""

from dataclasses import dataclass


@dataclass
class TradeRecommendation:

    ticker: str

    opportunity_type: str

    action: str

    confidence: int

    expected_apr: float | None

    option_strategy: str | None

    option_type: str | None

    expiration: str | None

    strike: float | None

    premium: float | None

    position_size_pct: float | None

    position_value: float | None

    max_risk_dollars: float | None

    contracts: int | None

    profit_target_pct: float | None

    stop_loss_pct: float | None

    time_stop_dte: int | None

    trade_quality_score: int | None

    trade_quality_grade: str | None

    notes: list[str]