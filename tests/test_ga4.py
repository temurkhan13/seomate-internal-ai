"""Tests for the GA4 adapter (Analytics Data API). No network, no real creds.

Covers the credential/property gate (unconfigured -> is_configured False),
property-id normalisation, and the runReport request shape against a
stubbed transport (URL, bearer header, and JSON body).
"""
from __future__ import annotations

import json as _json
from uuid import uuid4

import httpx
import pytest

from seomate.adapters._base import AdapterContext
from seomate.adapters.ga4 import GA4Adapter, GA4Settings
from seomate.adapters.google_oauth import GoogleOAuthSettings
from seomate.utils.cost_tracker import CostTracker


def _oauth(configured: bool) -> GoogleOAuthSettings:
    if configured:
        return GoogleOAuthSettings(
            GOOGLE_OAUTH_CLIENT_ID="cid",
            GOOGLE_OAUTH_CLIENT_SECRET="secret",
            GOOGLE_OAUTH_REFRESH_TOKEN="refresh",
        )
    return GoogleOAuthSettings(
        GOOGLE_OAUTH_CLIENT_ID=None,
        GOOGLE_OAUTH_CLIENT_SECRET=None,
        GOOGLE_OAUTH_REFRESH_TOKEN=None,
    )


def _ga4(pid: str | None) -> GA4Settings:
    return GA4Settings(GA4_PROPERTY_ID=pid)


def _ctx() -> AdapterContext:
    return AdapterContext(audit_id=uuid4(), cost_tracker=CostTracker(cap_gbp=1.0))


def test_property_path_normalises() -> None:
    assert _ga4("434308648").property_path == "properties/434308648"
    assert _ga4("properties/434308648").property_path == "properties/434308648"
    assert _ga4(None).property_path is None
    assert _ga4("   ").property_path is None


def test_unconfigured_without_oauth() -> None:
    a = GA4Adapter(_ctx(), oauth_settings=_oauth(False), settings=_ga4("434308648"))
    assert a.is_configured() is False
    assert a.name == "ga4"


def test_unconfigured_without_property() -> None:
    a = GA4Adapter(_ctx(), oauth_settings=_oauth(True), settings=_ga4(None))
    assert a.is_configured() is False


def test_configured_true() -> None:
    a = GA4Adapter(_ctx(), oauth_settings=_oauth(True), settings=_ga4("434308648"))
    assert a.is_configured() is True
    assert a.property_path == "properties/434308648"


@pytest.mark.asyncio
async def test_run_report_builds_request() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if "oauth2.googleapis.com/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = _json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "rows": [
                    {
                        "dimensionValues": [{"value": "Organic Search"}],
                        "metricValues": [{"value": "123"}],
                    }
                ]
            },
        )

    a = GA4Adapter(_ctx(), oauth_settings=_oauth(True), settings=_ga4("434308648"))
    a._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        out = await a.run_report(
            "434308648",
            start_date="90daysAgo",
            end_date="today",
            metrics=["sessions"],
            dimensions=["sessionDefaultChannelGroup"],
        )
    finally:
        await a._client.aclose()

    assert out["rows"]
    assert seen["url"] == "https://analyticsdata.googleapis.com/v1beta/properties/434308648:runReport"
    assert seen["auth"] == "Bearer tok"
    assert seen["body"]["metrics"] == [{"name": "sessions"}]
    assert seen["body"]["dimensions"] == [{"name": "sessionDefaultChannelGroup"}]
    assert seen["body"]["dateRanges"] == [{"startDate": "90daysAgo", "endDate": "today"}]
