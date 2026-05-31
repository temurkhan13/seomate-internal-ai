# Google Search Console + Business Profile OAuth setup

The GSC and GBP integrations read data private to the property/listing
owner, so they use OAuth 2.0 user credentials, not API keys. The code is
written and unit-tested; it activates when three env vars are present.
This doc is the one-time setup the property owner performs.

## What the code already does

- `seomate/adapters/google_oauth.py` , refresh-token -> access-token manager
  (in-memory cached, auto-refreshed, `is_configured()` gate).
- `seomate/adapters/gsc.py` , Search Console: `search_analytics()` (real
  rankings/clicks/impressions, feeds P0-13 keyword-to-page mapping + query
  performance), `list_sitemaps()` (P2-03 submission status).
- `seomate/adapters/gbp.py` , Business Profile: `list_accounts()`,
  `list_locations()` (P5 NAP / profile completeness; reviews + posts to follow).
- Until the env vars are set, `is_configured()` is False and the dependent
  variables stay `unmeasurable` with reason "Google OAuth not configured" ,
  no guessing, no fabrication.

Verified: `pytest tests/test_google_oauth.py` -> 5 passed (gate, error path,
token refresh+cache via mock transport, adapter status).

## One-time setup (property owner)

1. **GCP project + APIs.** In console.cloud.google.com, enable:
   - Search Console API
   - My Business Account Management API + My Business Business Information API (GBP)
2. **OAuth consent screen.** Configure it. Add scopes:
   - `https://www.googleapis.com/auth/webmasters.readonly` (GSC)
   - `https://www.googleapis.com/auth/business.manage` (GBP)
   GBP scopes require **Google app verification**; submit for review.
   GSC-only can proceed immediately (add yourself as a test user if unverified).
3. **OAuth client.** Create an OAuth client ID (Desktop app is simplest for a
   one-time refresh-token grab). Note **client_id** + **client_secret**.
4. **Get a refresh token.** Complete consent once, signed in as the account
   that owns the GSC property / GBP listing, requesting offline access (the
   OAuth Playground or a short helper script both work).
5. **Drop the credentials in** (env / .env, never committed):
   ```
   GOOGLE_OAUTH_CLIENT_ID=...
   GOOGLE_OAUTH_CLIENT_SECRET=...
   GOOGLE_OAUTH_REFRESH_TOKEN=...
   ```

That is the whole credential boundary. Once present, the next audit pulls
real GSC + GBP data and the P5 / GSC-gated variables move from
`unmeasurable` to measured. No code change required.

## GSC property string

GSC identifies a property as a domain property
(`sc-domain:pixelettetech.com`) or a URL-prefix property
(`https://pixelettetech.com/`). Use whichever the owning account verified.

## Multi-property (future)

The single refresh-token env var fits the single-pilot case. For many client
sites, persist a refresh token per property in a DB table and look it up by
site; `GoogleOAuthManager` already isolates the token source, so this is an
additive change, not a rewrite.
