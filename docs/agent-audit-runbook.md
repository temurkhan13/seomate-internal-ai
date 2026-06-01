# Agent audit runbook: how a Claude session audits any domain with SEOMATE

This is the **Phase 1 diagnostic loop**. A Claude session is the auditor;
SEOMATE supplies the taxonomy (the understanding), the data plumbing
(`seomate gather`), the storage, and the dashboard. To audit a new site you do
**not** hand-roll fetch logic, and you do **not** need to rediscover which
sources are reachable, that is what `gather` is for.

```
seomate export-brief ─► brief.json ─┐
                                     ├─► [ session: read manifest + brief, judge each variable ] ─► audit.json ─► seomate ingest ─► dashboard
seomate gather --domain X ─► cache/ ─┘        (semantic judgment only)                                (233 captures)    (write-back)
```

Three commands are code in this repo (`export-brief`, `gather`, `ingest`). The
middle, applying judgment per variable, is the session's job and the only part
that needs a brain.

## TL;DR for a fresh session ("audit abcd.com")

```bash
# 0. one-time: copy .env.example -> .env, fill the keys you have (see table below)
seomate export-brief --out brief.json                 # the 232-variable instruction set
seomate gather --domain abcd.com --out audit-cache    # collect every reachable source
#    -> reads audit-cache/manifest.json to see what's available vs unavailable
# ... session evaluates each variable from the cache (see "Evaluate" below) ...
seomate ingest --file audit.json --dry-run            # validate
seomate ingest --file audit.json                      # write -> dashboard
seomate inspect <printed-audit-id>                    # confirm
```

A bare `--domain` works: `gather` auto-derives keyword seeds (from the site's
own pages) and the market/location (from the TLD; override with
`--location-code`). For a non-UK/US site, pass the right DataForSEO location
code.

## Step 1 — Gather (`seomate gather`)

`seomate gather --domain abcd.com --out audit-cache` writes one JSON file per
source plus `manifest.json`. **Always read `manifest.json` first** , it lists,
per source, `available: true/false` and a `reason` when false. The contract:

> For any source marked **unavailable**, mark the variables that depend on it
> `unmeasurable` with that reason. **Never guess a pass/fail.**

### Source → capability matrix (what each unlocks, and how to enable it)

| Source (cache file) | Auth needed | Unlocks (pillars) |
|---|---|---|
| **crawl** (`crawl.json`) | none (HTTP) | On-page P1 (titles, meta, headings, canonical, schema, og/twitter, alt, URL), most of P2 technical, P6 structure, the **internal link graph** (orphans, inbound counts, depth), body text for P4/P6 content judgment |
| **robots** (`robots.json`) | none | P2 robots/sitemap, P6-17 LLM-bot access, P6-18 llms.txt |
| **psi** (`psi.json`) | `GOOGLE_PSI_API_KEY` | P2 Core Web Vitals lab (LCP/FCP/TBT/CLS), mobile usability |
| **crux** (`crux.json`) | `GOOGLE_PSI_API_KEY` (shared) | P2-09 INP + field-data CWV (real users). NB: the **Chrome UX Report API must be enabled** on the GCP project, else 403 |
| **wayback** (`wayback.json`) | none | P4-01 publishing cadence, P4-02 freshness, P1-44 content-update magnitude (diff snapshots), P2-40 host age |
| **knowledge_graph** (`entity.json`) | `GOOGLE_KG_API_KEY` | P6-29 KG entity completeness, brand-entity presence |
| **dataforseo.serp** (`dataforseo.json`) | `DATAFORSEO_LOGIN`/`PASSWORD` | P0-05 SERP features, P6-25 AI Overview, P0-18 big-brand preference, competitor set, P5-28 location demotion (multi-geo) |
| **dataforseo.labs** | DataForSEO | P0-02/03/04/06 keyword volume/difficulty/CPC/intent, P0-15 brand volume, rankings |
| **dataforseo.business** | DataForSEO | P5 GBP profile (category/completeness/rating) **and reviews** (velocity/recency/response/sentiment) , **no GBP owner access needed** |
| **dataforseo.backlinks** | DataForSEO + **Backlinks subscription** (~$100/mo) | All 39 P3 off-page. Tag deferred if the subscription is off |
| **dataforseo (AI Optimization)** | DataForSEO | P6-26/27/28/31 real LLM-citation/sentiment/hallucination across ChatGPT/Claude/Gemini/Perplexity (not yet in `gather`; call directly per the [[Jun-01]] pattern) |
| **gsc** (`gsc.json`) | `GOOGLE_OAUTH_*` triple | P0-13 cannibalization, P0-18 CTR, P2-02/03 sitemap, query/page performance. The consenting account must be a **user on the property** (owner adds the auditing email) |

### What still needs access a session may not have
- **GSC**: the OAuth account must be added to the target property in Search
  Console by its owner (one-time). Token setup: `docs/google-oauth-setup.md`.
- **GBP owner-only** (posts, Q&A, engagement, photo count): need the Business
  Profile **owner** API. Reviews + profile come through DataForSEO without it.
- **Local citations** (P5-06/07/08): SERP `site:` against directories
  (clutch/crunchbase/trustpilot/...) is a decent proxy; a dedicated citations
  tool gives the full count.
- **GSC Crawl Stats** (P2-05): UI-only, no API. Genuinely unmeasurable.

## Step 2 — Evaluate each variable

For each variable in `brief.json`:
1. Read its `description` + `raw_markdown` to understand what it measures.
2. **Confirm the variable_id matches the evidence** , a recurring bug is filing
   real data under the wrong id. The brief carries the canonical `name`; sanity-
   check your capture's intent against it before writing.
3. Apply its `step_1_5_rules` against the gathered cache. Each rule → `passed:
   true/false` + structured `evidence` (counts, failing URLs, expected vs actual).
4. Set `status`: `passed` / `failed` / `partial` / `not_applicable` /
   `unmeasurable` (source unavailable) / `error`.
5. Carry `evidence_weight` through; record `data_sources_used`.

**Discipline (non-negotiable, this is why the output is trusted):**
- Judge semantically against the rule text; never reduce a rule to a keyword match.
- Evidence must be real and in the cache. **Never invent a value, count, or a
  passing result you did not observe.** Unobserved = `unmeasurable`/`error`,
  never a fabricated pass/fail.
- After ingesting, **verify against the live dashboard / DB**, not just the CLI
  return. (Premature "it's done" claims, before the write was confirmed, have
  been a real failure mode.)

## Step 3 — Emit + write back

One JSON document per `docs/ingest-contract.md`: top-level `site_domain` +
`taxonomy_version` (from the brief) + `captures[]`. Then:

```bash
seomate ingest --file audit.json --dry-run   # reports all problems, writes nothing
seomate ingest --file audit.json             # writes audit + captures
seomate inspect <printed-audit-id>            # confirm on the dashboard
```

The audit then appears on the dashboard exactly like a natively-run one.

## Deferred vs unmeasurable

If a source is off by **business choice** (e.g. the Backlinks subscription),
mark those captures `unmeasurable` and set `value.deferred = true` +
`value.deferral_reason`, so the dashboard can separate "deferred by choice" from
"genuinely cannot measure." Do not silently fold them into plain unmeasurable.

## Scope

Phase 1 (diagnostic) only. Phase 2 (executing the fixes the diagnostic found,
the systematized version of the manual P1-20 canonical fix) is separate.

## Reference: a worked run

The 2026-06-01 pixelettetech.com audit drove coverage to 186/233 measured using
exactly this loop across every source above. Full method + the source-by-source
findings are in the vault (`agent-driven-audit`, the audit-findings analysis).
The taxonomy parses to **232** active variables (233 capture rows).
