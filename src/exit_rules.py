"""
Project Stonks
Exit Rules Engine

Sprint 18:
Adds predefined trade management rules for paper-trading recommendations.
"""


def build_profit_protection_stop(
    entry_price: float | None,
    current_price: float | None,
    original_stop: float | None,
    prior_recommended_stop: float | None = None,
    prior_peak_price: float | None = None,
    implied_volatility: float | None = None,
    spread_pct: float | None = None,
):
    """Build a one-way, volatility-aware stop ratchet for a long option."""
    numeric = (entry_price, current_price, original_stop)
    if any(value is None or value <= 0 for value in numeric):
        return {
            "stop_action": "KEEP STOP",
            "recommended_stop": original_stop,
            "peak_price": prior_peak_price,
            "peak_gain_pct": None,
            "locked_profit_pct": None,
            "trail_width_pct": None,
            "reason": "Profit protection unavailable because pricing is incomplete",
        }

    prior_stop = (
        prior_recommended_stop
        if prior_recommended_stop is not None and prior_recommended_stop > 0
        else original_stop
    )
    peak_price = max(entry_price, current_price, prior_peak_price or 0.0)
    peak_gain_pct = peak_price / entry_price - 1
    if peak_gain_pct < 0.10:
        return {
            "stop_action": "KEEP STOP",
            "recommended_stop": round(max(original_stop, prior_stop), 2),
            "peak_price": round(peak_price, 2),
            "peak_gain_pct": peak_gain_pct,
            "locked_profit_pct": max(0.0, prior_stop / entry_price - 1),
            "trail_width_pct": None,
            "reason": "Peak gain has not reached the 10% profit-protection trigger",
        }

    lock_fraction = 0.20 if peak_gain_pct < 0.20 else 0.35 if peak_gain_pct < 0.35 else 0.50
    profit_floor = entry_price * (1 + peak_gain_pct * lock_fraction)

    trail_width_pct = 0.15
    if implied_volatility is not None:
        if implied_volatility >= 0.80:
            trail_width_pct = 0.20
        elif implied_volatility >= 0.60:
            trail_width_pct = 0.18
        elif implied_volatility <= 0.30:
            trail_width_pct = 0.10
    if spread_pct is not None and spread_pct > 0:
        trail_width_pct = max(trail_width_pct, min(0.25, spread_pct * 2))
    trailing_floor = peak_price * (1 - trail_width_pct)

    uncapped_stop = max(original_stop, prior_stop, profit_floor, trailing_floor)
    quote_buffer_pct = max(0.02, min(0.10, (spread_pct or 0.0) * 1.5))
    current_price_cap = current_price * (1 - quote_buffer_pct)
    recommended_stop = round(max(prior_stop, min(uncapped_stop, current_price_cap)), 2)
    prior_stop_rounded = round(prior_stop, 2)
    stop_action = "RAISE STOP" if recommended_stop > prior_stop_rounded else "KEEP STOP"
    effective_locked_profit = recommended_stop / entry_price - 1
    return {
        "stop_action": stop_action,
        "recommended_stop": recommended_stop,
        "peak_price": round(peak_price, 2),
        "peak_gain_pct": peak_gain_pct,
        "locked_profit_pct": effective_locked_profit,
        "trail_width_pct": trail_width_pct,
        "reason": (
            f"Peak gain {peak_gain_pct:.1%}; locks {effective_locked_profit:.1%} "
            f"versus entry with a {trail_width_pct:.1%} volatility/spread trail"
        ),
    }


def build_exit_plan(
    confidence: int,
    premium: float | None,
    dte: int | None,
    theta: float | None,
    entry_price: float | None = None,
    implied_volatility: float | None = None,
    spread_pct: float | None = None,
    execution_score: float | None = None,
    time_edge_score: float | None = None,
    expected_move_window_days: int | None = None,
):
    if premium is None:
        return {
            "profit_target_pct": None,
            "stop_loss_pct": None,
            "time_stop_dte": None,
            "profit_target_price": None,
            "stop_loss_price": None,
            "exit_reference_price": None,
            "stop_loss_reason": None,
            "profit_target_reason": None,
            "exit_notes": [],
        }

    # Adaptive paper-trading stop. Twenty percent is a hard backstop, not a
    # default target. Observable evidence can tighten the stop toward 5%, but
    # the quote-noise floor prevents a stop from sitting inside normal spread.
    stop_loss_pct = 0.20
    stop_reasons = ["20% maximum planned-loss backstop"]

    if expected_move_window_days is not None:
        if expected_move_window_days <= 5:
            stop_loss_pct -= 0.04
            stop_reasons.append("five-day-or-shorter thesis (-4%)")
        elif expected_move_window_days <= 7:
            stop_loss_pct -= 0.03
            stop_reasons.append("seven-day-or-shorter thesis (-3%)")
        elif expected_move_window_days <= 14:
            stop_loss_pct -= 0.01
            stop_reasons.append("short thesis window (-1%)")

    if execution_score is not None:
        if execution_score >= 90:
            stop_loss_pct -= 0.03
            stop_reasons.append("excellent execution quality (-3%)")
        elif execution_score >= 80:
            stop_loss_pct -= 0.02
            stop_reasons.append("strong execution quality (-2%)")

    if spread_pct is not None:
        if spread_pct <= 0.02:
            stop_loss_pct -= 0.02
            stop_reasons.append("tight spread (-2%)")
        elif spread_pct <= 0.05:
            stop_loss_pct -= 0.01
            stop_reasons.append("acceptable spread (-1%)")

    if time_edge_score is not None:
        if time_edge_score >= 85:
            stop_loss_pct -= 0.03
            stop_reasons.append("high Time Edge (-3%)")
        elif time_edge_score >= 75:
            stop_loss_pct -= 0.02
            stop_reasons.append("positive Time Edge (-2%)")

    theta_drag_pct = None
    if theta is not None and premium > 0:
        theta_drag_pct = abs(theta) / premium
        if theta_drag_pct >= 0.03:
            stop_loss_pct -= 0.02
            stop_reasons.append("high daily theta drag (-2%)")

    if implied_volatility is not None:
        if implied_volatility >= 0.80:
            stop_loss_pct += 0.04
            stop_reasons.append("very high IV noise allowance (+4%)")
        elif implied_volatility >= 0.60:
            stop_loss_pct += 0.02
            stop_reasons.append("high IV noise allowance (+2%)")
        elif implied_volatility <= 0.30:
            stop_loss_pct -= 0.01
            stop_reasons.append("low IV (-1%)")

    quote_noise_floor = 0.05
    if spread_pct is not None:
        quote_noise_floor = max(quote_noise_floor, min(0.20, spread_pct * 2))
    stop_loss_pct = round(max(quote_noise_floor, min(0.20, stop_loss_pct)), 3)
    if stop_loss_pct == quote_noise_floor and quote_noise_floor > 0.05:
        stop_reasons.append(f"quote-noise floor ({quote_noise_floor:.1%})")

    # Target is expressed as a multiple of planned risk, not an arbitrary
    # confidence bucket. Stronger/faster evidence can demand more reward while
    # theta drag reduces the amount of time we should wait for a large winner.
    reward_multiple = 2.0
    target_reasons = ["2.00x planned-loss base reward"]
    if time_edge_score is not None:
        if time_edge_score >= 85:
            reward_multiple += 0.50
            target_reasons.append("high Time Edge (+0.50R)")
        elif time_edge_score >= 75:
            reward_multiple += 0.25
            target_reasons.append("positive Time Edge (+0.25R)")
    if confidence >= 90:
        reward_multiple += 0.25
        target_reasons.append("high research confidence (+0.25R)")
    if implied_volatility is not None and implied_volatility >= 0.80:
        reward_multiple += 0.25
        target_reasons.append("very high IV upside allowance (+0.25R)")
    if theta_drag_pct is not None and theta_drag_pct >= 0.03:
        reward_multiple -= 0.25
        target_reasons.append("high theta drag (-0.25R)")

    profit_target_pct = round(
        max(0.10, min(0.50, stop_loss_pct * reward_multiple)), 3
    )
    target_reasons.append(f"bounded target {profit_target_pct:.1%}")

    time_stop_dte = 14

    reference_price = entry_price if entry_price is not None and entry_price > 0 else premium
    target_price = reference_price * (1 + profit_target_pct)
    stop_price = reference_price * (1 - stop_loss_pct)

    exit_notes = [
        f"Profit target: +{profit_target_pct * 100:.0f}% (${target_price:.2f})",
        f"Stop loss: -{stop_loss_pct * 100:.0f}% (${stop_price:.2f})",
        "Stop basis: " + "; ".join(stop_reasons),
        "Target basis: " + "; ".join(target_reasons),
        f"Time stop: exit at {time_stop_dte} DTE",
    ]

    if theta_drag_pct is not None:
        exit_notes.append(
            f"Theta drag: {theta_drag_pct * 100:.2f}% of premium per day"
        )

        if theta_drag_pct >= 0.04:
            exit_notes.append("High theta risk: monitor closely")

    if dte is not None and dte <= time_stop_dte:
        exit_notes.append("Contract already near time stop")

    return {
        "profit_target_pct": profit_target_pct,
        "stop_loss_pct": stop_loss_pct,
        "time_stop_dte": time_stop_dte,
        "profit_target_price": round(target_price, 2),
        "stop_loss_price": round(stop_price, 2),
        "exit_reference_price": reference_price,
        "stop_loss_reason": "; ".join(stop_reasons),
        "profit_target_reason": "; ".join(target_reasons),
        "exit_notes": exit_notes,
    }
