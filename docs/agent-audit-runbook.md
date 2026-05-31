# Agent audit runbook: how a Claude session runs a SEOMATE audit

This is the **Phase 1 diagnostic loop** for the agent-driven model. The
Claude session is the auditor; SEOMATE supplies the understanding (the
taxonomy) and the storage + dashboard. The session reads a *brief*,
performs the 226-variable diagnostic itself using the same public data
sources the old auditor used, and emits one ingest document that
`seomate ingest` writes back so the audit appears on the dashboard.

```
seomate export-brief  ─►  audit-brief.json  ─►  [ Claude session does the audit ]  ─►  audit.json  ─►  seomate ingest  ─►  dashboard
        (taxonomy)                                  (gathers data, evaluates)            (226 captures)      (write-back)
```

The two ends of this loop are code in this repo (`export-brief`, `ingest`);
the middle is the session following the steps below.

## Prerequisites

- `DATABASE_URL` set (the session writes via `seomate ingest`, which needs DB access).
- Google data-source keys available to the session for the variables that need them:
  PageSpeed Insights (`GOOGLE_PSI_API_KEY`), Knowledge Graph (`GOOGLE_KG_API_KEY`).
  Page HTML is fetched directly. (These are the same sources the old auditor used.)

## Step 0 — Get the brief

```bash
seomate export-brief --out audit-brief.json
```

`audit-brief.json` contains, for every active variable:
`variable_id`, `pillar`, `name`, `description`, `evidence_weight`,
`data_sources` (which sources answer it), `step_1_5_rules` (the pass/fail
rules), `hard_dependencies`, and `raw_markdown` (the full taxonomy prose).
Top level carries `taxonomy_version` (copy it into the ingest doc), the
pillar counts, and the union of all `data_sources`.

## Step 1 — Gather inputs (from the same Google sources)

Per the `data_sources` named in the brief:

- **Page HTML / on-page**: fetch the site's pages (homepage + sitemap URLs).
  Titles, canonicals, headings, meta, schema/JSON-LD, OG tags, alt text,
  internal links come from here.
- **PageSpeed Insights**: performance / Core-Web-Vitals variables (P2).
  Run both mobile and desktop; if the mobile leg errors, the affected
  variables are `unmeasurable`, not a desktop-only `pass` (this was a real
  contamination bug, see the vault's reliability notes).
- **Knowledge Graph**: entity / brand presence variables.
- **Owner-only data** (Search Console, Business Profile, backlinks tools):
  not reachable by the session. Variables that depend on these are
  `unmeasurable` with an `errors` note saying which source is missing.
  Do **not** guess them as pass/fail.

## Step 2 — Evaluate each variable

For each variable in the brief:

1. Read its `description` + `raw_markdown` to understand what it measures.
2. Apply its `step_1_5_rules` against the gathered data. Each rule gets a
   `passed: true/false` plus structured `evidence` (counts, failing URLs,
   expected vs actual).
3. Set the capture `status`: `passed` (all rules pass), `failed` (one or
   more fail), `partial`, `not_applicable`, `unmeasurable` (owner data
   missing), or `error` (couldn't evaluate).
4. Carry the variable's `evidence_weight` through to the capture.
5. Record `data_sources_used`.

**Discipline (matches the old auditor's design rules):**
- Judge semantically against the rule text; do not reduce a rule to a
  keyword match.
- Evidence must be real and gathered this run. Never invent a value,
  a count, or a passing result you did not observe. An unobserved variable
  is `unmeasurable` or `error`, never a fabricated `pass`/`fail`.

## Step 3 — Emit the ingest document

Produce one JSON document per `docs/ingest-contract.md`:
top-level `site_domain` + `taxonomy_version` (from the brief) + `captures[]`
(one `CaptureRecord` per variable). Validate before writing:

```bash
seomate ingest --file audit.json --dry-run   # reports all problems, writes nothing
```

## Step 4 — Write it back

```bash
seomate ingest --file audit.json             # writes audit + captures
seomate inspect <printed-audit-id>           # confirm
```

The audit then appears on the dashboard exactly like a natively-run audit.

## Scope

This runbook is **Phase 1 (diagnostic)** only. Phase 2 (execution: fixing
the issues the diagnostic found, the systematized version of the manual
P1-20 canonical fix) is separate and not covered here.

## Why the loop ends in `ingest`, not an API call

The session reaches Postgres directly, so `ingest` reuses the auditor's own
models and keeps `seomate-be` read-only. See `docs/ingest-contract.md`
"Why this path".

## What the brief contains (verified)

`seomate export-brief` against the current taxonomy (`47872f06b860`)
produces **232 active variables**, populated as follows:

- `definition`: 226 / 232
- `data_sources` (Step 4): 226 / 232 (top-level union: 396 distinct source strings)
- `verification` (Step 5), `cost` (Step 6), `citations`, `weight_rationale`: 226 / 232
- `rules` (Step 1.5): 81 / 232 (only variables with an explicit evaluation
  step have rules; the rest are read-a-value variables)
- `hard_dependencies` (Step 7 `depends_on`): 48 / 232

The ~6 variables without `definition`/`data_sources` are edge entries
(headers or sparsely-specified variables); the session treats a variable
with no data source as `unmeasurable` unless it can determine the source
from context.

**Count note:** the taxonomy parses to **232** active variables, while the
cloud audits to date attempted **226** and the project has informally used
"226". The 6-variable gap is unreconciled and worth a one-time check
(whether those 6 are genuinely new variables to audit or parser edge
entries). It does not block the loop; flag it before treating 232 as the
official target.
