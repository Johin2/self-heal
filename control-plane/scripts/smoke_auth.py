"""End-to-end smoke for the magic-link auth flow.

Captures the link in-process (no real email), verifies, then hits /me
with the returned cookie.

Usage:
    python -m scripts.smoke_auth
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx

from app.main import app


async def main() -> int:
    captured: dict[str, str] = {}

    async def _capture(*, to: str, link: str) -> None:
        captured["to"] = to
        captured["link"] = link

    with patch("app.routes.auth.send_magic_link", side_effect=_capture):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Request the magic link
            r1 = await client.post(
                "/v1/auth/request-link", json={"email": "smoke@self-heal.dev"}
            )
            print("request-link:", r1.status_code, r1.json())
            if r1.status_code != 200:
                return 1
            if "link" not in captured:
                print("send_magic_link was not called", file=sys.stderr)
                return 1

            token = parse_qs(urlsplit(captured["link"]).query)["token"][0]
            print("captured token len:", len(token))

            # 2. Verify the token
            r2 = await client.post("/v1/auth/verify", json={"token": token})
            print("verify:      ", r2.status_code, r2.json())
            if r2.status_code != 200:
                return 1

            # 3. Use the cookie to call /me
            r3 = await client.get("/v1/auth/me")
            print("me:          ", r3.status_code, r3.json())
            if r3.status_code != 200:
                return 1

            # 4. Replay token -> should fail (single use)
            r4 = await client.post("/v1/auth/verify", json={"token": token})
            print("replay:      ", r4.status_code, r4.json())
            if r4.status_code != 400:
                return 1

            # 5. Logout, then /me should 401
            r5 = await client.post("/v1/auth/logout")
            print("logout:      ", r5.status_code)
            r6 = await client.get("/v1/auth/me")
            print("me-post-out: ", r6.status_code, r6.json())
            if r6.status_code != 401:
                return 1

    print("\nALL OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
