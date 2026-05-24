"""Email delivery. Resend in prod, console-print in dev.

If RESEND_API_KEY is empty we log the message to stderr instead of
calling the API. That keeps local dev usable without credentials.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

_log = logging.getLogger("app.email")


async def send_magic_link(*, to: str, link: str) -> None:
    settings = get_settings()
    subject = "Sign in to self-heal"
    text_body = (
        f"Click to sign in: {link}\n\n"
        f"This link expires in {settings.magic_link_ttl_minutes} minutes "
        "and can be used once.\n\n"
        "If you didn't request this, ignore the message."
    )
    html_body = (
        f"<p>Click to sign in:</p>"
        f'<p><a href="{link}">{link}</a></p>'
        f"<p>This link expires in {settings.magic_link_ttl_minutes} minutes "
        "and can be used once.</p>"
        "<p>If you didn't request this, ignore the message.</p>"
    )

    if not settings.resend_api_key:
        _log.warning(
            "RESEND_API_KEY not set — printing magic link instead of sending:\n  to=%s\n  link=%s",
            to,
            link,
        )
        return

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from,
                "to": [to],
                "subject": subject,
                "text": text_body,
                "html": html_body,
            },
        )
        if resp.status_code >= 300:
            _log.error("resend send failed: %s %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
