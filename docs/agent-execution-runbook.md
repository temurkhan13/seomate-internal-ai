# Agent execution runbook: how a Claude session FIXES what the audit found

The diagnostic loop (see `agent-audit-runbook.md`) tells you *what* is wrong.
This is the **Phase 2 execution loop**: turn a completed audit's failures into
fixes, verify each one re-audits clean, and write the result back.

```
seomate plan-fixes <audit-id>  ─►  fix-plan.json  ─►  [ session/human fixes each work order ]  ─►  re-gather + re-evaluate that variable  ─►  seomate ingest  ─►  dashboard shows it flipped to passed
```

## Step 1 — Get the plan

```bash
seomate plan-fixes <audit-id> --out fix-plan.json
```

This reads the audit's **failed + partial** captures, joins each with its
**remediation spec** (`seomate/agent/remediation.py`), and emits prioritised
work orders. Each work order carries:

- `fix_class` , **who can action it**: `session` (a Claude session alone),
  `owner` (needs an account owner, e.g. GBP), `human` (editorial/judgment),
  `offsite` (PR/outreach), `budget` (needs spend).
- `fix_type` , schema / template / content / internal_links / config / media /
  metadata / offsite.
- `target` , where the change is made (repo file, CMS field, sitemap, robots, GBP).
- `concrete_change` , what to do, specifically.
- `required_inputs` , the access/assets the fix needs.
- `verify` , the exact re-check that proves it worked.
- `automatable`, `risk`, `depends_on`, `effort`.

The plan groups by `fix_class` and lists `session_automatable` first. It also
lists `needs_remediation_authoring` , variables with no authored spec yet (they
get a routable fallback; author a real spec to improve the plan).

## Step 2 — Action the work orders

Start with the `session`/`automatable` orders (cheap, high-leverage, low risk).
Respect `depends_on` (e.g. fix P2-28 orphans before P1-24 inbound quality).

**Two disciplines, both already learned on this project:**
- **Don't fix working things.** Only act on a real `failed`/`partial` capture
  with evidence. Never "improve" a `passed` variable.
- **A fix is done when it re-audits clean, not when the edit compiles.** This
  mirrors the diagnostic-side "verify on the live dashboard" rule.

For `human`/`owner`/`budget`/`offsite` orders the session does not action them
directly , it produces the work order for the right person (a copywriter for
P6-03 citation density, the GBP owner for P5-22 posts, a budget decision for the
P3 backlinks campaign).

## Step 3 — Verify each fix

After making a change, re-run the diagnostic for **just that variable** and
confirm the status flipped:

```bash
seomate gather --domain <site> --out audit-cache   # refresh the cache (or just the affected source)
# re-evaluate the fixed variable(s) -> a new ingest doc
seomate ingest --file reaudit.json
```

The new audit shows the variable as `passed` on the dashboard. The `verify`
field on each work order is the explicit success criterion , loop until it's met.

## What's session-automatable vs not (from the pixelette audit)

`plan-fixes` on the 2026-06-01 pixelette audit routed 65 actionable findings as
**33 session / 7 owner / 25 human**, with **13 fully automatable now** (full
authored specs): titles/meta uniqueness (P1-01/02/06), schema (P1-21/42, P6-09/19),
sitemap priority (P2-42), internal-linking the 37 orphans (P2-28/P1-24), image
formats (P2-31), llms.txt + IndexNow (P6-18/P2-36).

The human/owner/budget ones (AI-Overview citations P6-25, reviews P5, original
research P4-11, backlinks P3) are real work orders for the right owner , not
things a session fabricates a fix for.

## Authoring more remediation specs

`remediation.py` covers the automatable wins + common human/budget cases. Any
variable without a spec gets a generic pillar-routed fallback so it's never
dropped, but it reads "needs manual triage". To improve coverage, add a
`RemediationSpec` for that variable (it's a single dataclass entry). This is the
highest-leverage way to make the execution side more turnkey over time.

## Step 2a — Generate fix artifacts (`seomate apply-fixes`)

```bash
seomate apply-fixes <audit-id> --cache audit-cache --out apply-manifest.json
```

For each **session-automatable** work order, the executor builds the **real fix
artifact** from the gather cache , deterministically, no fabrication:

| Variable | Artifact generated |
|---|---|
| P6-18 | the actual `llms.txt` body (from crawl + entity description) |
| P2-42 | the per-URL sitemap `<priority>` map (home 1.0 / service 0.8 / blog 0.5 / utility 0.3) |
| P6-19 | Organization JSON-LD with the real NAP (from GBP/KG) |
| P1-21 / P1-42 | Article + Person JSON-LD template + the list of posts that need it |
| P2-28 / P1-24 | the orphan internal-link plan (which core page links to each of the orphans) |

Each artifact carries its `verify` criterion. Manual work orders
(human/owner/budget) are routed onward with their spec, not given a fake fix.

### Safety model: propose, not push
`apply-fixes` runs in **propose mode** , it generates artifacts for review and
writes the apply manifest, but does **not** write to the target website.
Rationale: SEOMATE is the audit platform; the audited site is a separate
property whose repo/CMS this process does not own, and editing live production
is a gated action. Applying the artifacts needs the site's repo/CMS access +
per-change approval. An `apply` mode would require the caller to pass a target
adapter with write access; it is intentionally not implemented in the platform.

## Step 3 — Apply via a draft PR (gated) + verify

When you have the **audited site's GitHub repo + a write token**, `apply-fixes`
can open a draft PR with the auto-applyable artifacts:

```bash
export GITHUB_TOKEN=...        # write access to the SITE's repo (not SEOMATE's)
# dry run first (default): shows exactly what it would do, opens nothing
seomate apply-fixes <audit-id> --cache audit-cache --target-repo owner/site-repo
# then, to actually open the draft PR:
seomate apply-fixes <audit-id> --cache audit-cache --target-repo owner/site-repo --apply
```

**Layered safety (by design):**
- The token is read from `GITHUB_TOKEN` env, never a CLI arg (stays out of shell history).
- It opens a **draft PR** on a `seomate/fixes-<audit>` branch , never commits to
  the default branch, never auto-merges. A human reviews + merges.
- It defaults to **dry run**; `--apply` is required to actually open the PR.
- Only `file`-kind artifacts (e.g. `llms.txt`) are auto-written. `snippet`/`map`/
  `plan` artifacts and all human/owner/budget work orders go into the PR body as
  a **review checklist** , the adapter does not pretend to integrate
  site-specific templates/build steps.

After the PR is merged, re-audit each affected variable and confirm it flips to
`passed`. The `verify` field on each artifact is the explicit success criterion.

## Scope / status

Built 2026-06-01, the full Phase 2 spine: **plan-fixes** (handoff + routing),
**apply-fixes** propose mode (real artifact generation), and the **gated
GitHub-PR target adapter** (draft PR, dry-run-first). A fixing session with a
site's repo token can now go diagnosis -> draft PR end to end; everything
destructive stays behind review + an explicit `--apply`. CMS-API targets (for
non-repo sites) are the natural next adapter, same gated shape. The manual P1-20
canonical fix (vault [[May-31]]) is the worked precedent.
