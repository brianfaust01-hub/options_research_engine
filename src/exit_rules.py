"""
Project Stonks
Exit Rules Engine

Sprint 18:
Adds predefined trade management rules for paper-trading recommendations.
"""


def build_exit_plan(
    confidence: int,
    premium: float | None,
    dte: int | None,
    theta: float | None,
):
    if premium is None:
        return {
            "profit_target_pct": None,
            "stop_loss_pct": None,
            "time_stop_dte": None,
            "exit_notes": [],
        }

    if confidence >= 90:
        profit_target_pct = 0.75
        stop_loss_pct = 0.35
    elif confidence >= 80:
        profit_target_pct = 0.60
        stop_loss_pct = 0.35
    elif confidence >= 70:
        profit_target_pct = 0.50
        stop_loss_pct = 0.30
    else:
        profit_target_pct = 0.40
        stop_loss_pct = 0.25

    time_stop_dte = 14

    target_price = premium * (1 + profit_target_pct)
    stop_price = premium * (1 - stop_loss_pct)

    exit_notes = [
        f"Profit target: +{profit_target_pct * 100:.0f}% (${target_price:.2f})",
        f"Stop loss: -{stop_loss_pct * 100:.0f}% (${stop_price:.2f})",
        f"Time stop: exit at {time_stop_dte} DTE",
    ]

    if theta is not None and premium > 0:
        theta_drag_pct = abs(theta) / premium

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
        "exit_notes": exit_notes,
    }