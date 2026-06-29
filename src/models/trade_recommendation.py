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

    position_size_pct: float | None

    notes: list[str]