"""Google "Sign in with Google" -- server-side OAuth 2.0 authorization
code flow (RFC 6749) + OpenID Connect userinfo, not Google's newer
client-side Identity Services JS SDK. This app is a stateless JWT
bearer-token API with no server-side session store, so the classic
redirect-based flow fits best: routers/oauth.py's /start redirects the
browser to Google, Google redirects back with a code, this module
exchanges it server-side (the client secret never touches the browser)
and the router mints our own JWT the same way /auth/login does.

Endpoints below are Google's stable, official OAuth 2.0 / OIDC endpoints
(developers.google.com/identity/protocols/oauth2/web-server) -- unlike
the Hugging Face Inference Providers routing layer elsewhere in this
codebase, these have been unchanged for years and aren't the kind of
vendor-specific routing detail that needs live discovery before
trusting them. Still verified live once real credentials exist, per
this project's standing rule of confirming every external integration
actually works end-to-end before calling it done.
"""
from __future__ import annotations

import os
from typing import Optional, TypedDict

import httpx

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPE = "openid email profile"
TIMEOUT_S = 15.0


class GoogleProfile(TypedDict):
    sub: str
    email: str


def is_configured() -> bool:
    return bool(os.environ.get("GOOGLE_OAUTH_CLIENT_ID") and os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"))


def build_authorize_url(redirect_uri: str, state: str) -> str:
    params = {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "state": state,
        "prompt": "select_account",
    }
    return str(httpx.URL(AUTHORIZE_URL, params=params))


async def exchange_code(code: str, redirect_uri: str) -> Optional[GoogleProfile]:
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None
    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
        try:
            token_resp = await client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        except httpx.HTTPError:
            return None
        if token_resp.status_code != 200:
            return None
        access_token = token_resp.json().get("access_token")
        if not access_token:
            return None

        try:
            userinfo_resp = await client.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
        except httpx.HTTPError:
            return None
        if userinfo_resp.status_code != 200:
            return None
        data = userinfo_resp.json()
        sub, email = data.get("sub"), data.get("email")
        if not sub or not email:
            return None
        return {"sub": sub, "email": email}
