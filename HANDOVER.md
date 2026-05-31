# SEOMATE — Project Handover

**Author:** Humza Chishty (original owner & builder)
**Handover date:** 2026-05-15
**Last working state:** commit `7c1b052` (Inspector UI complete)
**Pilot site:** pixelettetech.com

---

## TL;DR — Read this first

SEOMATE is a closed-loop SEO + GEO audit platform built around a **constitutional taxonomy of 226 active variables** (`docs/o1-taxonomy.md`). Today, it runs as a Python CLI auditor + read-only FastAPI + Next.js inspection UI. It produces a structured per-variable audit of any web site against the taxonomy and has been validated against `pixelettetech.com` as the dogfood pilot.

**Where we are right now (15 May 2026):**

| Metric | Value |
|---|---|
| Active variables in taxonomy | 226 |
| Variables wired in auditor | 226 (100% of the operational ceiling) |
| Captures per full audit | 226 |
| Typical full-audit wall time | 5–9 minutes |
| Typical full-audit cost | ~£0.20 (DataForSEO) + ~£0.04 (LLM/embeddings) ≈ **£0.24** |
| Pillar coverage | P0 / P1 / P2 / P3 / P4 / P5 / P6 — all operational |
| Reliability rating (honest) | **~8/10** for the pilot site; not yet validated across multiple sites |
| LLM evaluators wired | 13 |
| External adapters wired | DataForSEO, Gemini embeddings, Anthropic LLM, Google PSI, Google KG, Wikipedia, Wikidata |

The system is **not yet customer-facing**. It works as a local-first tool that an SEO operator can run from the CLI and inspect via the web UI on `localhost`.

---

## Table of contents

1. [Vision — what SEOMATE is for](#1-vision)
2. [Architecture in one diagram](#2-architecture)
3. [Repository layout](#3-repository-layout)
4. [How to run it (cold start)](#4-how-to-run-it-cold-start)
5. [Credentials & external services](#5-credentials--external-services)
6. [The taxonomy — operating principles](#6-the-taxonomy)
7. [What's done, what's deferred, what's removed](#7-whats-done-whats-deferred-whats-removed)
8. [Reliability infrastructure (and why it exists)](#8-reliability-infrastructure)
9. [Open risks & things to watch](#9-open-risks)
10. [What's next — three honest options](#10-whats-next)
11. [Files & commits worth reading first](#11-files--commits-worth-reading-first)
12. [Glossary](#12-glossary)

---

## 1. Vision

SEO tools today (Ahrefs, Semrush, BrightLocal, etc.) are mostly *measurement* tools — they give you numbers. They don't tell you whether your site passes a defensible bar against a transparent, citable taxonomy of what actually matters.

SEOMATE is built around a **constitutional reference document** (`docs/o1-taxonomy.md`) that:

- Defines every SEO / GEO variable that materially affects ranking, organised into 7 pillars (P0 Strategic, P1 On-Page, P2 Technical, P3 Off-Page, P4 Content, P5 Local, P6 AI Search / GEO)
- Cites the source for every claim (Google Search Central docs, the 2024 Google content-warehouse leak, BrightLocal / Whitespark / industry research)
- Assigns an **evidence weight** to each variable: Consensus, Probable, Contested, or Speculative — so the audit doesn't pretend a speculative ranking factor is on the same footing as a Google-documented one
- Defines explicit **Step 1.5 evaluation rules** for each variable: a site doesn't just "have schema markup", it either passes or fails 7 specific named criteria

The auditor is a deterministic engine that converts a live site into a per-variable verdict against those rules, with the actual evidence attached. The output is reproducible, auditable, and survives expert scrutiny.

**The product hypothesis (still untested):** an SEO operator who runs SEOMATE on a client site gets a 200-row audit they can hand to a customer with the confidence that every finding is defensible against an industry expert's review. The audit becomes the *unit of work*, not just a stat dashboard.

**What SEOMATE is NOT (yet):**

- Not a customer-facing SaaS — no signups, no billing, no per-user audit history
- Not validated across multiple verticals — Pixelette is the only site it's been run against
- Not benchmarked against Ahrefs / Semrush — we have no ground-truth data for that comparison
- Not "automatic" — running an audit still requires a CLI command and a Python venv

---

## 2. Architecture

```
                      ┌──────────────────────────────────────┐
                      │  docs/o1-taxonomy.md                 │
                      │  226 active variables (Constitution) │
                      └────────────────┬─────────────────────┘
                                       │ loaded into
                                       ▼
┌─────────────┐         ┌──────────────────────────────────┐
│  configs/   │────────▶│  auditor/  (Python CLI)          │
│  pilot.yml  │         │                                  │
└─────────────┘         │  ┌──────────────────────────┐    │
                        │  │  orchestrator.py         │    │
   external adapters    │  │  - prefetch all data     │    │
   ─────────────────    │  │  - dispatch extractors   │    │
   DataForSEO API       │  │  - completeness gate     │    │
   Gemini Embeddings    │  │  - consistency rules     │    │
   Anthropic Haiku 4.5  │  │  - persist captures      │    │
   Google PSI           │  └──────────────────────────┘    │
   Google KG            │                                  │
   Wikipedia / Wikidata │  ┌──────────────────────────┐    │
                        │  │  pillars/*.py            │    │
                        │  │  226 extractor functions │    │
                        │  └──────────────────────────┘    │
                        └────────────────┬─────────────────┘
                                         │ writes to
                                         ▼
                        ┌──────────────────────────────────┐
                        │  Postgres + pgvector (Docker)    │
                        │  - audits                        │
                        │  - captures (the 226 rows/audit) │
                        │  - adapter_calls                 │
                        └────────────────┬─────────────────┘
                                         │ read by
                                         ▼
                        ┌──────────────────────────────────┐
                        │  api/  (FastAPI, READ-ONLY)      │
                        │  - /api/audits                   │
                        │  - /api/audits/{id}              │
                        │  - /api/audits/{id}/captures     │
                        │  - /api/taxonomy/variables/{id}  │
                        └────────────────┬─────────────────┘
                                         │ served to
                                         ▼
                        ┌──────────────────────────────────┐
                        │  web/  (Next.js 16 + React 19)   │
                        │  - /audits             (list)    │
                        │  - /audits/[auditId]   (detail)  │
                        │  - .../captures/[varId] (drill)  │
                        └──────────────────────────────────┘
```

**Key architectural commitments:**

- **Single writer:** the auditor is the *only* process that writes captures. The API is read-only. This keeps the audit a deterministic, idempotent unit.
- **Constitutional taxonomy:** every extractor declares which pillar it belongs to and which evidence weight applies. Variables removed from the taxonomy get a "redirect" stub left behind; nothing silently disappears.
- **Batching is mandatory for LLM calls:** any LLM evaluator batches N pages per call. Single-page LLM calls were ruled out from day one (lesson from 2Connect: monolithic LLM calls truncate / oversimplify / cost more).
- **Owner-data deferrals are explicit, not hidden:** variables that require GBP-owner or GSC-owner authentication are wired as UNMEASURABLE stubs with a clear remediation note pointing to the future OAuth integration.

---

## 3. Repository layout

```
seomate/
├── HANDOVER.md                      ← this file
├── README.md                        (out-of-date stub; see this doc instead)
├── docker-compose.yml               Postgres + pgvector for local dev
│
├── docs/
│   ├── o1-taxonomy.md               THE constitution (226 active vars, 9k lines)
│   ├── site-auditor-architecture.md Original architecture design doc
│   └── audit-validation-pixelettetech.docx  3-column doc for the SEO exec
│
├── auditor/                         Python CLI auditor
│   ├── seomate/
│   │   ├── orchestrator.py          Audit lifecycle; prefetch + dispatch + gate
│   │   ├── adapters/
│   │   │   ├── dataforseo.py        DataForSEO HTTP client
│   │   │   ├── llm.py               Anthropic Haiku 4.5 adapter
│   │   │   ├── embeddings.py        Gemini embedding-001
│   │   │   ├── wikipedia.py
│   │   │   ├── wikidata.py
│   │   │   ├── kg.py                Google Knowledge Graph
│   │   │   ├── psi.py               PageSpeed Insights
│   │   │   └── _base.py             rate_limited / retry_transient / tracked
│   │   ├── pillars/
│   │   │   ├── _base.py             SiteData (the shared audit state)
│   │   │   ├── p0_strategic.py
│   │   │   ├── p1_onpage.py
│   │   │   ├── p1_schema.py
│   │   │   ├── p2_psi.py
│   │   │   ├── p2_technical.py
│   │   │   ├── p3_backlinks.py      ★ heaviest single-pillar file, 36 vars
│   │   │   ├── p4_content.py
│   │   │   ├── p5_local.py          ★ includes review-level extractors
│   │   │   ├── p6_geo.py
│   │   │   ├── p6_serp.py
│   │   │   └── p_*.py               shared helpers (embeddings, keywords, freebatch)
│   │   ├── utils/
│   │   │   ├── llm_evaluation.py    The batched evaluator framework (13 evaluators)
│   │   │   ├── html_fetch.py
│   │   │   ├── text_extraction.py   trafilatura + bs4 fallback
│   │   │   └── link_graph.py
│   │   ├── storage/
│   │   │   ├── models.py            SQLAlchemy models: Audit, Capture, AdapterCall
│   │   │   └── db.py
│   │   ├── cli.py                   `seomate audit` / `migrate` / `snapshot-save` / etc.
│   │   ├── taxonomy.py              Parses o1-taxonomy.md → Catalog object
│   │   ├── config.py                Pydantic config schema (AuditScope, AuditTarget, ...)
│   │   └── data_contract.py         AuditStatus / CaptureStatus enums + RuleResult
│   ├── alembic/versions/
│   │   ├── 0001_initial_schema.py
│   │   ├── 0002_audit_status_anomalies.py
│   │   └── 0003_audit_anomalies_jsonb.py
│   ├── configs/
│   │   └── pixelette.yml            The one audit config in the repo today
│   ├── tests/
│   │   └── snapshots/
│   │       └── pixelette.json       Baseline snapshot (audit 95a8c164)
│   ├── scripts/
│   │   └── build_seo_validation_doc.py
│   └── pyproject.toml
│
├── api/                             FastAPI service (read-only)
│   ├── seomate_api/
│   │   ├── main.py                  App factory + lifespan (loads taxonomy)
│   │   ├── routes/
│   │   │   ├── audits.py
│   │   │   └── taxonomy.py
│   │   ├── schemas/
│   │   │   ├── audit.py             Pydantic response models
│   │   │   └── capture.py
│   │   └── settings.py
│   └── pyproject.toml
│
└── web/                             Next.js 16 inspection UI
    ├── app/
    │   ├── page.tsx                 (redirects to /audits)
    │   ├── audits/page.tsx
    │   └── audits/[auditId]/
    │       ├── page.tsx
    │       └── captures/[variableId]/page.tsx
    ├── lib/
    │   ├── api.ts                   Typed client matching api/schemas
    │   └── format.ts                Badge classes + formatters
    └── package.json                 Next.js 16 + React 19 + Tailwind 4
```

The `auditor`, `api`, and `web` directories are **three separate packages** that share a Postgres database. The auditor's storage models are the single source of truth — the API imports them directly to read from the same tables.

---

## 4. How to run it (cold start)

```bash
# === 1. Postgres + pgvector ===
cd seomate
docker compose up -d            # starts Postgres on :5433

# === 2. Auditor venv ===
cd auditor
python -m venv .venv
.venv/Scripts/activate          # Windows; use `.venv/bin/activate` on Linux/macOS
pip install -e .

# === 3. Environment ===
# Create auditor/.env with the keys listed in section 5 below.

# === 4. Run migrations ===
seomate migrate

# === 5. Run an audit (~6 min, ~£0.25) ===
seomate audit -c configs/pixelette.yml

# === 6. Inspect via API + Web (in two terminals) ===
# terminal A — API
cd api
../auditor/.venv/Scripts/python -m seomate_api  # binds :8000

# terminal B — web
cd web
npm install
API_BASE_URL=http://127.0.0.1:8000 npm run dev   # binds :3000

# open http://localhost:3000
```

**Quick development workflow during extractor work:**

```bash
# Run ONLY specific variables (skips LLM phase if not needed; ~3 min)
seomate audit -c configs/pixelette.yml --only "P3-29,P3-30"

# Compare a fresh audit against the baseline snapshot
seomate snapshot-check <audit-uuid>

# Save a new baseline (after deliberate extractor changes)
seomate snapshot-save <audit-uuid>
```

---

## 5. Credentials & external services

Most credentials live on Pixelette-owned accounts already; the two Google ones are on personal accounts and worth migrating off when convenient.

| Service | API key location | Owned by | Billing | Notes |
|---|---|---|---|---|
| **DataForSEO** | `auditor/.env` (DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD) | `admin@pixelette.tech` | Pay-as-you-go balance + £80/mo Backlinks subscription | Subscription commits ~£80/mo for backlinks endpoints. PAYG covers everything else. ~£0.20/audit. |
| **Anthropic Claude** | `auditor/.env` (ANTHROPIC_API_KEY) | `admin@pixelette.tech` | Prepaid balance | $25 top-up on 12 May 2026. Watch for "credit balance too low" 400s — see `MEMORY.md` and `seomate/adapters/llm.py` short-circuit logic. |
| **Gemini API** (embeddings) | `auditor/.env` (GEMINI_API_KEY) | `pixelettesales@gmail.com` | Paid tier billing attached 12 May 2026 | Used for the 768-dim page embeddings. Default RPS is 8 in `embeddings.py:80`; do NOT lower this back to 1 or you'll re-introduce the silent-regression bug from 14 May. |
| **Google PageSpeed Insights** | `auditor/.env` (PSI_API_KEY) | Temur's personal Google account | Free | Quota: 25k/day, plenty. |
| **Google Knowledge Graph** | `auditor/.env` (KG_API_KEY) | Temur's personal Google account | Free | Same project as PSI. |
| **Wikipedia / Wikidata** | none | n/a | Free | Public MediaWiki API; no key. |
| **Postgres** | local Docker (`docker-compose.yml`) | n/a | n/a | Port 5433. Connection string in `auditor/.env` as `DATABASE_URL`. |

**Migration target:** an empty SEOMate project exists on `admin@pixelette.tech` Google Cloud, intended as the long-term home for the two Gemini / PSI / KG keys currently on personal accounts. Currently empty; needs project creation + key generation + billing attachment when Pix decides to formalise ownership of those two keys.

**See also:** memory note `seomate_google_apis.md` for the full provenance trail.

---

## 5b. Source code repository

The whole project lives in a single GitHub repo:

> **`https://github.com/h-chishty/seomate`** (private)

Currently owned by Humza's personal GitHub account (`h-chishty`). Transfer to a Pix-owned org or to whichever individual takes over is a single operation in the GitHub repo settings. Pix can either:

- Create a `pixelette-tech` GitHub organisation and transfer the repo into it (preserves history + URL redirects), or
- Have me add a Pix-owned GitHub user as a collaborator and then transfer ownership to that user.

Either path keeps every commit, branch, and issue intact. Just let me know which account should receive the transfer.

---

## 5c. Build-session transcript

The complete back-and-forth that produced everything in this repo lives as a Claude Code session log at:

> `C:\Users\user\.claude\projects\c--Users-user--gemini-antigravity-playground\6391b296-d367-4b2c-b55a-56a532079651.jsonl`

It's a JSON-Lines file containing every prompt, tool call, file edit, audit run, and explanation in this project's build history. Temur specifically asked for this — useful for understanding *why* certain design choices were made when the code doesn't make the reasoning obvious. I'll send it across separately with the rest of the handover.

---

## 6. The taxonomy

The single most important file in the project is `docs/o1-taxonomy.md`. Read it before writing any extractor code.

**Structure of each variable entry:**

1. **Definition** — what the variable measures
2. **Step 1.5 — Evaluation rules** — the named pass/fail criteria (e.g. "1. Robots.txt is reachable at /robots.txt and returns 200; 2. Robots.txt contains no syntax errors; ...")
3. **Citations** — sources backing the variable's relevance
4. **Evidence weight rationale** — why this is Consensus vs Probable vs Contested vs Speculative
5. **Data source(s)** — which adapter(s) the extractor consumes
6. **Verification** — what granularity the data source delivers
7. **Cost** — operational cost notes
8. **Dependencies and cross-references** — links to related variables

**Pillars and their counts (post-removal totals):**

| Pillar | Count | Theme |
|---|---|---|
| P0 — Strategic Foundation | 18 | brand, ICP, keyword universe, KGE |
| P1 — On-Page SEO | 48 | titles, headings, schema, internal linking |
| P2 — Technical SEO | 38 | robots, sitemaps, canonicals, HTTPS, indexation |
| P3 — Off-Page Authority | 36 | backlinks, anchors, link graph, toxic refs |
| P4 — Content Operations | 23 | originality, authority, freshness, E-E-A-T |
| P5 — Local SEO | 28 | GBP, NAP, reviews, citations, local pack |
| P6 — AI Search / GEO | 32 | LLM corpora, AI Overview, Wikipedia, GEO levers |
| **Total active** | **226** | (the doc references 232 — 6 are "removed" stubs with redirect notes) |

**Removed variables (won't be re-added):**

| ID | Original name | Removal reason |
|---|---|---|
| P1-39 | Average term weight | Subsumed by P1-35 (TF-IDF / prominence) — dedup |
| P1-40 | Token count | Subsumed by P1-34 (content depth / word count) — dedup |
| P2-06 | Index tier / source type (leak) | Externally unmeasurable |
| P2-34 | llms.txt configuration | Duplicate of P6-18 |
| P2-35 | AI bot access in robots.txt | Duplicate of P6-17 |
| P3-11 | IndyRank (leak) | Externally unmeasurable |
| P3-13 | Anchor text font size (leak) | Externally unmeasurable |
| P3-16 | Dropped local anchor count (leak) | Externally unmeasurable |
| P4-18 | Goldstandard human-rated content | Externally unmeasurable |
| P6-15 | Podcast transcripts and citations | Low-ROI for the target audit profile; requires paid podcast adapter |

Every removal lives in the taxonomy as a `## P{x}-{y} — Name *(removed — May 2026 ...)*` stub explaining the rationale. **Do not remove these stubs** — they document why a slot is intentionally empty.

---

## 7. What's done, what's deferred, what's removed

**Done (production-quality):**

- All 226 active variables have a registered extractor that produces a real capture per audit
- Audit orchestration: prefetch → embeddings → LLM evaluators → extractor loop → completeness gate → consistency rules → close
- Web inspector: list / detail / variable-detail pages, status badges, reliability-flag rendering
- Migrations: 0001 (schema), 0002 (audit status enum), 0003 (anomalies JSONB)
- Snapshot regression testing against `tests/snapshots/pixelette.json`
- `--only` CLI flag for fast iteration during extractor development

**Deferred with explicit reason:**

| Item | Reason | Unblocks |
|---|---|---|
| **P0-14** Competitor discovery via SERP overlap | Circular for sites whose problem is undertargeted keywords. Need user-supplied strategic input (the proposed audit-launcher dialog) | User can declare aspirations in a future UI |
| **GBP OAuth** | 1–2 weeks of focused work; OAuth consent screen + token storage + adapter rewrite | Unlocks P5-22 (GBP posts), P5-27 (GBP engagement clicks/calls), partial P5-28 (location demotion), P3-30 (disavow read) |
| **GSC OAuth** | Same shape as GBP; smaller payoff | Unlocks P2-05 rules 2-6 (crawl-budget utilisation) and partial P2-03 (sitemap submission status) |
| **Audit-launcher UI** | Read-only API today; needs POST endpoint + background worker + auth (see section 10) | Removes the "CLI venv" friction; lets the SEO exec run audits without engineering help |
| **Multi-site validation** | Pixelette is the only site we've audited | We don't yet know how the heuristics behave on a SaaS site, a publisher, a multi-location chain, etc. Thresholds and pattern libraries are currently tuned to one profile. |

**LLM-classifier known issue (commit `5f2fb34`):**

The Tier 2 consistency check flags `techreviewer.co` as classified by both P3-34 (hub page) and P3-36 (guest-post network) at ≥0.7 confidence. This is a real LLM-prompt-inconsistency bug; the audit now flags itself `completed_with_anomalies` until either:

1. The P3-36 prompt is tightened to exclude domains already clearly hubs, or
2. The confidence threshold is raised

The data is still trustworthy — the flag just makes the inconsistency visible instead of hidden.

---

## 8. Reliability infrastructure

Three pieces of machinery exist specifically to catch silent regressions. They exist because we got burned by one (the Gemini RPS bug, 14 May 2026):

**Background:** the embeddings adapter was capped at 1 RPS as a free-tier safety margin. After Gemini billing moved to paid tier, the cap was no longer correct but stayed in place. On audits run close together, the embedding pass would silently land ≤2 of 58 pages, causing 22 downstream variables to report UNMEASURABLE. Nobody noticed for ~12 hours.

The fix (commit `2b38d09`) raised the default RPS to 8. The reliability infrastructure below was built so the same class of silent regression cannot hide again.

**1. Completeness gate** (commit `7b557cb`)

Runs at audit close. Detects:
- Embedding pass under-coverage (<90% of eligible pages embedded)
- HTML fetch under-coverage (<80% of URLs 200)
- backlinks_summary claims N main_domains but referring_domains sample is empty
- LLM configured but zero evaluations landed (the credit-balance regression)
- Embeddings configured but zero vectors persisted

When any check fires, audit status becomes `completed_with_anomalies` and the anomalies are persisted to `audits.anomalies` JSONB.

**2. Cross-extractor consistency rules** (commit `5f2fb34`)

Runs alongside the completeness gate. Three rules today:
- P3-34 (hub page) and P3-36 (guest-post network) shouldn't both flag the same domain at high confidence
- P0-07 (site focus) and P0-08 (site radius) compute from the same embeddings — their UNMEASURABLE state must match
- P3-01 (referring main domain count) must match `backlinks_summary.referring_main_domains` source value

Violations also bump the audit to `completed_with_anomalies` and persist to `audits.consistency_violations`.

**3. Snapshot regression test** (commit `7b557cb`)

`tests/snapshots/pixelette.json` is the canonical clean-run baseline (audit `95a8c164`). After any code change to a pillar, run:

```bash
seomate audit -c configs/pixelette.yml         # run a new audit
seomate snapshot-check <new-audit-uuid>        # diff against baseline; exit-1 on drift
```

Catches status drift, rule-outcome drift, and added/missing variables.

---

## 9. Open risks

In rough order of likelihood × cost:

1. **Anthropic credit balance running out silently.** When the prepaid balance hits zero, every LLM evaluator returns 400 and ~15 variables go UNMEASURABLE. The completeness gate now catches this *during* the audit, but the operator still needs to top up. Check `console.anthropic.com/settings/billing` if the audit ever fires `llm_configured_but_zero_evaluations`.

2. **Gemini quota window collisions.** RPS bump to 8 should mean this is gone. If embedding-pass coverage ever shows <90% again, check whether multiple audits were run in close succession or whether the daily quota is exhausted.

3. **DataForSEO crawl coverage drift.** The audit reported a -34.7% decay in Pixelette's referring main domains over 12 months (variable P3-25). This *could* be real link decay; it could also be DataForSEO narrowing their own crawl coverage. The two are not currently distinguishable. Cross-checking against Ahrefs for one audit would resolve this.

4. **LLM classifier consistency.** Same data, two LLM calls, contradictory verdicts (the techreviewer.co case). Tier 2 catches it; prompt tuning is needed long-term.

5. **Pixelette-only tuning.** Every threshold, every spam-phrase list, every PR-wire pattern was hand-curated against pixelettetech.com. Will produce false positives on other site profiles. Validation against a second site is the single highest-value next step *before* taking the product anywhere customer-facing.

6. **No regression tests on individual extractors.** Snapshot tests catch outcome drift but a refactor that changes extractor *logic* without changing the outcome for Pixelette would land silently. Per-extractor unit tests with mocked SiteData fixtures are the Tier 3 reliability item we never built.

---

## 10. What's next

Three honest options, ranked by what I'd actually recommend:

### Option A — Validate on a second site

**Effort:** 1–2 days
**Why:** Every threshold and heuristic is tuned to Pixelette. A second site (different vertical: e-commerce, SaaS, publisher, professional services) would tell us whether the audit is actually generalisable. Without this, anything customer-facing is built on sand.

**Concrete steps:** create a new `configs/site2.yml`, run the audit, walk through every FAILED variable manually with an SEO expert to check whether the verdict is defensible. Tune the heuristics that produce too many false positives. Re-snapshot.

### Option B — Audit-launcher UI

**Effort:** ~1 week (Sprint 1 of the launcher design)
**Why:** Removes the "needs a developer to run an audit" friction. Lets an SEO operator point SEOMATE at any URL from the browser.

**Concrete steps:**
1. Add minimal auth (API key in env or magic-link email) to the API
2. Add `POST /api/audits` endpoint that accepts URL + brand + competitors + free-text objectives
3. Add an `audit_jobs` table + a background worker process that polls it
4. Build the "New audit" dialog in `web/app/audits/new/page.tsx`
5. Status polling + redirect to detail page on completion

Design notes for this option live in the chat history but the short version: do NOT skip auth (otherwise it becomes a free internet-wide audit service at our DataForSEO cost), and treat the "objectives" field as stored-only-for-now (no extractor consumes it yet).

### Option C — GBP OAuth integration

**Effort:** 1–2 weeks
**Why:** Unlocks ~5 currently-deferred variables that would materially improve audit completeness for any business with a Google Business Profile (almost all of Pixelette's target customers). Highest-leverage of the two pending OAuth integrations.

**Concrete steps:**
1. Google Cloud Console project (use `admin@pixelette.tech` if migrating off personal accounts)
2. OAuth consent screen (will need verification for the GBP scopes)
3. Token storage table + refresh logic
4. Adapter rewrite to use OAuth tokens instead of the current API-key DataForSEO Business Data calls
5. New extractors for P5-22 (posts), P5-27 (engagement), expand P5-28 + P3-30

---

## 11. Files & commits worth reading first

If you're reading this with no context and want to understand the project quickly:

**Documents (in this order):**
1. `HANDOVER.md` ← you are here
2. `docs/o1-taxonomy.md` (don't read all 9k lines; read the intro + skim 3-4 pillars)
3. `docs/site-auditor-architecture.md` (original design doc)
4. `docs/audit-validation-pixelettetech.docx` (the SEO-exec view of an audit)

**Code (in this order):**
1. `auditor/seomate/orchestrator.py` — the audit lifecycle
2. `auditor/seomate/pillars/_base.py` — the `SiteData` object that every extractor reads from
3. `auditor/seomate/pillars/p3_backlinks.py` — the densest pillar, most representative of the extractor pattern
4. `auditor/seomate/utils/llm_evaluation.py` — the batched LLM evaluator framework
5. `api/seomate_api/main.py` and `api/seomate_api/routes/audits.py`
6. `web/app/audits/[auditId]/page.tsx` — the audit detail view

**Recent commits worth reading the diffs of:**

| Commit | What | Why |
|---|---|---|
| `7c1b052` | Inspector UI complete | Most recent. Shows the API extension pattern |
| `5f2fb34` | Cross-extractor consistency rules | The "techreviewer.co" story |
| `7b557cb` | Completeness gate + snapshot test | The Gemini RPS regression aftermath |
| `2b38d09` | Embeddings RPS bump | The actual bug fix; don't undo this |
| `5ad72c6` | LLM short-circuit | Handles Anthropic credit-balance outages |
| `41981d7` | P3 pillar complete | Shows the per-pillar wire-up pattern |

---

## 12. Glossary

- **Audit** — one execution of the full extractor loop against one site. Produces 226 captures and an `audits` row.
- **Capture** — one variable's verdict on one audit run. Stored as one row per (audit_id, variable_id).
- **Extractor** — the Python function that produces a capture for one variable. Registered via `@register_extractor("P3-12")`.
- **Pillar** — one of the seven top-level groupings (P0–P6).
- **Evidence weight** — Consensus / Probable / Contested / Speculative. The taxonomy's claim about how confident we should be that the variable matters.
- **Prefetch** — the data-collection phase before extractors run. Hits DataForSEO, Gemini, the LLM evaluators, etc.
- **Step 1.5 rules** — the named pass/fail criteria for a variable, defined in the taxonomy.
- **Completeness gate** — the post-extractor check that flags silent data-loss patterns.
- **Consistency rule** — a cross-extractor invariant (e.g. P3-34 vs P3-36 shouldn't both flag the same domain).
- **Snapshot** — a JSON file representing a known-good audit, used as a baseline for regression detection.

---

## Contact

If you're picking this project up and need context I haven't captured here, my personal email is `h.chishty@ymail.com`. Happy to walk through anything that doesn't make sense, or to do a live handover call.

The most important advice I can give: **read `o1-taxonomy.md` before you change any extractor.** The taxonomy is the constitution. Every shortcut that's tempting in code review either violates the taxonomy's evidence-weight assignments or papers over a measurement honesty problem the taxonomy explicitly forbids. When in doubt, choose UNMEASURABLE with a clear remediation note over a fake PASSED.

— Humza
