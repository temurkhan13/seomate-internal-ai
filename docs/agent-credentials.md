# Credentials a Claude session needs to run an audit

Copy `.env.example` to `.env` and fill what you have. **None of these are
required to start** , `seomate gather` runs every source you have a key for and
honestly marks the rest unavailable (dependent variables become `unmeasurable`,
never guessed). The more you fill, the more variables get measured.

This is per-auditor setup; the keys are not in the repo. Pick them up from the
team's secret store (ask the project owner). Never commit `.env`.

## What each key unlocks, and how to get it

| Env var(s) | Cost | Unlocks | How to obtain |
|---|---|---|---|
| `DATABASE_URL` | , | **Required to write back** (`ingest`). Without it you can gather + evaluate but not land on the dashboard. | The shared Supabase Postgres URL (session pooler). From the project owner. |
| (none) | free | crawl + link graph, robots/llms.txt, Wayback | nothing , always runs |
| `GOOGLE_PSI_API_KEY` | free | PageSpeed (lab CWV) **and CrUX** (field CWV/INP) | Google Cloud console → enable **PageSpeed Insights API** + **Chrome UX Report API** → create an API key. Same key serves both. |
| `GOOGLE_KG_API_KEY` | free | Knowledge Graph entity presence | Same GCP project → enable **Knowledge Graph Search API** → API key (can reuse the PSI key if scoped). |
| `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` | PAYG (~£0.05–0.75/audit) | SERP, Labs (rankings/volume/difficulty), Business Data (GBP + reviews), **AI Optimization** (LLM citations), and Backlinks **if** subscribed | app.dataforseo.com account. Top up PAYG balance. The login is your account email, the "password" is the API password (not your login password) , under API Access in the dashboard. |
| `GOOGLE_OAUTH_CLIENT_ID` / `_SECRET` / `_REFRESH_TOKEN` | free | Google Search Console (cannibalization, CTR, sitemap, query/page performance) | Two steps: (a) create a **Desktop OAuth client** in GCP (`docs/google-oauth-setup.md`) → gives client_id+secret; (b) run the loopback consent flow once to get the refresh token. **Then the site owner must add the consenting Google account as a user on the target property in Search Console** , otherwise GSC returns zero sites. |

## Optional / not yet wired into `gather`
These appear in `.env.example` for future use; current `gather` does not call them:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (session is the LLM, so not needed for
judgment), `PERPLEXITY_API_KEY` (LLM citations go through DataForSEO AI
Optimization instead), `NEWSAPI_KEY`, `REDDIT_*`, `YOUTUBE_API_KEY`,
`LISTEN_NOTES_API_KEY`. Social/forum presence is currently a SERP `site:` proxy.

## The honest-degradation contract (why missing keys are safe)
Every source `gather` runs reports `available: true/false` + a `reason` in
`manifest.json`. If you have no DataForSEO account, the ~60 SERP/Labs/Business/
LLM/backlinks variables are marked `unmeasurable` with that reason , the audit
still completes and lands on the dashboard, it just measures fewer variables. A
fuller `.env` = higher coverage, not a precondition.

## Minimum viable vs full
- **Minimum** (free only): `DATABASE_URL` + `GOOGLE_PSI_API_KEY` → crawl, robots,
  PSI, CrUX, Wayback, KG. Gets you the on-page/technical/CWV core.
- **Full**: add DataForSEO + GSC OAuth → SERP, rankings, GBP/reviews, LLM
  citations, Search Console. This is what the 186/233 pixelettetech.com run used.
