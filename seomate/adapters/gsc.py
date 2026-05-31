"""Google Search Console adapter (owner-data, OAuth).

Pulls the data behind the GSC-gated variables:
- searchAnalytics (queries/pages/clicks/impressions/CTR/position) -> feeds
  the keyword-to-page mapping (P0-13) with *actual* rankings + query perf.
- sitemaps list + submission status -> P2-03 sitemap submission.

Auth via GoogleOAuthManager (shared with GBP). When OAuth is not
configured the orchestrator skips this and marks the dependent variables
``unmeasurable`` with the standard reason. Follows the BaseAdapter
contract exactly: ``name`` class attr, async-context-manager ``self.client``,
and the ``@tracked`` decorator for per-call telemetry.
"""
from __future__ import annotations

from typing import Any, ClassVar
from urllib.parse import quote

from seomate.adapters._base import AdapterContext, BaseAdapter, tracked
from seomate.adapters.google_oauth import GoogleOAuthManager, GoogleOAuthSettings

SEARCH_CONSOLE_BASE = "https://searchconsole.googleapis.com/webmasters/v3"


class GSCAdapter(BaseAdapter):
    """Search Console API client using an OAuth bearer token."""

    name: ClassVar[str] = "gsc"
    default_rps: ClassVar[float] = 5.0

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        rps: float | None = None,
        timeout_seconds: float = 30.0,
        oauth: GoogleOAuthManager | None = None,
        oauth_settings: GoogleOAuthSettings | None = None,
    ) -> None:
        super().__init__(ctx, rps=rps, timeout_seconds=timeout_seconds)
        self.oauth = oauth or GoogleOAuthManager(oauth_settings)

    def is_configured(self) -> bool:
        return self.oauth.is_configured()

    async def _auth_headers(self) -> dict[str, str]:
        token = await self.oauth.access_token(self.client)
        return {"Authorization": f"Bearer {token}"}

    @tracked("searchconsole.searchAnalytics.query")
    async def search_analytics(
        self,
        site_url: str,
        *,
        start_date: str,
        end_date: str,
        dimensions: list[str] | None = None,
        row_limit: int = 1000,
    ) -> dict[str, Any]:
        """POST searchAnalytics/query for a property.

        ``site_url`` is the GSC property string, e.g.
        ``sc-domain:pixelettetech.com`` or ``https://pixelettetech.com/``.
        """
        headers = await self._auth_headers()
        url = f"{SEARCH_CONSOLE_BASE}/sites/{quote(site_url, safe='')}/searchAnalytics/query"
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": dimensions or ["query", "page"],
            "rowLimit": row_limit,
        }
        resp = await self.client.post(url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    @tracked("searchconsole.sitemaps.list")
    async def list_sitemaps(self, site_url: str) -> dict[str, Any]:
        """GET submitted sitemaps + their last-download / error status."""
        headers = await self._auth_headers()
        url = f"{SEARCH_CONSOLE_BASE}/sites/{quote(site_url, safe='')}/sitemaps"
        resp = await self.client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()
