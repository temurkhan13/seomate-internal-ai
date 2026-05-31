# SEOMATE — Site Auditor Architecture (H1)

**Project:** SEOMATE
**Component:** Site Auditor (Hypothesis 1)
**Owner:** Humza Chishty
**Status:** Draft 2 (May 2026)
**Constitutional reference:** `o1-taxonomy.md` (232 variables, 7 pillars)

---

## 1. Purpose

The Site Auditor is the data capture layer of SEOMATE. It pulls every measurable SEO/GEO variable from a configured live site and writes them into a uniform per-variable contract that downstream layers can consume without per-variable special-casing. A bare-bones inspection UI is included so we can validate captures and spot gaps during dogfood.

**One job:** capture data faithfully and consistently, and present it for inspection. Not analyse it, not recommend on it, not score it.

## 2. Non-goals (explicitly out of scope at H1)

- Recommendation generation
- Scoring / weighting
- Strategy or prioritisation
- Findings narrative
- Multi-tenancy / SaaS
- Auto-deployment of fixes
- Industry/site-type weighting (constitutional decision in `o1-taxonomy.md`)
- Dependency on client-owned analytics tooling (GA4, GTM, Pixel, Mixpanel, etc.) — the auditor must work without any of that access (see §3.1)

## 3. Hypothesis being tested

> Given the O1 taxonomy, we can build a bare-bones data-capture layer that pulls every measurable variable from a live website **into a uniform per-variable contract** that downstream layers can consume without per-variable special-casing. Where a variable cannot be captured at all, that failure is a finding (the taxonomy gets revised) rather than a blocker. Where a variable can be captured but the data does not fit the contract, the contract is the bug, not the data.

## 3.1 Externally-observable design property

A constitutional property of SEOMATE: **the auditor never requires access to a client's owned analytics or marketing tooling** (GA4, GTM, Meta Pixel, LinkedIn Insight, Mixpanel, Hotjar, Adobe Launch, Tealium, Segment, Optimizely, etc.). Every variable in the taxonomy is captured from one of:

| Source category | What it covers | Access requirement |
|----------------|----------------|---------------------|
| External SEO APIs | DataForSEO On-Page / SERP / Keywords / Backlinks / Labs | Our API key only — observes any public site |
| Public Google APIs | Knowledge Graph Search, CrUX, PageSpeed Insights | Our API key only — public data |
| Public web | Wikipedia / Wikidata / MediaWiki, Reddit, Stack Exchange, YouTube, Common Crawl, NewsAPI / GDELT, Listen Notes / Podchaser, llms.txt, robots.txt, structured data, raw HTML | Anyone can fetch |
| AI search engines | Perplexity, ChatGPT / Claude / Gemini with web tools | Our API keys only |
| Owner-granted Google APIs (only category requiring client cooperation) | GSC URL Inspection / Sitemaps / Crawl Stats; GBP Profile / Performance | Site owner OAuth — see fall-back below |
| Composition over captured data | Link graph authority, embeddings, TF-IDF, cluster detection, freshness diffs | None — derived from already-captured data |

**Owner-granted access (GSC, GBP) — fall-back behaviour:**

- **GSC unavailable:** indexation-related variables (P2-04 indexation status, P2-05 crawl budget) fall back from authoritative GSC data to weaker external inference (`site:` query SERP results, public sitemap fetch, robots.txt analysis). Captures retain `status='partial'` with `errors[]` noting the fallback path; the data is still useful, just less authoritative.
- **GBP unavailable:** local-pillar variables that need first-class engagement data (P5-27 engagement signals: clicks, calls, direction requests) become `status='unmeasurable'` for that subject. Variables with public observability (P5-01 proximity, P5-02/03 categories, P5-04 profile completeness from visible fields, P5-05 NAP consistency, P5-09 review count, P5-10 review rating, P5-21 photos, etc.) continue to capture from public Maps / SERP scraping.

**Why this matters:** the auditor works on any website we point it at, regardless of whether the site owner cooperates. For www.pixelettetech.com (where we have full owner access), no degradation. For prospect or competitor audits later, the architecture still produces valuable data without needing access we won't get.

## 4. High-level architecture

Three layers: a Python **auditor** that captures data, a Python **API** (FastAPI) that exposes captures for read access, a Next.js **web UI** that consumes the API. All three share a single Postgres database (with pgvector). For local dogfood, all three run on Humza's machine. Vercel hosts the web UI when we deploy.

```
                       ┌───────────────────────────┐
                       │  Next.js  (web/, Vercel)  │
                       │  - audits list            │
                       │  - audit overview         │
                       │  - capture filter / drill │
                       │  - audit compare diff     │
                       └─────────────┬─────────────┘
                                     │  HTTPS (typed JSON)
                                     ▼
                       ┌───────────────────────────┐
                       │  FastAPI  (api/)          │
                       │  - read-only endpoints    │
                       │  - Pydantic responses     │
                       │  - OpenAPI for TS gen     │
                       └─────────────┬─────────────┘
                                     │  SQLAlchemy
                                     ▼
                       ┌───────────────────────────┐
                       │  Postgres 16 + pgvector   │
                       │  - audits, captures,      │
                       │    adapter_calls          │
                       │  - JSONB for value/rules  │
                       └─────────────▲─────────────┘
                                     │  SQLAlchemy
                                     │  (writer)
┌────────────────────────┐           │
│  CLI (auditor/seomate  │───────────┤
│  audit, inspect, etc.) │           │
└───────────┬────────────┘           │
            │                        │
            ▼                        │
┌──────────────────────────┐         │
│  Configuration loader    │         │
│  (YAML + env credentials)│         │
└───────────┬──────────────┘         │
            │                        │
            ▼                        │
┌──────────────────────────┐         │
│  Audit orchestrator      │         │
│  - dependency order      │         │
│  - pillar dispatch       │         │
│  - cost cap enforcement  │         │
│  - asyncio concurrency   │         │
└───────────┬──────────────┘         │
            │                        │
            ▼                        │
┌──────────────────────────┐         │
│  Pillar capture modules  │         │
│  (P0..P6, parallel)      │         │
└───────────┬──────────────┘         │
            │                        │
            ▼                        │
┌──────────────────────────┐         │
│  Variable extractors     │─────────┘
│  (one fn per variable)   │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────────────────────────────┐
│  External adapters (rate-limited, retrying,      │
│  cost-tracking)                                  │
│  - DataForSEO (On-Page, SERP, Keywords, Labs,    │
│    Backlinks)                                    │
│  - Google Search Console (URL Inspection,        │
│    Sitemaps, Crawl Stats)                        │
│  - Google Business Profile (incl. Performance)   │
│  - Google Knowledge Graph Search                 │
│  - Wikipedia / Wikidata / MediaWiki              │
│  - Reddit / Stack Exchange                       │
│  - YouTube Data, Listen Notes / Podchaser        │
│  - Common Crawl Index, NewsAPI / GDELT           │
│  - Anthropic / OpenAI (LLM evaluation)           │
│  - Gemini / OpenAI embeddings                    │
│  - Perplexity API + cross-assistant eval         │
└──────────────────────────────────────────────────┘
```

The auditor (CLI + orchestrator + extractors + adapters) is plain Python with `asyncio`. No LLM-driven control flow, no Temporal, no agents inside the auditor itself — determinism is the design constraint. The FastAPI layer is read-only: the auditor is the only writer to Postgres.

## 5. Data contract (the most important part)

Every variable produces a `CaptureRecord`. This is the constitutional contract every downstream layer reads against.

### 5.1 CaptureRecord schema

```python
@dataclass
class RuleResult:
    rule_id: int
    rule_text: str
    passed: bool
    evidence: Dict[str, Any]      # rule-specific structured proof
    notes: Optional[str] = None

@dataclass
class CaptureRecord:
    # Identity
    capture_id: str               # UUID
    audit_id: str                 # UUID, links to audits table
    variable_id: str              # "P1-01"
    pillar: str                   # "P1"
    captured_at: datetime         # UTC
    taxonomy_version: str         # "1.0" — frozen when audit started

    # Subject of measurement
    subject_type: str             # "site" | "url" | "business" | "brand" | "query"
    subject_id: str               # canonical identifier (URL/domain/place_id/etc.)

    # Result
    status: str
    # one of:
    #   "passed"        — all rules passed (or single measurement returned cleanly)
    #   "failed"        — rules ran, one or more failed
    #   "partial"       — some rules ran, some couldn't (e.g., one API timed out)
    #   "not_applicable"— variable doesn't apply to this subject
    #   "error"         — capture failed entirely (errors[] populated)
    #   "unmeasurable"  — variable cannot be measured given current data sources;
    #                     taxonomy revision flag

    # The raw measurement
    value: Any
    # type varies per variable; conforms to that variable's documented value schema.
    # For Step 1.5 variables, value is typically a structured object describing the
    # underlying data; the rule outcomes live in `rules`.

    # For Step 1.5 variables only
    rules: Optional[List[RuleResult]] = None

    # Methodology metadata
    evidence_weight: str          # "Consensus" | "Probable" | "Contested" | "Speculative"
    data_sources_used: List[str]  # e.g. ["dataforseo.on_page.instant_pages",
                                  #       "composition.duplicate_title_aggregation"]
    cost_incurred_gbp: float      # incremental cost of this single capture
    staleness_seconds: Optional[int]  # how old is the underlying data
    errors: Optional[List[str]] = None
    raw_response_ref: Optional[str] = None  # path to debug snapshot if retained
```

### 5.2 Why this contract

- **`variable_id` + `taxonomy_version`** anchors every capture to a specific entry in `o1-taxonomy.md`. If we revise a rule, old captures don't silently mean something new.
- **`status`** is a controlled vocabulary. Downstream layers can filter `WHERE status = 'failed'` without parsing raw values.
- **`rules`** carries per-rule outcomes for Step 1.5 variables. The downstream analyser doesn't need the taxonomy in context to know which specific rule failed.
- **`evidence_weight`** is denormalised onto the capture so Model B operational treatment can be applied without a join.
- **`data_sources_used`** answers "which adapters fired" for debugging and cost attribution.
- **`cost_incurred_gbp`** rolls up to per-audit and per-adapter cost reports.
- **`staleness_seconds`** is essential for variables that depend on slow-updating sources (GSC has 2–3 day lag; Wikipedia revisions are real-time; Common Crawl is monthly).
- **`status = 'unmeasurable'`** is a first-class outcome — the taxonomy needs revising for that variable.

### 5.3 Append-only ledger

Captures are never overwritten. Every audit run inserts new rows. This buys us:
- Trend analysis for variables that depend on history (P1-44 update magnitude, P1-45 cadence, P3-24/25 backlink velocity, P4-21 mass-production detection)
- Attribution for Phase B+ ("did anything change after we deployed the fix?")
- Reproducibility — old audits remain readable

Disk cost is trivial at one-site scale.

## 6. Module / package layout (monorepo)

The repo is a monorepo with three sub-projects: `auditor/` (Python), `api/` (Python/FastAPI), `web/` (Next.js). They share a single Postgres database with schema owned by `auditor/` via Alembic.

```
seomate/                                # monorepo root
├── README.md
├── docker-compose.yml                  # Postgres 16 + pgvector for local dev
├── .env.example                        # all expected env vars
├── docs/
│   └── site-auditor-architecture.md
│
├── auditor/                            # Python — the H1 capture layer
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/                        # DB migrations (canonical schema)
│   │   ├── env.py
│   │   └── versions/
│   ├── seomate/
│   │   ├── __init__.py
│   │   ├── cli.py                      # `seomate audit | inspect | smoke | migrate`
│   │   ├── config.py                   # YAML loader, schema validation
│   │   ├── orchestrator.py             # audit lifecycle, dependency resolution
│   │   ├── data_contract.py            # CaptureRecord, RuleResult, enums
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── db.py                   # SQLAlchemy engine, session
│   │   │   ├── models.py               # ORM models (audits, captures, etc.)
│   │   │   └── repository.py           # CaptureRecord persistence helpers
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── _base.py                # interface + retry/rate-limit/cost decorators
│   │   │   ├── dataforseo.py
│   │   │   ├── gsc.py
│   │   │   ├── gbp.py
│   │   │   ├── google_kg.py
│   │   │   ├── wikipedia.py
│   │   │   ├── wikidata.py
│   │   │   ├── reddit.py
│   │   │   ├── stack_exchange.py
│   │   │   ├── youtube.py
│   │   │   ├── listen_notes.py
│   │   │   ├── common_crawl.py
│   │   │   ├── newsapi.py
│   │   │   ├── perplexity.py
│   │   │   ├── llm.py                  # Claude / GPT shared
│   │   │   └── embeddings.py           # Gemini Embedding 2 / OpenAI
│   │   ├── pillars/
│   │   │   ├── __init__.py
│   │   │   ├── _base.py
│   │   │   ├── p0_strategic.py
│   │   │   ├── p1_onpage.py
│   │   │   ├── p2_technical.py
│   │   │   ├── p3_offpage.py
│   │   │   ├── p4_content_ops.py
│   │   │   ├── p5_local.py
│   │   │   └── p6_geo.py
│   │   ├── taxonomy/
│   │   │   ├── loader.py               # parse o1-taxonomy.md → structured catalog
│   │   │   ├── schemas.py              # per-variable value/rule schemas
│   │   │   └── catalog.py              # the 232-variable registry
│   │   ├── composition/
│   │   │   ├── link_graph.py
│   │   │   ├── embeddings.py
│   │   │   ├── tfidf.py
│   │   │   ├── topic_clustering.py
│   │   │   └── freshness_diff.py
│   │   └── utils/
│   │       ├── retry.py
│   │       ├── rate_limit.py
│   │       ├── logging.py
│   │       ├── cost_tracker.py
│   │       └── async_runner.py
│   ├── tests/
│   │   ├── adapters/
│   │   ├── pillars/
│   │   ├── composition/
│   │   ├── fixtures/
│   │   └── e2e/
│   ├── configs/
│   │   ├── pixelette.yml
│   │   └── pixelette-keywords.yml
│   └── data/
│       └── logs/                       # per-audit JSON logs (gitignored)
│
├── api/                                # Python — read-only API for the UI
│   ├── pyproject.toml
│   ├── seomate_api/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI app
│   │   ├── routes/
│   │   │   ├── audits.py
│   │   │   ├── captures.py
│   │   │   └── compare.py
│   │   ├── schemas/                    # Pydantic response models
│   │   │   ├── audit.py
│   │   │   └── capture.py
│   │   ├── deps.py                     # DB session dependency
│   │   └── settings.py
│   └── tests/
│
├── web/                                # Next.js — UI (Vercel deploy target)
│   ├── package.json
│   ├── next.config.js
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── app/                            # App Router
│   │   ├── layout.tsx
│   │   ├── page.tsx                    # /  → redirects to /audits
│   │   ├── audits/
│   │   │   ├── page.tsx                # list of audits
│   │   │   └── [auditId]/
│   │   │       ├── page.tsx            # audit overview
│   │   │       ├── captures/
│   │   │       │   ├── page.tsx        # filterable captures table
│   │   │       │   └── [variableId]/
│   │   │       │       └── page.tsx    # single capture detail
│   │   │       └── compare/
│   │   │           └── [otherId]/
│   │   │               └── page.tsx    # diff between two audits
│   │   └── api/                        # (none — proxy through FastAPI)
│   ├── components/
│   │   ├── ui/                         # shadcn/ui primitives
│   │   ├── capture-card.tsx
│   │   ├── rules-table.tsx
│   │   ├── status-badge.tsx
│   │   ├── pillar-summary.tsx
│   │   └── audit-compare.tsx
│   └── lib/
│       ├── api-client.ts               # typed fetch wrapper
│       ├── types.ts                    # TS types generated from FastAPI OpenAPI
│       └── utils.ts
│
└── credentials/                        # gitignored, env-var-referenced
```

**Schema ownership:** `auditor/alembic/` is the single source of truth for DB schema. Both `auditor/` (writer) and `api/` (reader) use the same SQLAlchemy ORM models in `auditor/seomate/storage/models.py`. The `api/` package imports the auditor's models package as a dev-mode local install (`pip install -e ../auditor`).

**Type sharing for the frontend:** FastAPI's OpenAPI schema is exported and Next.js generates TypeScript types from it via `openapi-typescript` or similar. No manual type duplication.

## 7. Configuration model

YAML-driven. Credentials by env-var reference, never embedded.

```yaml
# configs/pixelette.yml
audit:
  site:
    domain: pixelettetech.com
    primary_url: https://www.pixelettetech.com
    business_type: saas-marketing
    locales: [en-GB, en-US]

  keywords:
    file: configs/pixelette-keywords.yml   # external keyword list

  competitors:
    - example-competitor1.com
    - example-competitor2.com

  scope:
    pillars: all                            # or [P0, P1, P2] for partial
    h1_stage: a                             # a | b | c | d | all
    skip_variables: []                      # explicit skip list

  brand:
    name: Pixelette Technologies
    aliases: [Pixelette, Pixelette Tech]
    legal_entities: [Pixelette Technologies Ltd.]

  gbp:
    place_id: ""                            # if applicable

apis:
  dataforseo:
    login_env: DATAFORSEO_LOGIN
    password_env: DATAFORSEO_PASSWORD
  gsc:
    service_account_file: ./credentials/gsc.json
    property_url: https://www.pixelettetech.com/
  gbp:
    service_account_file: ./credentials/gbp.json
    account_id_env: GBP_ACCOUNT_ID
  google_kg:
    api_key_env: GOOGLE_KG_API_KEY
  anthropic:
    api_key_env: ANTHROPIC_API_KEY
  openai:
    api_key_env: OPENAI_API_KEY
  gemini:
    api_key_env: GEMINI_API_KEY
  perplexity:
    api_key_env: PERPLEXITY_API_KEY
  newsapi:
    api_key_env: NEWSAPI_KEY
  reddit:
    client_id_env: REDDIT_CLIENT_ID
    client_secret_env: REDDIT_CLIENT_SECRET
  listen_notes:
    api_key_env: LISTEN_NOTES_API_KEY

run:
  parallelism: 4
  rate_limits:
    dataforseo_rps: 5
    google_kg_rps: 10
    perplexity_rps: 1
  timeout_seconds: 300
  cost_cap_gbp: 5.00
  cost_warn_at: 0.80                        # warn at 80% of cap
  retain_raw_responses: true                # for debugging

storage:
  db_path: ./data/seomate.db
  log_dir: ./data/logs
```

## 8. Storage schema (Postgres 16 + pgvector, append-only)

Schema owned by `auditor/alembic/`. Migrations applied via `seomate migrate`. JSONB columns get GIN indexes where we expect to query inside them.

```sql
-- Required Postgres extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";   -- pgvector for embedding-based queries

-- Audit run metadata
CREATE TABLE audits (
    audit_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ,
    site_domain         TEXT NOT NULL,
    config_snapshot     JSONB NOT NULL,
    taxonomy_version    TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN
        ('running', 'completed', 'partial', 'failed', 'cost_capped')),
    total_cost_gbp      NUMERIC(12, 4),
    variables_attempted INTEGER NOT NULL DEFAULT 0,
    variables_passed    INTEGER NOT NULL DEFAULT 0,
    variables_failed    INTEGER NOT NULL DEFAULT 0,
    variables_errored   INTEGER NOT NULL DEFAULT 0,
    variables_partial   INTEGER NOT NULL DEFAULT 0,
    variables_unmeasurable INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_audits_site_started ON audits (site_domain, started_at DESC);

-- The capture ledger (one row per (audit, variable, subject) tuple)
CREATE TABLE captures (
    capture_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id            UUID NOT NULL REFERENCES audits(audit_id) ON DELETE CASCADE,
    variable_id         TEXT NOT NULL,                   -- "P1-01"
    pillar              TEXT NOT NULL,                   -- "P1"
    captured_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    taxonomy_version    TEXT NOT NULL,
    subject_type        TEXT NOT NULL,                   -- site | url | business | brand | query
    subject_id          TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN
        ('passed', 'failed', 'partial', 'not_applicable', 'error', 'unmeasurable')),
    value               JSONB,                           -- raw measurement
    rules               JSONB,                           -- List[RuleResult] for Step 1.5 vars
    evidence_weight     TEXT NOT NULL CHECK (evidence_weight IN
        ('Consensus', 'Probable', 'Contested', 'Speculative')),
    data_sources_used   JSONB NOT NULL DEFAULT '[]'::jsonb,
    cost_incurred_gbp   NUMERIC(12, 6) NOT NULL DEFAULT 0,
    staleness_seconds   INTEGER,
    errors              JSONB,                           -- List[str]
    raw_response_ref    TEXT,
    embedding           VECTOR(768)                      -- nullable; only populated for embedding-based vars
);

CREATE INDEX idx_captures_audit         ON captures (audit_id);
CREATE INDEX idx_captures_variable      ON captures (audit_id, variable_id);
CREATE INDEX idx_captures_subject_time  ON captures (subject_type, subject_id, captured_at DESC);
CREATE INDEX idx_captures_status        ON captures (audit_id, status);
CREATE INDEX idx_captures_pillar_status ON captures (audit_id, pillar, status);
CREATE INDEX idx_captures_value_gin     ON captures USING GIN (value);
CREATE INDEX idx_captures_rules_gin     ON captures USING GIN (rules);
CREATE INDEX idx_captures_embedding_ivfflat
    ON captures USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Adapter-level call log for cost attribution and debugging
CREATE TABLE adapter_calls (
    call_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_id            UUID NOT NULL REFERENCES audits(audit_id) ON DELETE CASCADE,
    capture_id          UUID REFERENCES captures(capture_id) ON DELETE SET NULL,
    adapter             TEXT NOT NULL,
    endpoint            TEXT NOT NULL,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    duration_ms         INTEGER,
    cost_gbp            NUMERIC(12, 6) NOT NULL DEFAULT 0,
    status_code         INTEGER,
    error               TEXT
);

CREATE INDEX idx_adapter_calls_audit   ON adapter_calls (audit_id);
CREATE INDEX idx_adapter_calls_adapter ON adapter_calls (audit_id, adapter);
CREATE INDEX idx_adapter_calls_started ON adapter_calls (started_at DESC);
```

**Why pgvector now rather than later:** several variables produce embeddings during capture (P0-09 site embedding, P0-10 page embedding, P1-46 near-duplicate detection via embedding similarity, P6-21 vector retrievability). Storing them in Postgres with pgvector means the API and downstream Phase A analyser can do similarity queries natively (`ORDER BY embedding <-> :query_vec LIMIT 5`) without us shipping vectors out to a separate vector store. 768-dim is the Gemini Embedding 2 size used elsewhere in Pixelette stacks; same dimension means cross-system embedding consistency.

## 9. Run lifecycle

1. **CLI parse:** `seomate audit --config=configs/pixelette.yml [--stage=a]`
2. **Config load:** YAML parsed, env vars resolved, schema validated. Missing credentials = fail fast.
3. **Audit init:** new `audit_id` (UUID), insert `audits` row with `status='running'` and config snapshot.
4. **Taxonomy snapshot:** read `o1-taxonomy.md`, parse into structured catalog, freeze version for this audit.
5. **Plan:** orchestrator builds the variable execution plan:
   - Filter by `scope.pillars` and `scope.h1_stage`
   - Resolve variable dependency graph (P1-03 needs P0-13 keyword mapping; P4-06 needs nine upstream variables; etc.)
   - Build a topologically-sorted DAG of capture tasks
6. **Pre-fetch site data:** one shared crawl fetch via DataForSEO On-Page (full-site mode) so Pillar 1/2 extractors share the same crawl rather than re-crawling.
7. **Execute:** orchestrator dispatches capture tasks respecting:
   - Dependency order (downstream waits for upstream)
   - Per-adapter rate limits
   - `run.parallelism` cap
   - `run.cost_cap_gbp` (hard halt)
8. **Per-extractor:**
   - Build `CaptureRecord`
   - Persist to DB
   - Update audit running totals
9. **Aggregate:** orchestrator updates `audits` row to `status='completed'` (or `partial` / `cost_capped` / `failed`), writes summary counts.
10. **Output:** CLI prints terse summary; full audit detail accessed via `seomate inspect <audit_id>`.

## 10. Variable extractor pattern

Every variable is a function with the same shape:

```python
async def capture_p1_01(ctx: AuditContext, site: SiteData) -> CaptureRecord:
    """P1-01 — Title tag presence and uniqueness (Consensus)."""

    # Pull required raw data via adapters
    pages = await ctx.adapters.dataforseo.on_page_titles(site.urls)
    # pages: Dict[url -> {"title": str | None, "duplicate_title_in_head": bool}]

    rules: list[RuleResult] = []

    # Rule 1: Every indexable page has a <title> element
    missing = [u for u, p in pages.items() if p["title"] is None]
    rules.append(RuleResult(
        rule_id=1,
        rule_text="Every indexable page has a <title> element",
        passed=(len(missing) == 0),
        evidence={"pages_missing_title": missing},
    ))

    # Rule 2: Title text is non-empty
    blank = [u for u, p in pages.items()
             if p["title"] is not None and not p["title"].strip()]
    rules.append(RuleResult(
        rule_id=2,
        rule_text="Title text is non-empty (not whitespace, placeholder, or unrendered template)",
        passed=(len(blank) == 0),
        evidence={"pages_with_blank_title": blank},
    ))

    # Rule 3: No two indexable pages share the same title
    title_to_urls: dict[str, list[str]] = {}
    for u, p in pages.items():
        if p["title"]:
            title_to_urls.setdefault(p["title"].strip().lower(), []).append(u)
    duplicates = {t: us for t, us in title_to_urls.items() if len(us) > 1}
    rules.append(RuleResult(
        rule_id=3,
        rule_text="No two indexable pages share the same title",
        passed=(len(duplicates) == 0),
        evidence={"duplicate_title_clusters": duplicates},
    ))

    # Rule 4: Single <title> element per page
    multi_title = [u for u, p in pages.items() if p["duplicate_title_in_head"]]
    rules.append(RuleResult(
        rule_id=4,
        rule_text="Single <title> element per page (no duplicates in head)",
        passed=(len(multi_title) == 0),
        evidence={"pages_with_multiple_title_elements": multi_title},
    ))

    # Rules 5–6 ... (non-indexable exemption, distinct failure modes)

    overall = "passed" if all(r.passed for r in rules) else "failed"

    return CaptureRecord(
        capture_id=str(uuid4()),
        audit_id=ctx.audit_id,
        variable_id="P1-01",
        pillar="P1",
        captured_at=utcnow(),
        taxonomy_version=ctx.taxonomy_version,
        subject_type="site",
        subject_id=site.domain,
        status=overall,
        value={
            "pages_audited": len(pages),
            "duplicate_title_clusters": list(duplicates.keys()),
        },
        rules=rules,
        evidence_weight="Consensus",
        data_sources_used=["dataforseo.on_page.instant_pages"],
        cost_incurred_gbp=ctx.cost_tracker.delta_since_marker(),
        staleness_seconds=0,
    )
```

**Conventions:**
- Function name: `capture_<variable_id_lowercased_with_underscores>` → `capture_p1_01`, `capture_p6_25`, etc.
- Always async (so we can run them concurrently).
- Always returns a single `CaptureRecord` (or `None` only if `not_applicable`).
- Never raises into the orchestrator: catch all unexpected exceptions, populate `errors`, set `status='error'`. Failure is data, not a stop signal.
- Cost tracker uses `delta_since_marker()` so each extractor records its incremental spend independently.

## 11. Adapter pattern

Each adapter is a thin async client that:
- Encapsulates auth, retry, rate-limit, cost-recording for one external service
- Exposes domain-specific methods returning normalised dataclasses (not raw API JSON)
- Records each call into `adapter_calls` table

```python
class DataForSEOAdapter(BaseAdapter):
    name = "dataforseo"

    @rate_limited(rps=5)
    @retry(max_attempts=3, backoff=ExponentialBackoff)
    @cost_tracked
    async def on_page_titles(self, urls: list[str]) -> dict[str, OnPageTitleResult]:
        ...

    @rate_limited(rps=5)
    @retry(max_attempts=3, backoff=ExponentialBackoff)
    @cost_tracked
    async def serp_organic(self, query: str, location: str = "United Kingdom") -> SerpResult:
        ...

    # ... etc
```

The decorators handle:
- `@rate_limited`: per-adapter token bucket
- `@retry`: transient errors only (rate-limit, 5xx, timeout); 4xx auth fails fast
- `@cost_tracked`: writes the call into `adapter_calls`, increments the audit's `total_cost_gbp`

## 12. Error handling philosophy

| Layer | On error |
|-------|----------|
| Adapter | Retry transient (rate-limit, 5xx, timeout). Fail fast on 4xx (auth/bad-request). Raise typed exceptions. |
| Variable extractor | Catch all. Populate `errors[]`. Set `status='error'` or `status='partial'` if some rules ran. Always return a `CaptureRecord`. |
| Orchestrator | Continue on per-variable errors. Halt on systemic failure (DB unreachable, all adapters down, cost cap hit). |
| CLI | Non-zero exit only on systemic failure. Per-variable errors are content of the run, not a failure mode. |

This means a single audit can complete with a mix of `passed`, `failed`, `partial`, `error`, and `unmeasurable` captures — and that mix is itself the deliverable.

## 13. Cost tracking & cap

- Every `@cost_tracked` adapter call records its £ cost
- `CostTracker` per audit accumulates total
- Each `CaptureRecord.cost_incurred_gbp` = delta from start to end of that extractor
- Soft warning logged at `cost_warn_at × cost_cap_gbp`
- Hard halt at `cost_cap_gbp` — orchestrator stops dispatching new captures, marks audit `cost_capped`
- Per-adapter cost summary surfaced in `seomate inspect <audit_id>`

## 13.5 API layer (FastAPI)

Read-only HTTP API exposing capture data to the Next.js UI. Single source of truth for what the UI sees; the auditor never writes through the API.

**Endpoints (initial, read-only):**

| Route | Returns |
|-------|---------|
| `GET /api/audits` | Paginated list of audits with summary counts |
| `GET /api/audits/{audit_id}` | Single audit overview (per-pillar status counts, cost breakdown) |
| `GET /api/audits/{audit_id}/captures` | Capture list, filterable by `pillar`, `status`, `evidence_weight`, `subject_type` |
| `GET /api/audits/{audit_id}/captures/{variable_id}` | Single capture detail including full rules array, value, errors |
| `GET /api/audits/{audit_id}/adapter-calls` | Adapter call log for cost attribution / debugging |
| `GET /api/audits/{audit_id}/cost-summary` | Cost breakdown per adapter and per pillar |
| `GET /api/audits/compare?a={audit_id}&b={audit_id}` | Side-by-side diff: which variables changed status, which changed value, which gained or lost rules |
| `GET /api/taxonomy/variables/{variable_id}` | The variable definition from `o1-taxonomy.md` (rules, sources, weight) — for showing context next to captures |

**Stack:**
- FastAPI 0.110+, async by default
- SQLAlchemy 2.0 (shared models package with `auditor/`)
- Pydantic v2 response models
- OpenAPI schema exposed at `/openapi.json` for Next.js TypeScript generation
- No auth in H1 (single-user local dogfood). Auth and tenancy added when SEOMATE moves beyond dogfood.

**Local dev:** `uvicorn seomate_api.main:app --reload --port 8000`

## 13.6 Web UI (Next.js)

Bare-bones inspection UI. Read-only, focused on one job: making H1 captures visible in human-readable form.

**Pages:**

| Route | Purpose |
|-------|---------|
| `/audits` | Audits list. Columns: site, started_at, completed_at, total_cost_gbp, pass / fail / error / unmeasurable counts. Click → audit detail. |
| `/audits/[auditId]` | Audit overview. Per-pillar summary (P0..P6 with status counts), total cost, top-5 most expensive adapters, list of unmeasurable variables flagged for taxonomy revision. |
| `/audits/[auditId]/captures` | Filterable capture table. Filters: pillar, status, evidence_weight, subject_type, search by variable_id. Table shows: variable_id, pillar, weight, status badge, subject, cost. Click → capture detail. |
| `/audits/[auditId]/captures/[variableId]` | Capture detail. Status banner, the variable's definition (fetched from `/api/taxonomy/variables/...`), rules table (each rule with pass/fail and structured evidence rendered as expandable JSON tree), raw value, data sources used, cost, staleness, errors. |
| `/audits/[auditId]/compare/[otherId]` | Compare diff. Lists variables that changed status, value, or rule outcomes between the two audits. |

**Stack:**
- Next.js 14 App Router, React Server Components
- Tailwind CSS + shadcn/ui for components
- TanStack Query for client-side data fetching
- Zod for runtime validation of API responses
- TypeScript types generated from FastAPI OpenAPI via `openapi-typescript`

**Local dev:** `cd web && npm run dev` → http://localhost:3000

**Vercel deployment:** `web/` deploys to Vercel as a standalone Next.js app. The FastAPI backend is reached via a public URL (deployed later — Fly.io or Railway are likely candidates; auditor stays as a worker, not a publicly-exposed service). For H1 dogfood, deployment is not required — local dev loop is the working environment.

## 13.7 Local development workflow

Single-developer loop:

```
# 1. Boot Postgres
docker compose up -d

# 2. Apply migrations (first time and after schema changes)
cd auditor && seomate migrate

# 3. Run an audit
seomate audit --config=configs/pixelette.yml

# 4. (in another terminal) Boot the API
cd api && uvicorn seomate_api.main:app --reload

# 5. (in another terminal) Boot the web UI
cd web && npm run dev

# 6. Open localhost:3000, inspect audits
```

Three terminals for the full loop. Each layer can be developed and tested independently.

## 14. Logging and observability

- Structured JSON logs (`structlog`) per audit at `data/logs/audit-<audit_id>.json`
- Each log line: `audit_id`, `variable_id` (when applicable), `adapter` (when applicable), `event`, `duration_ms`, `cost_gbp`
- CLI output during run: pillar-level progress bar, running cost, capture counts (passed/failed/error)
- After the run: `seomate inspect <audit_id>` prints structured summary; `seomate inspect <audit_id> --variable=P1-01` prints the full capture record including rules

## 15. Testing approach

| Level | What | Tool |
|-------|------|------|
| Unit (adapter) | Mock external HTTP, test response normalisation, retry/rate-limit semantics | `pytest`, `respx` for httpx mocking |
| Unit (extractor) | Mock adapter responses with canonical fixtures, verify each rule's logic and the resulting `CaptureRecord` | `pytest` |
| Unit (composition) | Test link-graph authority, embedding similarity, TF-IDF, freshness diff against known inputs | `pytest` |
| Integration | Replay saved fixture audit (a frozen www.pixelettetech.com response set) end-to-end, verify DB state | `pytest` |
| Live smoke | Single command `seomate smoke` runs against www.pixelettetech.com with cost cap £0.50 — confirms credentials, adapters, and enough variables work for a sanity check | manual |

## 16. Build sequencing — Foundation → H1a → H1d, plus UI layered in

| Stage | Variables | Auditor / API / UI work | Expected effort |
|-------|-----------|-------------------------|----------------|
| **Foundation** | (none — scaffolding) | **Auditor:** data contract, Postgres + Alembic + first migration, config, CLI shell (`seomate audit | inspect | migrate | smoke`), base adapter with retry/rate-limit/cost decorators, orchestrator skeleton, taxonomy loader, cost tracker, logging. <br>**API:** FastAPI scaffold with `/api/audits` endpoint backed by mocked data initially, OpenAPI exposed. <br>**Web:** Next.js scaffold, Tailwind + shadcn/ui, `/audits` page hitting the API, type generation pipeline working. <br>**Infra:** `docker-compose.yml` for Postgres+pgvector. | **~1 week** |
| **H1a — Cheap layer** | ~80 variables: most of P0, most of P1, cheap P2, most of P5, P6 entity coverage | **Auditor:** DataForSEO On-Page, GSC URL Inspection / Sitemaps / Crawl Stats, GBP, Knowledge Graph Search, Wikipedia, Wikidata adapters; ~80 extractors. <br>**API:** capture-list, capture-detail, audit-overview endpoints. <br>**Web:** `/audits/[id]/captures` filterable table, `/audits/[id]/captures/[variableId]` detail page with rules rendering. | 1.5–2 weeks |
| **H1b — Composition layer** | ~80 variables: link graph authority, embeddings, TF-IDF, topic clustering, freshness diffs, pillar architecture detection, cluster definitions | **Auditor:** internal `composition/` modules + Gemini Embedding 2 / OpenAI embeddings adapter; pgvector writes. <br>**Web:** embedding-related captures get a vector visualisation panel; cluster definition gets a topic-cluster visualisation. | 1.5–2 weeks |
| **H1c — LLM evaluation layer** | ~40 variables: originality, quotability, citation density, statistical specificity, expert quotes, first-person authority, original research, FAQ, definitional clarity, comparison structures, sentiment, hallucination resistance, headlines accuracy, E-E-A-T composition | **Auditor:** Anthropic + OpenAI adapters with batched evaluation. <br>**Web:** LLM-evaluation captures show the prompt batch, the structured response, and the rule outcomes side-by-side. | 1 week |
| **H1d — Backlinks + entity ecosystem** | ~30 variables: deep DataForSEO Backlinks, news (NewsAPI / GDELT), Reddit, Stack Exchange, YouTube, podcasts (Listen Notes / Podchaser), training-corpus checks (Common Crawl, C4), Wikipedia article quality deep audit, Perplexity citation tracking, cross-assistant tracking | **Auditor:** DataForSEO Backlinks, NewsAPI, GDELT, Reddit API, Stack Exchange API, YouTube Data API, Listen Notes / Podchaser, Common Crawl Index, Perplexity API, multi-LLM cross-assistant tracking. <br>**Web:** AI Overview / Perplexity citation captures get a "where the brand appeared" visualisation. | 1 week |
| **Hardening + UI polish** | Live smoke against www.pixelettetech.com, fix Step 5 verification flags, retrofit anything `unmeasurable` back into taxonomy as a revision | **Auditor:** end-to-end smoke, fix verification flags. <br>**API:** auth/CORS hardening, error response polish. <br>**Web:** compare-audits diff page, empty-state handling, filter UX polish, keyboard nav. | 1–1.5 weeks |

**Total H1: ~7–9 weeks of focused build for one developer.**

Foundation grew from 2–3 days to ~1 week because of the three-layer scaffold (Postgres + Alembic + FastAPI + Next.js) instead of single-Python-app. After Foundation, every subsequent stage delivers a working partial audit visible in the UI; UI work happens in parallel with adapter/extractor work since the data shape is fixed by the contract from day one.

After H1a we already see ~80 captures rendered in the UI. After H1b the structural picture is largely complete. After H1c qualitative evaluation lands. H1d closes the long tail. Hardening makes it presentable.

## 17. Decisions settled (Draft 2)

These were settled in the architecture review session:

| # | Decision | Settled value | Notes |
|---|----------|--------------|-------|
| 1 | **Storage backend** | **Postgres 16 + pgvector** | Same stack as 2Connect; pgvector for embedding queries; Alembic for migrations. |
| 2 | Async runtime | `asyncio` (stdlib) | — |
| 3 | HTTP client | `httpx` | — |
| 4 | Schema validation | `pydantic v2` | — |
| 5 | Taxonomy access | **Parse `o1-taxonomy.md` into structured catalog at audit start** | Single source of truth; no drift from hand-maintained registry. |
| 6 | Append-only ledger | **Yes, no retention policy at H1** | Disk usage trivial at single-site scale. Add retention if and when needed. |
| 7 | Per-audit log file | Yes (JSON, structlog) | — |
| 8 | LLM adapter abstraction | Single `LLMAdapter` interface | Swap Claude / GPT / Gemini behind it. |
| 9 | Cost cap default | £5 per audit | Configurable. |
| 10 | Python version | 3.11+ | — |
| 11 | Repo structure | **Monorepo with three sub-projects: `auditor/`, `api/`, `web/`** | Schema owned by `auditor/` via Alembic; `api/` and `web/` import from the auditor. |
| 12 | **UI layer** | **Next.js 14 (App Router) + Tailwind + shadcn/ui, deployed to Vercel** | Read-only inspection UI for H1; richer features deferred to Phase A+. |
| 13 | **API layer** | **FastAPI between Postgres and Next.js** | Decouples DB schema from frontend; auth-ready; OpenAPI for TypeScript generation. |
| 14 | Pilot site | www.pixelettetech.com | Owner access available for GSC and GBP. |
| 15 | Builder | TBC | Capacity question, not architecture. |
| 16 | **Externally-observable design** | **Constitutional** | Auditor never requires access to client analytics tooling (GA4, GTM, Pixel, etc.). Owner-granted GSC/GBP have documented fall-back paths. |
| 17 | Embedding model | Gemini Embedding 2 (768-dim) | Matches 2Connect; `VECTOR(768)` in Postgres. |

## 18. What this architecture commits to

- The Site Auditor is **deterministic** at every layer except the LLM-evaluation adapter calls in H1c. The orchestrator does not run on LLM judgment.
- Every variable produces a **uniform, structured record**. Downstream layers do not have to know per-variable quirks.
- **Failure is data**, not an exception. `unmeasurable`, `error`, `partial` are first-class outcomes that drive taxonomy revisions and adapter improvements.
- **Append-only history** is preserved from day one — Phase B+ attribution becomes possible without re-architecture.
- **Cost is a first-class signal** — capped per audit, attributed per variable, summarisable per adapter.
- Build is **staged H1a → H1d**, each stage delivering a working (partial) audit.

## 19. What this architecture does NOT commit to

- No agent framework. No LLM-driven orchestration. No Temporal. (All deferred to Phase B/C.)
- No batching analyser layer. (That's Phase A's concern, not H1's. H1 captures and stores; Phase A reads and analyses.)
- No multi-site. Single-site dogfood is the entire scope.
- No automated remediation. Captures only.
- No ranking / scoring. Captures only.
- No auth, no multi-tenancy, no public deployment of the auditor or API. UI deploys to Vercel; the auditor and API stay local for H1.
- No dependency on client-owned analytics tooling. Constitutional, see §3.1.

---

*Draft 2 — May 2026. Settled UI stack (Next.js + Vercel), API layer (FastAPI), database (Postgres + pgvector), and externally-observable design property.*
