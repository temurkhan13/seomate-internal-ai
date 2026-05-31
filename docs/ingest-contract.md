# Ingest contract: agent-produced audits

This is the JSON a **Claude session** emits after performing the 226-variable
diagnostic itself, and that `seomate ingest` writes into the database so it
appears on the dashboard exactly like a natively-run audit.

The session is the auditor; SEOMATE provides the taxonomy (its understanding of
the 226 variables) and the storage + dashboard. This document is the boundary
between the two.

## How to run it

```bash
seomate ingest --file audit.json            # validate + write
seomate ingest --file audit.json --dry-run  # validate only, write nothing
```

`DATABASE_URL` must be set (the session writes directly to Postgres). On success
the command prints the new `audit_id`; confirm with `seomate inspect <audit_id>`
or the dashboard.

## Top-level shape

```json
{
  "site_domain": "pixelettetech.com",
  "taxonomy_version": "47872f06b860",
  "audit_id": "optional-uuid-if-you-need-to-reference-it-first",
  "status": null,
  "total_cost_gbp": 0.0,
  "config_snapshot": { "source": "claude-session", "model": "..." },
  "anomalies": [],
  "consistency_violations": [],
  "captures": [ /* one object per variable, see below */ ]
}
```

| Field | Required | Notes |
|-------|----------|-------|
| `site_domain` | yes | The audited domain. |
| `taxonomy_version` | yes | Freeze the taxonomy version used. Applied to every capture if the capture omits it. |
| `captures` | yes | Non-empty array, one entry per variable (see contract below). Each `variable_id` may appear once. |
| `audit_id` | no | Provide a UUID if the session needs to reference the audit before writing; otherwise one is minted. |
| `status` | no | Force an audit status (`completed`, `completed_with_anomalies`, `partial`, `failed`, `cost_capped`). If omitted it is derived: any `error` capture -> `partial`; else any anomalies -> `completed_with_anomalies`; else `completed`. |
| `total_cost_gbp` | no | Audit cost. Defaults to the sum of capture costs (0 for a no-API session). |
| `config_snapshot` | no | Free-form JSON describing how the session ran. Defaults to `{"source": "claude-session-ingest"}`. |
| `anomalies`, `consistency_violations` | no | JSON arrays, stored verbatim. |

## Per-capture contract

Each entry in `captures` validates against the existing `CaptureRecord`
(`seomate/data_contract.py`). `audit_id`, `taxonomy_version`, and `captured_at`
are filled in for you if omitted; everything else is the session's job.

```json
{
  "variable_id": "P1-20",
  "pillar": "P1",
  "subject_type": "site",
  "subject_id": "pixelettetech.com",
  "status": "failed",
  "value": { "indexable_pages": 58, "pages_missing_canonical": 48 },
  "rules": [
    {
      "rule_id": 1,
      "rule_text": "Canonical tag is present on every indexable page",
      "passed": false,
      "evidence": { "pages_missing_canonical": ["https://.../contact-us"] }
    }
  ],
  "evidence_weight": "Consensus",
  "data_sources_used": ["claude-session.fetch", "google.psi"],
  "cost_incurred_gbp": 0.0,
  "errors": null
}
```

### Field rules (enforced at ingest; invalid documents are rejected whole)

- `variable_id` must match `^P[0-6]-\d{2}$` (e.g. `P1-20`).
- `pillar` must match `^P[0-6]$` and should be the variable's pillar.
- `subject_type` one of: `site`, `url`, `business`, `brand`, `query`.
- `status` one of: `passed`, `failed`, `partial`, `not_applicable`, `error`, `unmeasurable`.
- `evidence_weight` one of: `Consensus`, `Probable`, `Contested`, `Speculative` (per the taxonomy's Evidence Weight Rubric for that variable).
- `value` is free-form JSON; shape follows the variable's documented value schema in `docs/o1-taxonomy.md`.
- `rules` is optional; when present each item is `{rule_id:int>=1, rule_text:str, passed:bool, evidence:object, notes?:str}` mirroring the variable's Step 1.5 rules.
- `errors` should be populated for `error` / `partial` / `unmeasurable` statuses.

## Validation behaviour

`seomate ingest` validates the **entire** document before writing anything and
reports **all** problems at once (missing fields, bad enums, malformed
`variable_id`, duplicate variables). If validation fails, nothing is written, so
a rejected document never leaves a half-formed audit on the dashboard. Use
`--dry-run` to check a document without writing.

## Why this path (not an HTTP endpoint)

The session runs where it can reach Postgres directly (verified: the Supabase
session pooler is reachable, `DATABASE_URL` is configured), so ingest writes
through the same `Audit`/`Capture` models and `session_scope` the orchestrator
uses. This keeps `seomate-be` (the API) cleanly read-only and adds no new
network/auth surface. If a future session must run somewhere without DB
reachability, the same `ingest_audit()` function can be wrapped by a thin
authenticated `POST` on `seomate-be`; the contract above does not change.
