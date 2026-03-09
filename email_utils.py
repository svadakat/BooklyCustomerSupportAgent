"""
email_utils.py — SMTP email helper for Bookly support notifications.

Configure via .env:
    SMTP_HOST      e.g. smtp.gmail.com
    SMTP_PORT      e.g. 587
    SMTP_USER      sender address / login
    SMTP_PASSWORD  app password or SMTP credential
    FROM_EMAIL     optional display address (defaults to SMTP_USER)
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(to_email: str, subject: str, body: str) -> dict:
    """
    Send a plain-text email.
    If EMAIL_OVERRIDE is set, all emails are redirected to that address.
    Returns {"sent": True} on success or {"sent": False, "reason": "..."} otherwise.
    """
    host = os.environ.get("SMTP_HOST", "")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    password = os.environ.get("SMTP_PASSWORD", "")
    from_addr = os.environ.get("FROM_EMAIL", user)

    override = os.environ.get("EMAIL_OVERRIDE", "")
    if override:
        to_email = override

    if not all([host, user, password]):
        return {"sent": False, "reason": "SMTP not configured"}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Bookly Support <{from_addr}>"
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(user, password)
            smtp.sendmail(from_addr, to_email, msg.as_string())
        return {"sent": True}
    except Exception as exc:
        return {"sent": False, "reason": str(exc)}
