from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def send_email_report(
    report_path: str | Path,
    subject: str = "Project Stonks Daily Report",
) -> None:
    report_path = Path(report_path)

    smtp_host = os.getenv("STONKS_SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("STONKS_SMTP_PORT", "587"))
    smtp_user = os.getenv("STONKS_SMTP_USER")
    smtp_password = os.getenv("STONKS_SMTP_PASSWORD")
    email_to = os.getenv("STONKS_EMAIL_TO", smtp_user)

    if not smtp_user or not smtp_password or not email_to:
        raise ValueError(
            "Missing email settings. Set STONKS_SMTP_USER, "
            "STONKS_SMTP_PASSWORD, and STONKS_EMAIL_TO."
        )

    body = report_path.read_text(encoding="utf-8")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg["Subject"] = subject
    msg.set_content(body)

    msg.add_attachment(
        body.encode("utf-8"),
        maintype="text",
        subtype="markdown",
        filename=report_path.name,
    )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)