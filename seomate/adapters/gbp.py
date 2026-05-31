"""Google Business Profile adapter (owner-data, OAuth).

Pulls the data behind the GBP-gated P5 (local) variables:
- business location(s) + profile completeness -> P5 NAP / completeness.
- (reviews summary + posts/performance to follow.)

GBP uses several versioned host bases. Auth shares GoogleOAuthManager with
GSC. GBP scopes require Google app verification before consent will grant
them; until then this adapter stays dormant and the P5 variables remain
``unmeasurable`` with the standard reason.
"""
from __future__ import annotations

from typing import Any

from seomate.adapters._base import AdapterContext, BaseAdapter
from seomate.adapters.google_oauth import GoogleOAuthManager, GoogleOAuthSettings

ACCOUNT_MGMT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
BUSINESS_INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"


class GBPAdapter(BaseAdapter):
    """Business Profile API client using an OAuth bearer token."""

    adapter_name = "gbp"

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

    async def list_accounts(self) -> dict[str, Any]:
        """List the GBP accounts the authorised user can access."""
        headers = await self._auth_headers()
        resp = await self.tracked_get(
            "accounts.list", f"{ACCOUNT_MGMT_BASE}/accounts", headers=headers
        )
        resp.raise_for_status()
        return resp.json()

    async def list_locations(self, account: str, *, read_mask: str | None = None) -> dict[str, Any]:
        """List locations for an account (``accounts/{id}``).

        ``read_mask`` selects fields, e.g.
        ``name,title,storefrontAddress,phoneNumbers,websiteUri,regularHours``.
        """
        headers = await self._auth_headers()
        params = {"readMask": read_mask or "name,title,storefrontAddress,phoneNumbers,websiteUri"}
        url = f"{BUSINESS_INFO_BASE}/{account}/locations"
        resp = await self.tracked_get("locations.list", url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
