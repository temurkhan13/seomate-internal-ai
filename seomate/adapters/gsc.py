"""Google Search Console adapter (owner-data, OAuth).

Pulls the data behind the GSC-gated variables:
- searchAnalytics (queries/pages/clicks/impressions/CTR/position) -> feeds
  the keyword-to-page mapping (P0-13) with *actual* rankings + query perf.
- sitemaps list + submission status -> P2-03 sitemap submission.

Auth via GoogleOAuthManager (shared with GBP). When OAuth is not
configured the orchestrator skips this and marks the dependent variables
``unmeasurable`` with the standard reason.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from seomate.adapters._base import AdapterContext, BaseAdapter
from seomate.adapters.google_oauth import GoogleOAuthManager, GoogleOAuthSettings

SEARCH_CONSOLE_BASE = "https://searchconsole.googleapis.com/webmasters/v3"


class GSCAdapter(BaseAdapter):
    """Search Console API client using an OAuth bearer token."""

    adapter_name = "gsc"

    def __init__(
        self,
        ctx: AdapterContext,
        *,
        oauth: GoogleOAuthManager | None = None,
        settings: GoogleOAuthSettings | None = None,
    ) -> None:
        super().__init__(ctx, settings=settings)
        self.oauth = oauth or GoogleOAuthManager(settings)

    def is_configured(self) -> bool:
        return self.oauth.is_configured()

    async def _auth_headers(self) -> dict[str, str]:
        assert self._client is not None
        token = await self.oauth.access_token(self._client)
        return {"Authorization": f"Bearer {token}"}

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
        resp = await self._tracked("POST", "searchAnalytics.query", url, json=body, headers=headers)
        resp.raise_for_status()
        return resp.json()

    async def list_sitemaps(self, site_url: str) -> dict[str, Any]:
        """GET submitted sitemaps + their last-download / error status."""
        headers = await self._auth_headers()
        url = f"{SEARCH_CONSOLE_BASE}/sites/{quote(site_url, safe='')}/sitemaps"
        resp = await self.tracked_get("sitemaps.list", url, headers=headers)
        resp.raise_for_status()
        return resp.json()
