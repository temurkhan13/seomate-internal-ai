"""Tests for the Google OAuth manager + GSC/GBP adapter wiring.

No network, no real credentials: cover the credential-boundary behaviour
(unconfigured -> is_configured False + OAuthNotConfigured) and the token
refresh+cache path against a stubbed token endpoint.
"""
from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from seomate.adapters._base import AdapterContext
from seomate.adapters.gbp import GBPAdapter
from seomate.adapters.google_oauth import (
    GoogleOAuthManager,
    GoogleOAuthSettings,
    OAuthNotConfigured,
)
from seomate.adapters.gsc import GSCAdapter
from seomate.utils.cost_tracker import CostTracker


def _unconfigured() -> GoogleOAuthSettings:
    return GoogleOAuthSettings(
        GOOGLE_OAUTH_CLIENT_ID=None,
        GOOGLE_OAUTH_CLIENT_SECRET=None,
        GOOGLE_OAUTH_REFRESH_TOKEN=None,
    )


def _configured() -> GoogleOAuthSettings:
    return GoogleOAuthSettings(
        GOOGLE_OAUTH_CLIENT_ID="cid",
        GOOGLE_OAUTH_CLIENT_SECRET="secret",
        GOOGLE_OAUTH_REFRESH_TOKEN="refresh",
    )


def _ctx() -> AdapterContext:
    return AdapterContext(audit_id=uuid4(), cost_tracker=CostTracker(cap_gbp=1.0))


def test_unconfigured_is_false() -> None:
    assert GoogleOAuthManager(_unconfigured()).is_configured() is False


def test_configured_is_true() -> None:
    assert GoogleOAuthManager(_configured()).is_configured() is True


@pytest.mark.asyncio
async def test_access_token_raises_when_unconfigured() -> None:
    m = GoogleOAuthManager(_unconfigured())
    async with httpx.AsyncClient() as client:
        with pytest.raises(OAuthNotConfigured):
            await m.access_token(client)


@pytest.mark.asyncio
async def test_access_token_refreshes_and_caches() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"access_token": "tok123", "expires_in": 3600})

    transport = httpx.MockTransport(handler)
    m = GoogleOAuthManager(_configured())
    async with httpx.AsyncClient(transport=transport) as client:
        t1 = await m.access_token(client)
        t2 = await m.access_token(client)  # cached, no second network call
    assert t1 == "tok123" and t2 == "tok123"
    assert calls["n"] == 1


def test_adapters_report_unconfigured() -> None:
    ctx = _ctx()
    gsc = GSCAdapter(ctx, oauth_settings=_unconfigured())
    gbp = GBPAdapter(ctx, oauth_settings=_unconfigured())
    assert gsc.is_configured() is False
    assert gbp.is_configured() is False
    assert gsc.name == "gsc" and gbp.name == "gbp"


@pytest.mark.asyncio
async def test_access_token_retries_transient_disconnect() -> None:
    """A transient RemoteProtocolError on the token endpoint (the exact
    failure observed live) is retried, not surfaced to the caller."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.RemoteProtocolError(
                "Server disconnected without sending a response.", request=request
            )
        return httpx.Response(200, json={"access_token": "tok-after-retry", "expires_in": 3600})

    transport = httpx.MockTransport(handler)
    m = GoogleOAuthManager(_configured())
    async with httpx.AsyncClient(transport=transport) as client:
        tok = await m.access_token(client)
    assert tok == "tok-after-retry"
    assert calls["n"] == 2  # failed once (transient), retried, then succeeded


@pytest.mark.asyncio
async def test_access_token_does_not_retry_4xx() -> None:
    """A 400 (e.g. invalid_grant) is a caller error — raised immediately, never retried."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "invalid_grant"})

    transport = httpx.MockTransport(handler)
    m = GoogleOAuthManager(_configured())
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await m.access_token(client)
    assert calls["n"] == 1  # 4xx not retried
