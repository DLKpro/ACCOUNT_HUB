from __future__ import annotations

import logging

import resend

from account_hub.config import settings

logger = logging.getLogger("account_hub.mail")


def _send(to: str, subject: str, html: str) -> None:
    """Send an email via Resend. Falls back to logging if no API key or in test mode."""
    import os
    if os.environ.get("TESTING") == "1":
        logger.info("TEST MODE — email skipped. To: %s Subject: %s", to, subject)
        return

    if not settings.resend_api_key:
        logger.warning(
            "RESEND_API_KEY not set — email not sent. To: %s Subject: %s",
            to, subject,
        )
        return

    resend.api_key = settings.resend_api_key
    try:
        resend.Emails.send({
            "from": settings.from_email,
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info("Email sent to %s: %s", to, subject)
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to, e)


_EMAIL_STYLE = """\
<style>
  .email-wrap {
    font-family: 'Outfit', system-ui, sans-serif;
    max-width: 480px;
    margin: 0 auto;
    padding: 40px 24px;
    background: #060F1E;
    color: #D8EAF6;
    border-radius: 12px;
  }
  .email-logo {
    text-align: center;
    margin-bottom: 32px;
  }
  .email-logo .light {
    font-size: 24px;
    font-weight: 300;
    color: #E6F0FA;
    letter-spacing: -0.03em;
  }
  .email-logo .accent {
    font-size: 24px;
    font-weight: 600;
    color: #2DD4BF;
    letter-spacing: -0.03em;
  }
  .email-heading {
    margin: 0 0 8px;
    font-size: 20px;
    font-weight: 500;
    color: white;
  }
  .email-body {
    margin: 0 0 24px;
    font-size: 15px;
    color: #5A8FAE;
    line-height: 1.6;
  }
  .email-btn-wrap {
    text-align: center;
    margin-bottom: 24px;
  }
  .email-btn {
    display: inline-block;
    padding: 12px 32px;
    background: #2DD4BF;
    color: #060F1E;
    font-weight: 600;
    font-size: 14px;
    border-radius: 8px;
    text-decoration: none;
  }
  .email-link {
    margin: 0;
    font-size: 12px;
    color: #2F5470;
    line-height: 1.5;
  }
  .email-link a {
    color: #2DD4BF;
    word-break: break-all;
  }
  .email-footer {
    margin: 16px 0 0;
    font-size: 12px;
    color: #2F5470;
  }
</style>
"""


def send_verification_email(to: str, username: str, token: str) -> None:
    """Send an email verification link."""
    url = f"{settings.app_url}/verify-email?token={token}"
    html = f"""\
{_EMAIL_STYLE}
<div class="email-wrap">
  <div class="email-logo">
    <span class="light">account</span>\
<span class="accent">hub</span>
  </div>
  <h2 class="email-heading">Verify your email</h2>
  <p class="email-body">
    Hi {username}, click the button below to verify your
    email address and unlock all features.
  </p>
  <div class="email-btn-wrap">
    <a href="{url}" class="email-btn">Verify Email</a>
  </div>
  <p class="email-link">
    Or copy this link: <a href="{url}">{url}</a>
  </p>
  <p class="email-footer">
    This link expires in 24 hours.
  </p>
</div>
"""
    _send(to, "Verify your email — AccountHub", html)


def send_password_reset_email(to: str, username: str, token: str) -> None:
    """Send a password reset link."""
    url = f"{settings.app_url}/reset-password?token={token}"
    html = f"""\
{_EMAIL_STYLE}
<div class="email-wrap">
  <div class="email-logo">
    <span class="light">account</span>\
<span class="accent">hub</span>
  </div>
  <h2 class="email-heading">Reset your password</h2>
  <p class="email-body">
    Hi {username}, we received a request to reset your
    password. Click the button below to set a new one.
  </p>
  <div class="email-btn-wrap">
    <a href="{url}" class="email-btn">Reset Password</a>
  </div>
  <p class="email-link">
    Or copy this link: <a href="{url}">{url}</a>
  </p>
  <p class="email-footer">
    This link expires in 30 minutes.
    If you didn't request this, you can ignore this email.
  </p>
</div>
"""
    _send(to, "Reset your password — AccountHub", html)
