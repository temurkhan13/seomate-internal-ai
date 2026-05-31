# SEOMATE — Roadmap & Future Phases

**Author:** Humza Chishty
**Companion to:** `HANDOVER.md`
**Written:** 2026-05-15

This document picks up where `HANDOVER.md` ends. It describes the full SEOMATE vision beyond the Phase 1 Auditor that we've shipped, and gives whoever picks the project up an honest map of:

- What the complete system looks like once it's done
- The three phases (Auditor → Strategist → Executor) and how they connect
- What each phase needs to be built, with effort estimates
- The trust progression — from "read-only audit" to "autonomous improvement loop"
- The open design questions that need decisions *before* serious building starts
- The risks, and which ones must be solved before crossing each trust boundary

Read `HANDOVER.md` first — it documents the foundation everything below is built on.

---

## Table of contents

1. [The complete vision in one paragraph](#1-the-complete-vision)
2. [Day-in-the-life — what SEOMATE feels like at full vision](#1b-day-in-the-life)
3. [The three phases](#2-the-three-phases)
4. [Phase 2 — The Strategist](#3-phase-2--the-strategist)
5. [Phase 3 — The Executor](#4-phase-3--the-executor)
6. [Orchestration across phases](#5-orchestration-across-phases)
7. [Trust progression — L0 to L4](#6-trust-progression)
8. [The continuous-loop monitoring layer](#6b-the-continuous-loop-monitoring-layer)
9. [The taxonomy as a living asset](#6c-the-taxonomy-as-a-living-asset)
10. [The data flywheel — why SEOMATE gets better as it's used](#6d-the-data-flywheel)
11. [Market positioning & moat](#6e-market-positioning--moat)
12. [Pricing & business model sketch](#6f-pricing--business-model-sketch)
13. [Honest engineering scope & sequencing](#7-honest-engineering-scope)
14. [Open design questions](#8-open-design-questions)
15. [Risks specific to Phase 2 and Phase 3](#9-risks)
16. [What I would build first](#10-what-i-would-build-first)

---

## 1. The complete vision

SEOMATE in its full form is a **closed-loop SEO + GEO improvement system**: a website goes in, comes out audited, has a prioritised strategy generated against the operator's objectives, has the safe-class changes applied automatically (with PRs proposed for the rest), gets re-audited after deployment, and the loop continues. The operator stays in command of what gets approved at each trust level; SEOMATE handles the heavy lifting between command decisions.

Where industry tools today (Ahrefs, Semrush, BrightLocal, Yoast) end at *measurement* — they tell you what's wrong but leave the planning, prioritisation, and execution entirely to a human — SEOMATE closes the loop. The auditor is the diagnostic. The strategist is the planner. The executor is the doer. Together they form the only product I'm aware of where a site can be measurably improved by software with the operator's role reduced to *approval, not authorship*.

The current state (the Phase 1 Auditor) is the **measurement floor everything else stands on**. If the audit is wrong, the strategy is wrong; if the strategy is wrong, the execution is dangerous. That's why so much of the recent work has been on reliability infrastructure (the completeness gate, the consistency rules, the snapshot regression tests).

---

---

## 1b. Day-in-the-life

To make the vision concrete, here's what an operator's week with SEOMATE looks like at L3 trust (the realistic long-term state):

**Monday morning:** the operator opens the SEOMATE dashboard. Three of their managed sites finished their scheduled weekly audits over the weekend.

- **Site A (pixelettetech.com style — a services agency):** audit pass rate is 64%, up from 58% last week. The Strategist's previous playbook had 12 actions; the Executor auto-merged 5 (alt-text, schema, meta-tag updates) over the week. CI passed on all 5. Post-deploy audit confirmed each change moved its underlying capture from FAILED → PASSED. Remaining 7 actions are awaiting human review (content production, internal-link restructure, disavow-file upload).

- **Site B (an e-commerce store):** audit flagged a new completeness anomaly — `html_fetch_under_coverage` at 76%. The dashboard shows the operator: "you should investigate before trusting this week's strategy." Drill-down shows the customer's site started rate-limiting our crawler. Suggested fix: add the SEOMATE user-agent to their robots whitelist. One-click action.

- **Site C (a B2B SaaS publisher):** the Strategist's content module flagged a new keyword cluster that competitors are dominating ("AI customer support automation" — search volume up 340% in the last 90 days). The Executor drafted 3 long-form articles as PRs against the customer's CMS repo. The operator reviews each article, edits voice, approves merge. Articles publish via the customer's normal deploy.

**Wednesday:** the operator gets a Slack alert: site C's post-deploy audit detected a *regression* on canonical tags after the new articles published. The Executor's auto-rollback kicked in within 4 minutes; the issue was a CMS-template bug, not the articles themselves. The operator reads the alert, confirms the rollback was correct, files a ticket with the customer's dev team to fix the template.

**Friday:** weekly review. The operator opens SEOMATE's executive report for each managed site. The report shows: how many actions completed this week, what audit metrics moved, what's queued for next week. Customer A's CMO gets the report forwarded; she pings the operator to discuss prioritising the disavow upload (still requires her sign-off because it touches Google Search Console).

This is the **steady state**: the operator's job becomes high-leverage supervision and strategic judgement, not manual implementation. SEOMATE is the muscle; the operator is the brain and the safety conscience.

**What it doesn't look like:** SEOMATE is *not* a fully autonomous "set it and forget it" system. The operator stays in the loop for content judgements, brand-voice approvals, customer communication, and any change above the L3 safe-class. The product hypothesis is that SEOMATE removes the *toil* of SEO operations, not the *judgement*.

---

## 2. The three phases

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│   Phase 1 — AUDITOR              ★ DONE                             │
│   ──────────────────                                                │
│   Input:  site URL + brand + (optional) competitors                 │
│   Does:   measures the site against 226 taxonomy variables          │
│   Output: 226 captures (passed/failed/partial/unmeasurable) +       │
│           rule evidence + value JSON per variable                   │
│                                                                     │
│                            ▼                                        │
│                                                                     │
│   Phase 2 — STRATEGIST           ☐ NOT STARTED                      │
│   ───────────────────                                               │
│   Input:  audit captures + user objectives + (optional) competitors │
│   Does:   keyword research, competitor analysis, off-page plan,     │
│           technical fix plan, content strategy, GEO strategy        │
│   Output: a prioritised playbook citing specific audit captures     │
│                                                                     │
│                            ▼                                        │
│                                                                     │
│   Phase 3 — EXECUTOR             ☐ NOT STARTED                      │
│   ──────────────────                                                │
│   Input:  the playbook + (optional) repo access                     │
│   Does:   drafts code/content changes as PRs                        │
│           (later: auto-merges safe changes; later still: deploys)   │
│   Output: PRs against the customer's repo + deploy artefacts        │
│                                                                     │
│                            ▼                                        │
│                                                                     │
│   ┌──── loop ───┐                                                   │
│   Phase 1 again, validating that the changes moved the needle.     │
│   └─────────────┘                                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

The phases handshake through a shared Postgres database (the same `audits` and `captures` tables that already exist), with two new tables to be added — `strategies` and `executions` — each linking back to the audit that produced them.

---

## 3. Phase 2 — The Strategist

### 3.1 What the Strategist does

The Strategist consumes a completed audit and the operator's objectives, performs deeper research the audit alone doesn't do, and produces a prioritised playbook.

**Concretely, six sub-modules:**

| Sub-module | Input | Output |
|---|---|---|
| **Keyword research** | Audit's ranked keywords + objectives | Expanded keyword universe (100s → 1000s), each tagged with search volume, difficulty, intent, opportunity score |
| **Competitor analysis** | User-supplied competitor list + SERP overlap | Real competitor identification (not the audit's circular discovery), gap analysis, positioning recommendations |
| **Off-page plan** | Audit's P3 captures + competitor backlinks | Disavow recommendations (extends audit's P3-29), backlink-acquisition target list, PR pitches, link-reclamation opportunities |
| **Technical fix plan** | Audit's P1/P2 captures | Prioritised technical changes with per-change effort estimate, expected impact, code locations, dependencies |
| **Content strategy** | Audit's P4 captures + keyword research | Content gap analysis, topical clustering, editorial calendar with per-piece briefs |
| **GEO / AI strategy** | Audit's P6 captures + AI Overview presence | Specific levers for Wikipedia presence, citation diversity, AI-corpora signals |

### 3.2 Architecture: modular agents, not one big LLM call

A naive implementation would send the entire audit (226 captures) plus the objectives to a single LLM call and ask "give me the strategy." This fails for three reasons:

1. **Context window exhaustion** — 226 captures, even compressed, blow out the context window for most LLMs once you add the value JSON
2. **Hallucinated citations** — the LLM will invent references to captures that don't exist or misattribute the evidence
3. **Single point of failure** — one fragile prompt holds everything; if the LLM has a bad day, the entire strategy is bad

The right pattern is **modular agents with structured I/O**:

- Each sub-module above is a Python function that:
  - Takes `(audit_id, objectives)` as input
  - Pulls only the captures it needs from Postgres (e.g. keyword module pulls P0-01, P0-06, P1-35; technical module pulls P1 + P2)
  - Calls external APIs as needed (DataForSEO Labs for keyword expansion, SERP API for competitor SERPs)
  - Makes one or two narrowly-scoped LLM calls with structured output
  - Returns a typed result with explicit citations back to capture IDs
- A **supervisor LLM call** synthesises the module outputs into a single ranked playbook
- The supervisor is the *only* call that sees all the data, and even it sees module-summarised data, not raw captures

This mirrors the constitutional taxonomy approach: the audit's per-extractor pattern (each variable is its own function with its own data sources) carries forward into Phase 2's per-module pattern. Don't break the pattern.

### 3.3 Inputs

| Input | Source | Notes |
|---|---|---|
| Audit captures (226) | `captures` table | Already exists |
| User objectives | New `audit_objectives` field on `audits` | Free-text → LLM classification into structured "intents" as a first step |
| User-supplied competitors | `audits.config_snapshot` already has `competitors` array | Currently unused; the Strategist consumes it |
| Site context | Inferred from audit + structured questionnaire | Industry, scale, target market, technical stack |
| GBP / GSC data (optional) | Pending OAuth integrations | If available, unlocks better competitor + technical analysis |

### 3.4 Outputs

A **prioritised playbook** with this structure per action:

```yaml
action_id: A001
category: technical_fix  # or off_page, content, geo, keyword
priority: 1  # P1 highest
title: "Add server-side canonical tags to 48 marketing pages"
description: "..."
effort_estimate_hours: 4
expected_impact: high     # or medium, low
expected_impact_rationale: "..."
evidence:
  - capture_id: <P1-20 audit capture>
  - capture_id: <P3-31 audit capture>
target_files:
  - app/clutch/page.tsx
  - app/dedicated-team-services/page.tsx
  - ...
success_metric: "P1-20 status PASSED on next audit"
trust_class: L3_safe  # auto-mergeable by Phase 3
```

The playbook lives in a new `strategies` table linked to the audit. The UI renders it as a Kanban-style backlog grouped by priority and category.

### 3.5 External APIs the Strategist needs

| Already wired (Phase 1) | New for Phase 2 |
|---|---|
| DataForSEO Labs | Optional: Ahrefs / Semrush cross-validation (paid) |
| SERP API (DataForSEO) | Optional: BuiltWith / Wappalyzer for tech-stack detection |
| Anthropic Claude (Haiku) | Anthropic Claude **Sonnet 4.6** or **Opus 4.7** for synthesis (Haiku is too lightweight) |
| Gemini embeddings | — |

LLM cost goes up materially in Phase 2: ~£0.50–1.50 per audit's strategy generation depending on model choice. Worth the cost — strategy is where the value lives.

### 3.6 What success looks like

A strategy is *good* when:

1. **Every recommendation cites a specific capture** — no floating claims
2. **Priorities reflect the operator's objectives** — the same audit gives different playbooks to a brand that says "fix our local pack" vs "win AI Overview"
3. **Effort estimates are calibrated** — calibration starts wrong; gets better over time as actual implementation feedback closes the loop
4. **Cross-pillar synthesis happens** — e.g. "your decay in P3-25 backlinks combined with no funnel content in P4-08 means link-acquisition without content depth will plateau quickly; sequence content production before outreach"
5. **It survives expert scrutiny** — your SEO exec colleague reads it and says "yes, that's the order I'd attack this in" rather than "this is generic"

---

## 4. Phase 3 — The Executor

### 4.1 What the Executor does

The Executor takes a Strategist playbook and turns the executable actions into actual code/content changes. Different actions need different specialists.

**Specialist agents (each is a Python module + a narrow LLM prompt):**

| Specialist | Handles | Trust class | Effort to build |
|---|---|---|---|
| **Schema injector** | Adds JSON-LD blocks to specific pages | L3 (safe with CI) | ~3 days |
| **Meta-tag editor** | Title / description / canonical / OG tags | L3 (safe with CI) | ~3 days |
| **Image alt-text adder** | Generates + adds alt attributes from page context | L3 (safe with CI) | ~2 days |
| **Internal link adder** | Adds links between topically-related pages | L3 (safe with CI) | ~4 days |
| **Robots / sitemap editor** | Fixes robots.txt + regenerates sitemaps | L2 (PR-only) | ~3 days |
| **Content writer** | Drafts new content pages (blog posts, comparison pages) | L1 / L2 (human-reviewed) | ~2-3 weeks per content type |
| **Disavow file generator** | Produces a Google Disavow file from audit + strategy | L2 (operator uploads) | ~2 days |
| **PR pitch drafter** | Drafts outreach emails for backlink-acquisition targets | L1 (human reviews + sends) | ~4 days |

Each specialist:
1. Receives a single playbook action as input
2. Clones the customer's website repo into a sandbox
3. Makes the change(s)
4. Runs the customer's CI (lint / typecheck / tests) to validate
5. Opens a PR with a description that includes:
   - What changed
   - Why (with link back to the audit capture)
   - Expected impact
   - The audit capture ID the change is addressing
6. (At L3) auto-merges the PR if CI passes and the change-class is safe-listed
7. (At L4) triggers a deploy after staging-validation passes

### 4.2 Architecture

A new `executor/` package alongside `auditor/` and `api/`:

```
executor/
├── seomate_executor/
│   ├── orchestrator.py           Top-level lifecycle: playbook → PRs
│   ├── repo/
│   │   ├── git_integration.py    Clone, branch, commit, push via gh / GitHub API
│   │   └── sandbox.py            Temporary working directories
│   ├── specialists/
│   │   ├── schema_injector.py
│   │   ├── meta_tag_editor.py
│   │   ├── alt_text_adder.py
│   │   ├── internal_link_adder.py
│   │   ├── content_writer.py
│   │   └── ...
│   ├── ci/
│   │   ├── runner.py             Runs the target repo's test commands
│   │   └── safety_checks.py      Cross-cutting safety validation
│   └── trust/
│       └── classifier.py         Decides whether an action is L2 vs L3 vs L4-safe
└── pyproject.toml
```

### 4.3 Customer repo integration

**Required for Phase 3 to be useful:**

- Customer connects their GitHub repo via OAuth (similar to Vercel / Netlify connections)
- SEOMATE gets a bot account with write access to a feature branch namespace (e.g. `seomate/`)
- All PRs land on `seomate/<action_id>-<slug>` branches and are PR'd into the customer's `main` (or chosen default branch)
- Auto-merging requires the customer to opt in per change-class

**Alternative if customer can't / won't connect their repo:**

- SEOMATE generates a downloadable patch file per playbook action
- Customer applies manually
- Loses the auto-merge / auto-deploy progression but keeps the strategy-execution value at L1

### 4.4 The hard part: what's safe to auto-apply?

Code changes range from trivially-safe to potentially catastrophic. A change-class taxonomy is needed before L3+ trust can be granted:

| Change class | Examples | Safety |
|---|---|---|
| **Static metadata** | meta title, meta description, canonical URL, OG tags | Very safe — text-only edits to well-defined fields |
| **Structured data** | JSON-LD schema blocks | Safe — additive, validated by schema tests |
| **Static content additions** | New blog posts, new comparison pages | Safe — net-new pages, no removal |
| **Image attributes** | alt text additions | Safe — additive |
| **Internal link additions** | new `<a href>` to existing pages | Mostly safe — risk of bad UX if poorly placed |
| **Configuration** | robots.txt, sitemap.xml | Medium — wrong robots can de-index the site |
| **Existing-content edits** | Rewriting page copy | Medium — risk of brand-voice drift |
| **Code refactoring** | Renaming components, splitting files | High — easy to break things |
| **Page deletions / redirects** | Removing pages | High — can lose ranking, traffic |
| **Infrastructure changes** | Deploy config, DNS, CDN settings | Highest — never auto-apply |

L3 auto-merge starts with **only the top three rows**. Everything else is L2 (PR proposed, human reviews).

### 4.5 Deployment (L4)

L4 is the moonshot: SEOMATE auto-deploys the changes after staging-validation. This is genuinely dangerous unless:

- The customer has a documented staging environment
- Their CI runs full integration tests
- Their site has a rollback mechanism the executor can trigger if the post-deploy audit detects regression
- The change-class is in the L3 safe-list (no infrastructure, no deletions)

Most customers don't have all four. L4 is a 6+ month investment, not a sprint goal. Phase 3 should ship at L2 and earn L3 over time.

---

## 5. Orchestration across phases

The hand-offs between phases need explicit orchestration:

```
seomate audit <site>                    →  audit run (Phase 1)
seomate plan <audit_id> --objectives    →  strategy run (Phase 2)
seomate execute <strategy_id>           →  executor run (Phase 3)
seomate loop <site> --schedule weekly   →  full automated loop
```

**Orchestration evolution:**

| Stage | Mechanism | When |
|---|---|---|
| Today (Phase 1 only) | CLI invocation; in-process async | Now |
| Near-term | Postgres-backed job queue + worker | When Phase 1 launcher UI ships |
| Mid-term | Per-phase workers (`audit_worker`, `strategy_worker`, `executor_worker`) | When Phase 2 ships |
| Long-term | Temporal workflows | When multi-tenant + scheduled re-audits demand durability |

Memory note on prior project work: `seomate_project.md` already calls out Phase A (batched analyser) → Phase B (multi-agent + RAG-first) → Phase C (Temporal). That ordering still holds.

---

## 6. Trust progression

The trust between SEOMATE and the operator grows in distinct levels. Each level needs prerequisites met before crossing.

| Level | What SEOMATE does | What the operator does | Prerequisites |
|---|---|---|---|
| **L0 (today)** | Audit only — produces 226 captures | Reads audit, implements everything | Reliable auditor (✓) |
| **L1** | Audit + Strategy as human-readable text | Implements based on recommendations | Validated Strategist on 2+ sites |
| **L2** | Audit + Strategy + PR drafts via Executor | Reviews each PR + merges manually | Customer repo connection + CI integration |
| **L3** | L2 + auto-merge low-risk PRs after CI passes | Reviews dashboard, intervenes on alerts | Change-class taxonomy + per-class FP rate < 5% |
| **L4** | L3 + auto-deploy after staging validation | Audit dashboard only | Rollback mechanism + post-deploy audit gate |

**Graduation between levels is earned, not assumed.** Each level needs:

- Empirical data showing the prior level produces correct outputs on real sites
- Per-change-class false-positive rates measured and below a threshold
- Customer opt-in (we never escalate trust unilaterally)
- A rollback / kill-switch — there must always be a way for the operator to stop the loop

---

## 6b. The continuous-loop monitoring layer

Once Phase 3 ships, every site SEOMATE manages becomes a **continuously-monitored, continuously-improving asset**, not a one-shot audit.

The monitoring loop:

```
       ┌──────── weekly schedule ────────┐
       ▼                                  │
   Run audit  ──►  Compare vs prior week's snapshot
       │                  │
       │                  ▼
       │           Did anything regress?
       │                  │
       │           yes ──►  alert operator + auto-rollback if appropriate
       │           no  ──►  continue
       │                  │
       ▼                  ▼
   Generate strategy ────────►  Executor drafts/merges PRs
       │
       ▼
   Wait for deploy ──►  Re-audit ──►  Validate changes moved the right metrics
       │
       └────────── loop ───────────┐
                                   │
                                   ▼
                            (back to top)
```

**What this enables:**

- **Regression detection** — every audit's snapshot is compared against the prior; any unexpected drift (e.g. canonical tags disappear after a CMS migration) gets flagged within hours, not weeks
- **Effect attribution** — when audit metrics move, SEOMATE can correlate the change to specific executor actions, building a per-action "actual impact" history that calibrates future effort/impact estimates
- **Compounding gains** — sites under SEOMATE management get measurably better over time as the loop closes; competitors using point-in-time audits do not
- **Defensible ROI** — at any moment, the operator can show "here are the 47 actions we've completed in the last 90 days, here's the audit-metric movement attributable to each"

**Required infrastructure for the monitoring layer:**

- Scheduled audit runs (Postgres-backed cron or Temporal workflows)
- Per-action impact tracking (link each playbook-action to the captures it expected to move; observe whether they did)
- Alerting (email + Slack at minimum)
- The operator dashboard described in Section 1b

This is genuinely the moat. Anyone can build a one-shot audit tool. Building one that *learns its own calibration over time* via the loop is the structural advantage.

---

## 6c. The taxonomy as a living asset

`docs/o1-taxonomy.md` is not a static document. Google's algorithm evolves; new GEO surfaces (AI Overview, ChatGPT search, Perplexity, Gemini Deep Research) shift the relative importance of variables; leaked features get analysed and added; deprecated signals get removed.

**The taxonomy needs its own lifecycle:**

| Activity | Cadence | Owner |
|---|---|---|
| Algorithm-update tracking (Google announcements + practitioner analyses) | Continuous | Domain expert (SEO researcher / consultant) |
| New variable additions | Quarterly review | Same |
| Evidence-weight reassessment | Quarterly review | Same |
| Removal / consolidation of obsoleted variables | Quarterly review | Same |
| Citation freshness audit (do the linked sources still exist? still say what we cite them as saying?) | Annual | Same |

**This is a role, not an automated process.** Hiring (or contracting) an SEO researcher whose job is to keep the taxonomy current is a Phase 2 prerequisite for product credibility. Without it, the constitutional taxonomy stops being constitutional within 12 months as the SEO landscape moves.

A version-controlled `docs/o1-taxonomy.md` with semantic versioning (the catalog already exposes `taxonomy_version`, currently a git commit hash) lets every audit be comparable to its peers and lets historical audits be re-interpreted against newer taxonomy versions.

**Adjacent assets that also need active maintenance:**

- The spam-phrase library (`p3_backlinks.py:_SPAM_ANCHOR_PATTERNS`)
- The PR-wire / article-directory pattern lists (`p3_backlinks.py:_PRESS_RELEASE_DOMAIN_PATTERNS`)
- The source-type taxonomy for citation diversity (`p6_serp.py:_SOURCE_TYPE_PATTERNS`)
- The infinite-space URL pattern list (`p2_technical.py:_INFINITE_SPACE_PARAM_PATTERNS`)
- The generic-anchor list (`p3_backlinks.py:_GENERIC_ANCHOR_PHRASES`)
- The LLM prompts for the 13 evaluators + the future Strategist sub-modules

All of these are "domain knowledge encoded in code." All need a review cadence; none should be considered done.

---

## 6d. The data flywheel

This is where SEOMATE becomes structurally hard to replicate. Every audit run generates data that, with permission, improves the next audit:

**Per-customer flywheel (no cross-site data needed):**

- Audit history shows which actions actually moved their metrics → effort/impact estimates calibrate per-site over time
- Per-site false-positive rates inform threshold tuning (a site whose blog is heavily-imaged shouldn't fail P1-28 the same way a marketing site does)
- Operator approval/rejection patterns on PRs teach the Executor which change-classes are safe for that customer

**Cross-customer flywheel (with explicit opt-in):**

- Aggregate "what actions are most often approved at L3" tunes the safe-class taxonomy product-wide
- Aggregate "what audit-finding precedes what algorithm-update impact" feeds the taxonomy researcher
- Aggregate "which Strategist sub-modules produced strategies that customers actually executed" informs prompt refinement
- Industry-vertical benchmarking — what does a "good" services-agency audit look like vs a "good" e-commerce audit?

The cross-customer data flywheel is where the moat gets meaningful. After 50 customers across 5 verticals, SEOMATE has empirical data about what works that no competitor can match. After 500, it becomes definitive. **The product is born value-neutral; it accrues value with usage.**

**Privacy / data-handling implications:**

- Audit findings include site URLs, anchor text, third-party domain names — all public-facing data
- The "what worked" calibration data is aggregable without exposing individual customer specifics
- A clear privacy policy on the cross-customer aggregation is a Phase 2 prerequisite — customers opt in explicitly, see what's aggregated, and can opt out

---

## 6e. Market positioning & moat

**What SEOMATE competes with:**

| Category | Examples | What they do | What they don't |
|---|---|---|---|
| **Point-in-time audit tools** | Screaming Frog, Sitebulb, Ahrefs Site Audit | Crawl + report | No strategy synthesis, no execution |
| **All-in-one SEO platforms** | Ahrefs, Semrush, Moz | Audit + keyword research + competitor analysis dashboards | Operator still has to synthesise + execute manually |
| **Managed-service SEO agencies** | Various human-staffed agencies | Full-service implementation | Manual, doesn't scale, inconsistent quality |
| **"AI SEO" startups (2024–2026)** | Many — most short-lived | Auto-generated content + automated outreach | Wrap a single LLM call; produce generic outputs; not grounded |
| **Code-modifying agents** | Devin, SWE-agent, Cursor | General-purpose code modification | Not SEO-specific; no audit foundation |

**SEOMATE's positioning:** the only product where the audit is constitutional, the strategy cites the audit, the execution acts on the strategy, and the loop validates the change. Each layer grounds the next.

**The moat is layered:**

1. **The taxonomy** — 226 variables × multi-rule × citations × evidence weights is months of expert-curated work
2. **The audit infrastructure** — multi-provider data fan-out, completeness gates, consistency rules, snapshot testing
3. **The Strategist's per-module specialisation** — each module is its own narrow LLM-prompting craft
4. **The Executor's change-class safety taxonomy** — categorising every code change by risk + per-customer trust progression
5. **The data flywheel** — calibration improves with usage
6. **The continuous loop** — sites get better over time under management

Any single layer can be replicated. The full stack, with the audit as the foundation and the loop closing on real customer outcomes, is structurally hard.

**Where SEOMATE deliberately does NOT compete:**

- General-purpose content marketing (Ahrefs Content Explorer-style features)
- Backlink monitoring as a standalone product (Ahrefs / Majestic core offering)
- Rank tracking dashboards (the table-stakes commodity layer)

The product is specifically the **automated closed-loop improvement system**, not a stat dashboard. Customers who want the dashboard already have Ahrefs/Semrush; SEOMATE is what they put on top.

---

## 6f. Pricing & business model sketch

This is unvalidated thinking — included so it's not a black box, but expect it to change after market contact.

**Per-audit cost (what we pay):**

| Item | Cost |
|---|---|
| DataForSEO API | £0.20 |
| LLM (Haiku + future Sonnet/Opus for Strategist) | £0.10–1.50 (Phase 1 vs Phase 2) |
| Gemini embeddings | £0.01 |
| Compute (managed Postgres + worker servers) | £0.05 |
| **Total marginal cost** | **£0.36–1.86 per audit** depending on phase |

**Per-customer monthly subscription tiers (proposed):**

| Tier | Audits/month | Trust level | Price/month | Margin per customer |
|---|---|---|---|---|
| **Inspector** (Phase 1 only) | 4 weekly audits + UI access | L0 — read-only | £79 | ~£75 |
| **Strategist** (Phase 1 + 2) | + monthly strategy regeneration | L1 — recommendations only | £249 | ~£235 |
| **Operator** (Phase 1 + 2 + 3) | + Executor PR-only | L2 — PR drafts | £599 | ~£560 |
| **Autopilot** (Phase 1 + 2 + 3) | + auto-merge safe classes | L3 — auto-merge | £1,499 | ~£1,400 |
| **Enterprise** | Multi-site + custom integrations | L4 — auto-deploy | £5,000+ | Custom |

**Critical pricing observations:**

- The Inspector tier is loss-leader territory; its purpose is to bring customers into the funnel
- The real margin lives at Operator and Autopilot tiers, where SEOMATE's value (saved operator hours) is huge
- Multi-site is a natural upsell — managed services agencies buying 10–50 site slots is the obvious channel-partner motion

**Revenue sketch at the natural scale:**

- 100 Operator tier customers @ £600/mo = £720k ARR
- 50 Autopilot tier customers @ £1,500/mo = £900k ARR
- 10 Enterprise customers @ £5k/mo = £600k ARR
- Total: ~£2.2M ARR at 160 paying customers

This is a wedge — not a unicorn-scale business in this form. The unicorn version requires either: enterprise expansion to multi-site portfolio management for agencies (10× ARR per logo), or category expansion beyond SEO (the same closed-loop pattern applied to ads-account optimisation, conversion-rate optimisation, lifecycle email).

That's a 5-year question, not a Phase 2 question. Right answer for now: build the Operator tier well; let the rest reveal itself.

---

## 7. Honest engineering scope

| Workstream | Effort | Prerequisites |
|---|---|---|
| **Phase 1 finalisation** | | |
| ↳ Multi-site audit validation | 1–2 weeks per additional site (3 weeks for a representative 3-site set) | None |
| ↳ Audit launcher UI | ~1 week | Auth on the API |
| ↳ GBP OAuth integration | 1–2 weeks | Google Cloud Console + consent screen |
| **Phase 2 — Strategist** | | |
| ↳ Single-module proof (keyword research) | ~2 weeks | Phase 1 multi-site validation |
| ↳ Multi-module orchestration (4–5 modules) | ~2 weeks | Single-module proof working |
| ↳ Strategy report rendering in UI | ~1 week | Module output schemas finalised |
| ↳ Total Phase 2 to L1 trust | **~5 weeks** | |
| **Phase 3 — Executor (L2)** | | |
| ↳ Git integration + sandbox cloning | ~1 week | None |
| ↳ First specialist (alt-text) | ~1 week | Git integration |
| ↳ 3–4 more specialists (meta, schema, internal links) | ~2 weeks | First specialist pattern proven |
| ↳ Executor supervisor + PR lifecycle UI | ~1 week | Specialists working |
| ↳ Total Phase 3 to L2 trust | **~5 weeks** | |
| **L3 trust (auto-merge safe-class)** | +3 weeks | Per-change-class FP rate measured |
| **L4 trust (auto-deploy)** | +6 weeks + customer infrastructure dependencies | Staging environment + rollback per customer |

**Critical-path total to L2 trust (Strategist + Executor PR-only):** ~3 months of focused engineering, assuming Phase 1 multi-site validation has happened first.

These estimates assume one full-time engineer with the SEOMATE codebase familiar. Less than that is a lot longer.

---

## 8. Open design questions

These need explicit answers before Phase 2 building starts. Don't skip these by accident.

**1. What is "objectives", concretely?**

Options:
- Free-text — easiest UX, hardest to consume
- Structured picker (target keywords, target markets, competitive priorities) — harder UX, easier to consume
- Hybrid — structured fields plus a free-text "anything else"

Recommendation: hybrid, with the structured fields being the *only* thing the Strategist consumes initially. The free-text field gets stored for human reference but doesn't influence strategy generation (yet).

**2. Single-site or multi-tenant?**

Phase 1 is single-tenant by design (the `configs/pixelette.yml` file model). Phase 2 onward almost certainly needs multi-tenant — the strategy and execution surface is per-customer.

Decisions needed:
- Database-per-customer or shared-database-with-customer-id?
- Auth model — username/password? Magic link? Connect via OAuth?
- Billing model — per-audit? Per-month? Per-site?

Recommendation: shared-database-with-customer-id (simplest), magic-link auth (lowest friction), per-audit pricing (~£15-25/audit covering compute + LLM + margin).

**3. Which LLM for synthesis steps?**

| Model | Cost per million tokens | Use case |
|---|---|---|
| Claude Haiku 4.5 | $0.80 in / $4 out | Per-page evaluators (current) |
| Claude Sonnet 4.6 | $3 in / $15 out | Strategy synthesis sub-modules |
| Claude Opus 4.7 | $15 in / $75 out | Top-level Strategist supervisor; high-stakes Executor decisions |

The cost difference between Haiku and Opus is 18×. Use the cheapest model that works for each step. Synthesis steps probably need Sonnet+; per-module narrow tasks can stay on Haiku.

**4. Citation grounding — how do we stop the LLM hallucinating capture references?**

Two patterns:
- **Pre-filter then prompt** — the Python module pulls only the relevant captures, formats them with their IDs, and passes only those into the prompt. The LLM physically cannot cite a capture that wasn't in its prompt.
- **Post-validate** — the LLM produces citations; we validate each one exists in the audit + the cited evidence actually supports the claim.

Recommendation: both. Pre-filter is the primary defence; post-validate is the safety net.

**5. PR target — customer's repo or our fork?**

Options:
- Customer connects their repo directly; PRs go to their main branch
- SEOMATE holds a fork; PRs go to the fork; customer pulls if they want
- Patch file delivery — no Git integration at all

Recommendation: direct connection for L3+ trust customers, patch file fallback for L1/L2 only.

**6. Change-class safety taxonomy — who decides what's "safe"?**

The L3 safe-list (alt-text, meta tags, schema) shouldn't be hard-coded. Per-customer override needed: some customers will be more conservative (only L2), some more aggressive (more classes opted into L3). Needs a settings UI per customer.

**7. Strategy storage model**

Strategies are produced per (audit_id, objectives). Same audit can have different strategies if objectives change. Two-table model: `strategies` (one per generation, links to audit + objectives snapshot) + `playbook_actions` (one row per action within a strategy). UI renders the latest strategy by default but lets the operator switch between past versions.

**8. Continuous re-audit triggers**

After execution, when does the next audit run?
- On every PR merge? — too frequent, expensive
- After a deploy? — ideal, requires deploy-trigger integration
- Scheduled weekly? — simple, may miss changes
- On-demand? — operator triggers

Recommendation: deploy-triggered for L4 customers, weekly-scheduled for L2/L3, on-demand for L1.

---

## 9. Risks

Phase 2 + 3 introduce new risk classes the Phase 1 audit didn't have. Calibrate accordingly.

**Phase 2 — Strategist risks:**

| Risk | Severity | Mitigation |
|---|---|---|
| Hallucinated capture citations | High | Pre-filter pattern (see Q4 above) + post-validate |
| Strategy ignores the operator's objectives | High | Make objectives a top-level input to every module, not just the supervisor |
| Cost per audit balloons | Medium | Tiered LLM model choice; cache module outputs that don't change between audits |
| Strategy quality varies day-to-day | Medium | `temperature=0` on all synthesis calls; inter-rater consistency checks (snapshot Strategist outputs and diff between runs) |
| Recommendations are generic | Medium | Per-customer + per-vertical fine-tuning of prompts over time |
| Strategist depends on auditor quality | High | Phase 2 cannot ship before Phase 1 is validated on multiple sites |

**Phase 3 — Executor risks:**

| Risk | Severity | Mitigation |
|---|---|---|
| Executor pushes broken code | Catastrophic | Mandatory CI gate; per-change-class trust levels; never bypass `--no-verify` |
| Executor edits something it shouldn't | Catastrophic | File-path allowlists per specialist; never touch infrastructure |
| Customer's CI is weak/missing | High | Detect at connect-time; refuse L3 trust if CI doesn't exist |
| Auto-merged change kills traffic | High | Post-deploy audit gate at L4; alert + auto-rollback on regression |
| Brand-voice drift in content-writer outputs | Medium | Brand style guide stored per customer; L1 trust only for content for a long time |
| Customer's tech stack is exotic | Medium | Detect at audit time; fall back to L1 (patch files) when SEOMATE doesn't recognise the stack |

**The unifying meta-risk:** in a closed-loop system, errors compound. A bad audit → bad strategy → bad PR → bad deploy → audit picks up the new (worse) state → cycle continues. The completeness gate + consistency rules built into Phase 1 are the foundation here; Phase 2 + 3 need their own equivalent guard layers.

---

## 10. What I would build first

If I were continuing this project, the next 6 months in order:

1. **Multi-site audit validation (3 weeks).** Run the audit on 3 representative sites — a SaaS product, an e-commerce store, a publisher. For each, manually walk every FAILED capture with an SEO expert and confirm the finding is defensible. Tune heuristic libraries against the false positives discovered. Re-snapshot.

2. **Audit launcher UI (1 week).** Per Section 10 of `HANDOVER.md`. Lets the SEO operator run audits without a developer. Unblocks usage testing.

3. **GBP OAuth integration (2 weeks).** Highest-leverage of the two pending OAuth flows. Unlocks ~5 deferred variables that materially improve audit completeness for any business with a Google Business Profile.

4. **Strategist single-module proof of concept (2 weeks).** Just the **keyword research module**. Takes (audit_id, objectives), produces an expanded keyword universe with intent + opportunity scoring. Validate the structured-output + citation pattern works on real data.

5. **Strategist multi-module + UI (3 weeks).** Add competitor analysis, technical fix plan, content strategy, off-page plan, GEO strategy. Supervisor synthesis. Render in the UI as a prioritised playbook.

6. **Strategist validation (2 weeks).** Run the Strategist on the 3 multi-site validation set. SEO expert grades each strategy. Iterate prompts. Snapshot strategy outputs for regression detection.

7. **Executor L2 trust — first specialists (3 weeks).** Git integration + sandbox + alt-text adder + meta-tag editor + schema injector. Three specialists, PR-only.

8. **Executor expansion (3 weeks).** Internal link adder, robots/sitemap editor, disavow file generator, PR pitch drafter.

**End of month 6:** SEOMATE can take a site URL, audit it, generate a strategy, and propose PRs against the customer's repo. The operator approves everything. That's the **L2 trust state** — the first commercially-defensible product. Everything beyond is graduating to higher trust levels.

**Don't try to parallelise the order above.** Each step depends on the prior one producing reliable outputs. Phase 2 building on a fragile Phase 1 is a waste; Phase 3 building on a fragile Phase 2 is dangerous. The 6-month sequence is the path of least regret.

---

## Closing thought

What we've built (Phase 1) is the diagnostic — and a diagnostic that survives expert scrutiny is rarer than it sounds. Most SEO tools today produce verdicts that don't trace back to documented evidence and don't graduate to honest "unmeasurable" when measurement isn't possible. SEOMATE Phase 1 does both. That's the foundation.

Phase 2 and Phase 3 are the *interesting* product. They're also the ones where most teams over-promise and under-deliver. The pattern of "AI agents that improve your SEO automatically" is being pitched by dozens of startups right now; almost all of them are wrappers around a single LLM call that hallucinate citations and produce generic recommendations. SEOMATE has the chance to be the one that actually works *because* it's built on top of a real audit, not on top of "ask GPT what to do about SEO."

If you take one piece of advice from this roadmap: **don't compromise on the constitutional taxonomy.** Every shortcut that's tempting in Phase 2 and Phase 3 either bypasses the taxonomy or weakens the citation grounding. When in doubt, slow down and choose the more defensible path.

— Humza

Contact: `h.chishty@ymail.com`
