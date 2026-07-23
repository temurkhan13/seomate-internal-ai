"""Google Analytics 4 (GA4) adapter — owner-data, OAuth.

Pulls GA4 engagement/acquisition data via the Analytics Data API
(``analyticsdata.googleapis.com`` v1beta ``runReport``). This feeds the
Phase-2 Strategist / project workspace (engagement + search footprint over
time); it is **not** a constitutional auditor dependency — the Phase-1
auditor never requires client analytics (GA4/GTM/Pixel), see
``docs/site-auditor-architecture.md`` §3.1. When OAuth or the GA4 property
id is absent, ``is_configured()`` is False and callers mark the dependent
data ``unmeasurable`` with the standard reason — no guessing, no fabrication.

Auth shares :class:`GoogleOAuthManager` with GSC/GBP; the required scope
``analytics.readonly`` is granted alongside ``webmasters.readonly`` in a
single consent (the refresh token is scope-bound — see
``docs/google-oauth-setup.md``). Follows the BaseAdapter contract exactly:
``name`` class attr, async-context-manager ``self.client``, and ``@tracked``
telemetry. The Analytics Data API is free, so calls record £0.
"""
from __future__ import annotations

from typing import Any, ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict

from seomate.adapters._base import AdapterContext, BaseAdapter, tracked
from seomate.adapters.google_oauth import GoogleOAuthManager, GoogleOAuthSettings

ANALYTICS_DATA_BASE = "https://analyticsdata.googleapis.com/v1beta"

# Standard GA4 metrics/dimension chosen to always resolve (no deprecated
# names like the old ``conversions``). Callers may override per report.
DEFAULT_METRICS = [
    "sessions",
    "engagedSessions",
    "engagementRate",
    "screenPageViews",
    "totalUsers",
    "averageSessionDuration",
]
DEFAULT_DIMENSIONS = ["sessionDefaultChannelGroup"]


class GA4Settings(BaseSettings):
    """GA4 property id, read from env / .env.

    Format is the numeric Data-API property, e.g. ``properties/434308648``
    (GA4 Admin → Property Settings). Bare digits are accepted and
    normalised to the ``properties/<id>`` form.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    GA4_PROPERTY_ID: str | None = None

    @property
    def property_path(self) -> str | None:
        pid = (self.GA4_PROPERTY_ID or "").strip()
        if not pid:
            return None
        return pid if pid.startswith("properties/") else f"properties/{pid}"


class GA4Adapter(BaseAdapter):
    """Analytics Data API client using an OAuth bearer token."""

    name: ClassVar[str] = "ga4"
    default_rps: ClassVar[float] = 5.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        rps: float | None = None,
        timeout_seconds: float = 60.0,
        oauth: GoogleOAuthManager | None = None,
        oauth_settings: GoogleOAuthSettings | None = None,
        settings: GA4Settings | None = None,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self.oauth = oauth or GoogleOAuthManager(oauth_settings)
        self.settings = settings or GA4Settings()

    def is_configured(self) -> bool:
        """True only when OAuth creds *and* a GA4 property id are present."""
        return self.oauth.is_configured() and self.settings.property_path is not None

    @property
    def property_path(self) -> str | None:
        return self.settings.property_path

    async def _auth_headers(self) -> dict[str, str]:
        token = await self.oauth.access_token(self.client)
        return {"Authorization": f"Bearer {token}"}

    @staticmethod
    def _property(property_id: str) -> str:
        pid = (property_id or "").strip()
        return pid if pid.startswith("properties/") else f"properties/{pid}"

    @tracked("analyticsdata.runReport")
    async def run_report(
        self,
        property_id: str,
        *,
        start_date: str,
        end_date: str,
        metrics: list[str] | None = None,
        dimensions: list[str] | None = None,
        row_limit: int = 10000,
    ) -> dict[str, Any]:
        """POST ``properties/<id>:runReport`` for a GA4 property.

        ``property_id`` is the numeric Data-API property, e.g.
        ``properties/434308648`` (bare digits also accepted). ``start_date``
        / ``end_date`` are ISO ``YYYY-MM-DD`` or GA4 relative forms
        (``NdaysAgo``, ``yesterday``, ``today``).
        """
        prop = self._property(property_id)
        headers = await self._auth_headers()
        url = f"{ANALYTICS_DATA_BASE}/{prop}:runReport"
        body: dict[str, Any] = {
            "dateRanges": [{"startDate": start_date, "endDate": end_date}],
            "metrics": [{"name": m} for m in (metrics or DEFAULT_METRICS)],
            "dimensions": [{"name": d} for d in (dimensions or DEFAULT_DIMENSIONS)],
            "limit": row_limit,
        }
        resp = await self.client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    @tracked("analyticsdata.getMetadata")
    async def get_metadata(self, property_id: str) -> dict[str, Any]:
        """GET ``properties/<id>/metadata`` — dimensions/metrics available.

        Doubles as a cheap connectivity + permission probe for a property.
        """
        prop = self._property(property_id)
        headers = await self._auth_headers()
        url = f"{ANALYTICS_DATA_BASE}/{prop}/metadata"
        resp = await self.client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
