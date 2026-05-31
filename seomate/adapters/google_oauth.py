"""Google OAuth token manager for the GSC + GBP adapters.

Shared auth layer for the two owner-data integrations (Search Console and
Business Profile). Both require an OAuth 2.0 *user* credential (not an API
key) because they expose data private to the property/listing owner.

Credential boundary (only the property owner can provide)
---------------------------------------------------------
1. A GCP OAuth client (client_id + client_secret) with the Search Console
   + Business Profile APIs enabled and the relevant scopes on the consent
   screen. GBP scopes also require Google app verification.
2. A refresh token from completing consent once as the account that owns
   the GSC property / GBP listing.

Provide via env (see docs/google-oauth-setup.md):
    GOOGLE_OAUTH_CLIENT_ID
    GOOGLE_OAUTH_CLIENT_SECRET
    GOOGLE_OAUTH_REFRESH_TOKEN

When any are missing, is_configured() is False and the GSC/GBP extractors
emit ``unmeasurable`` ("OAuth not configured") instead of guessing, the
same honesty contract the rest of the auditor follows. The integration
activates the moment real credentials are present; no code change needed.
"""
from __future__ import annotations

import time

import httpx
from pydantic_settings import BaseSettings, SettingsConfigDict

TOKEN_URL = "https://oauth2.googleapis.com/token"
_REFRESH_MARGIN_S = 60  # refresh 60s before the ~3600s token expires


class GoogleOAuthSettings(BaseSettings):
    """OAuth client + refresh credentials, read from env / .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    GOOGLE_OAUTH_CLIENT_ID: str | None = None
    GOOGLE_OAUTH_CLIENT_SECRET: str | None = None
    GOOGLE_OAUTH_REFRESH_TOKEN: str | None = None

    @property
    def configured(self) -> bool:
        return bool(
            self.GOOGLE_OAUTH_CLIENT_ID
            and self.GOOGLE_OAUTH_CLIENT_SECRET
            and self.GOOGLE_OAUTH_REFRESH_TOKEN
        )


class OAuthNotConfigured(RuntimeError):
    """Raised when an access token is requested without full credentials."""


class GoogleOAuthManager:
    """Refresh-token -> access-token exchange with in-memory caching."""

    def __init__(self, settings: GoogleOAuthSettings | None = None) -> None:
        self.settings = settings or GoogleOAuthSettings()
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    def is_configured(self) -> bool:
        return self.settings.configured

    async def access_token(self, client: httpx.AsyncClient) -> str:
        """Return a valid access token, refreshing if needed.

        Raises OAuthNotConfigured if credentials are absent so callers can
        translate that into an ``unmeasurable`` capture.
        """
        if not self.settings.configured:
            raise OAuthNotConfigured(
                "Google OAuth not configured: set GOOGLE_OAUTH_CLIENT_ID, "
                "GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_REFRESH_TOKEN "
                "(see docs/google-oauth-setup.md)."
            )
        now = time.time()
        if self._access_token and now < self._expires_at - _REFRESH_MARGIN_S:
            return self._access_token

        resp = await client.post(
            TOKEN_URL,
            data={
                "client_id": self.settings.GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": self.settings.GOOGLE_OAUTH_CLIENT_SECRET,
                "refresh_token": self.settings.GOOGLE_OAUTH_REFRESH_TOKEN,
                "grant_type": "refresh_token",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        body = resp.json()
        self._access_token = body["access_token"]
        self._expires_at = now + float(body.get("expires_in", 3600))
        return self._access_token
