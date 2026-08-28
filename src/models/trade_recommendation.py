"""
Project Stonks
Trade Recommendation Model

Sprint 33A
Institutional Trade Score
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
    # Hindsight Research Context (Sprint 34A)
    # ------------------------------------------------------------------

    research_score: float | None

    opportunity_score: float | None

    bullish_score: float | None

    bearish_score: float | None

    directional_conviction: float | None

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

    # Greek and volatility observations (shadow research only)
    broker_delta: float | None = None
    broker_gamma: float | None = None
    broker_theta: float | None = None
    broker_vega: float | None = None
    broker_rho: float | None = None
    implied_volatility: float | None = None
    iv_rank: float | None = None
    iv_percentile: float | None = None
    estimated_delta: float | None = None
    estimated_theta: float | None = None
    theta_drag_pct_per_day: float | None = None
    gamma_per_premium: float | None = None
    vega_per_premium: float | None = None
    greeks_source: str | None = None
    iv_context_status: str | None = None

    # ------------------------------------------------------------------
    # Institutional Trade Score (Sprint 33A)
    # ------------------------------------------------------------------

    institutional_trade_score: float | None = None

    institutional_trade_grade: str | None = None

    institutional_research_score: float | None = None

    institutional_contract_score: float | None = None

    institutional_execution_score: float | None = None

    institutional_trade_quality_score: float | None = None

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    notes: list[str] | None = None
