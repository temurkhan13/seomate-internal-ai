"""Google Business Profile adapter (owner-data, OAuth).

Pulls the data behind the GBP-gated P5 (local) variables:
- business location(s) + profile completeness -> P5 NAP / completeness.
- (reviews summary + posts/performance to follow.)

GBP uses several versioned host bases. Auth shares GoogleOAuthManager with
GSC. GBP scopes require Google app verification before consent will grant
them; until then this adapter stays dormant and the P5 variables remain
``unmeasurable`` with the standard reason. Follows the BaseAdapter
contract: ``name`` class attr, ``self.client``, ``@tracked`` decorator.
"""
from __future__ import annotations

from typing import Any, ClassVar

from seomate.adapters._base import AdapterContext, BaseAdapter, tracked
from seomate.adapters.google_oauth import GoogleOAuthManager, GoogleOAuthSettings

ACCOUNT_MGMT_BASE = "https://mybusinessaccountmanagement.googleapis.com/v1"
BUSINESS_INFO_BASE = "https://mybusinessbusinessinformation.googleapis.com/v1"


class GBPAdapter(BaseAdapter):
    """Business Profile API client using an OAuth bearer token."""

    name: ClassVar[str] = "gbp"
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

    @tracked("gbp.accounts.list")
    async def list_accounts(self) -> dict[str, Any]:
        """List the GBP accounts the authorised user can access."""
        headers = await self._auth_headers()
        resp = await self.client.get(f"{ACCOUNT_MGMT_BASE}/accounts", headers=headers)
        resp.raise_for_status()
        return resp.json()

    @tracked("gbp.locations.list")
    async def list_locations(self, account: str, *, read_mask: str | None = None) -> dict[str, Any]:
        """List locations for an account (``accounts/{id}``).

        ``read_mask`` selects fields, e.g.
        ``name,title,storefrontAddress,phoneNumbers,websiteUri,regularHours``.
        """
        headers = await self._auth_headers()
        params = {"readMask": read_mask or "name,title,storefrontAddress,phoneNumbers,websiteUri"}
        url = f"{BUSINESS_INFO_BASE}/{account}/locations"
        resp = await self.client.get(url, headers=headers, params=params)
        resp.raise_for_status()
        return resp.json()
