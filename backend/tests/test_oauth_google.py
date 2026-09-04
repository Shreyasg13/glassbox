"""Google OAuth provider correctness: authorize-URL construction, the
code-exchange -> userinfo round trip, and every "provider said no"
failure path returning None cleanly (never raising) so routers/oauth.py
can turn each into the same clean failure redirect rather than a 500.
"""
from __future__ import annotations

import httpx
import respx

from app import oauth_google


def test_is_configured_false_when_unset(monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    assert oauth_google.is_configured() is False


def test_is_configured_true_when_both_set(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    assert oauth_google.is_configured() is True


def test_build_authorize_url_includes_required_params(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    url = oauth_google.build_authorize_url("https://example.com/auth/oauth/google/callback", "state-abc")
    assert url.startswith(oauth_google.AUTHORIZE_URL)
    parsed = httpx.URL(url)
    assert parsed.params["client_id"] == "fake-id"
    assert parsed.params["redirect_uri"] == "https://example.com/auth/oauth/google/callback"
    assert parsed.params["response_type"] == "code"
    assert parsed.params["scope"] == "openid email profile"
    assert parsed.params["state"] == "state-abc"


@respx.mock
async def test_exchange_code_success_returns_sub_and_email(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    respx.post(oauth_google.TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "fake-access-token"}))
    respx.get(oauth_google.USERINFO_URL).mock(
        return_value=httpx.Response(200, json={"sub": "google-sub-123", "email": "shreyash@example.com"})
    )
    profile = await oauth_google.exchange_code("fake-code", "https://example.com/auth/oauth/google/callback")
    assert profile == {"sub": "google-sub-123", "email": "shreyash@example.com"}


@respx.mock
async def test_exchange_code_sends_client_secret_server_side_only(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    token_route = respx.post(oauth_google.TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "fake-access-token"})
    )
    respx.get(oauth_google.USERINFO_URL).mock(
        return_value=httpx.Response(200, json={"sub": "google-sub-123", "email": "shreyash@example.com"})
    )
    await oauth_google.exchange_code("fake-code", "https://example.com/auth/oauth/google/callback")
    sent = httpx.QueryParams(token_route.calls[0].request.content.decode())
    assert sent["client_secret"] == "fake-secret"
    assert sent["code"] == "fake-code"
    assert sent["grant_type"] == "authorization_code"


async def test_exchange_code_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT_SECRET", raising=False)
    assert await oauth_google.exchange_code("fake-code", "https://example.com/cb") is None


@respx.mock
async def test_exchange_code_returns_none_when_token_exchange_fails(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    respx.post(oauth_google.TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
    assert await oauth_google.exchange_code("bad-code", "https://example.com/cb") is None


@respx.mock
async def test_exchange_code_returns_none_when_userinfo_fails(monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    respx.post(oauth_google.TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "fake-access-token"}))
    respx.get(oauth_google.USERINFO_URL).mock(return_value=httpx.Response(401))
    assert await oauth_google.exchange_code("fake-code", "https://example.com/cb") is None


@respx.mock
async def test_exchange_code_returns_none_when_email_missing(monkeypatch):
    """Google can return a profile without email (e.g. scope not
    actually granted) -- must not hand back a profile with no usable
    identity for oauth_login's username selection."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    respx.post(oauth_google.TOKEN_URL).mock(return_value=httpx.Response(200, json={"access_token": "fake-access-token"}))
    respx.get(oauth_google.USERINFO_URL).mock(return_value=httpx.Response(200, json={"sub": "google-sub-123"}))
    assert await oauth_google.exchange_code("fake-code", "https://example.com/cb") is None
