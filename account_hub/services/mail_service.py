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
        logger.warning("RESEND_API_KEY not set — email not sent. To: %s Subject: %s", to, subject)
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


def send_verification_email(to: str, username: str, token: str) -> None:
    """Send an email verification link."""
    url = f"{settings.app_url}/verify-email?token={token}"
    html = f"""
    <div style="font-family:'Outfit',system-ui,sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#060F1E;color:#D8EAF6;border-radius:12px">
      <div style="text-align:center;margin-bottom:32px">
        <span style="font-size:24px;font-weight:300;color:#E6F0FA;letter-spacing:-0.03em">account</span><span style="font-size:24px;font-weight:600;color:#2DD4BF;letter-spacing:-0.03em">hub</span>
      </div>
      <h2 style="margin:0 0 8px;font-size:20px;font-weight:500;color:white">Verify your email</h2>
      <p style="margin:0 0 24px;font-size:15px;color:#5A8FAE;line-height:1.6">
        Hi {username}, click the button below to verify your email address and unlock all features.
      </p>
      <div style="text-align:center;margin-bottom:24px">
        <a href="{url}" style="display:inline-block;padding:12px 32px;background:#2DD4BF;color:#060F1E;font-weight:600;font-size:14px;border-radius:8px;text-decoration:none">Verify Email</a>
      </div>
      <p style="margin:0;font-size:12px;color:#2F5470;line-height:1.5">
        Or copy this link: <a href="{url}" style="color:#2DD4BF;word-break:break-all">{url}</a>
      </p>
      <p style="margin:16px 0 0;font-size:12px;color:#2F5470">This link expires in 24 hours.</p>
    </div>
    """
    _send(to, "Verify your email — AccountHub", html)


def send_password_reset_email(to: str, username: str, token: str) -> None:
    """Send a password reset link."""
    url = f"{settings.app_url}/reset-password?token={token}"
    html = f"""
    <div style="font-family:'Outfit',system-ui,sans-serif;max-width:480px;margin:0 auto;padding:40px 24px;background:#060F1E;color:#D8EAF6;border-radius:12px">
      <div style="text-align:center;margin-bottom:32px">
        <span style="font-size:24px;font-weight:300;color:#E6F0FA;letter-spacing:-0.03em">account</span><span style="font-size:24px;font-weight:600;color:#2DD4BF;letter-spacing:-0.03em">hub</span>
      </div>
      <h2 style="margin:0 0 8px;font-size:20px;font-weight:500;color:white">Reset your password</h2>
      <p style="margin:0 0 24px;font-size:15px;color:#5A8FAE;line-height:1.6">
        Hi {username}, we received a request to reset your password. Click the button below to set a new one.
      </p>
      <div style="text-align:center;margin-bottom:24px">
        <a href="{url}" style="display:inline-block;padding:12px 32px;background:#2DD4BF;color:#060F1E;font-weight:600;font-size:14px;border-radius:8px;text-decoration:none">Reset Password</a>
      </div>
      <p style="margin:0;font-size:12px;color:#2F5470;line-height:1.5">
        Or copy this link: <a href="{url}" style="color:#2DD4BF;word-break:break-all">{url}</a>
      </p>
      <p style="margin:16px 0 0;font-size:12px;color:#2F5470">This link expires in 30 minutes. If you didn't request this, you can ignore this email.</p>
    </div>
    """
    _send(to, "Reset your password — AccountHub", html)
