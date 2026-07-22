"""
Project Stonks
Trade Recommendation Model

Sprint 32B
Institutional Execution Engine
"""

from dataclasses import dataclass


@dataclass
class TradeRecommendation:

    # ------------------------------------------------------------------
    # Core Recommendation
    # ------------------------------------------------------------------

    ticker: str

    opportunity_type: str

    action: str

    confidence: int

    expected_apr: float | None

    # ------------------------------------------------------------------
    # Option Details
    # ------------------------------------------------------------------

    option_strategy: str | None

    option_type: str | None

    expiration: str | None

    strike: float | None

    premium: float | None

    # ------------------------------------------------------------------
    # Position Sizing
    # ------------------------------------------------------------------

    position_size_pct: float | None

    position_value: float | None

    max_risk_dollars: float | None

    contracts: int | None

    # ------------------------------------------------------------------
    # Exit Plan
    # ------------------------------------------------------------------

    profit_target_pct: float | None

    stop_loss_pct: float | None

    time_stop_dte: int | None

    # ------------------------------------------------------------------
    # Trade Quality
    # ------------------------------------------------------------------

    trade_quality_score: int | None

    trade_quality_grade: str | None

    # ------------------------------------------------------------------
    # Execution Engine (Sprint 32B)
    # ------------------------------------------------------------------

    execution_score: float | None = None

    execution_grade: str | None = None

    execution_friction: str | None = None

    spread_pct: float | None = None

    spread_dollars: float | None = None

    research_price: float | None = None

    research_price_method: str | None = None

    execution_entry_price: float | None = None

    execution_entry_method: str | None = None

    execution_exit_price: float | None = None

    execution_exit_method: str | None = None

    entry_execution_cost_pct: float | None = None

    immediate_liquidation_return_pct: float | None = None

    last_trade_price: float | None = None

    option_volume: int | None = None

    option_open_interest: int | None = None

    execution_engine_test_mode: bool = False

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    notes: list[str] | None = None