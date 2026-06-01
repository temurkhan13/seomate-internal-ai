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

## Scope / status

This is the **handoff + planning** half of Phase 2 (built 2026-06-01): the plan
is produced and routed. The fully-automated executor loop (a session that reads a
work order, makes the change, re-audits, and confirms , unattended) is the next
build on top of this. The manual P1-20 canonical fix (vault [[May-31]]) is the
worked precedent for that loop.
