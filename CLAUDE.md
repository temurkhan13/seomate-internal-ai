# SEOMATE , session operating guide (read this first)

You are a Claude session operating the SEOMATE platform. This file is the
intro: what SEOMATE is, what you need, and how YOU do the work. Claude Code
auto-loads this, so you have full context from the start.

Also read, when relevant: `HANDOVER.md` (foundation), `ROADMAP.md` (Humza's
vision), `docs/o1-taxonomy.md` (the constitution , before changing any extractor).

---

## The model: platform = tools, sessions = brains + hands + memory

SEOMATE is **not** a fully-autonomous system. It is a set of deterministic
**tools**; **you (the session) provide the intelligence, the execution, and the
record-keeping.** The four layers:

| Layer | What it is | Who does it |
|---|---|---|
| **Auditor** | 224-variable diagnostic of one site | **The tool** (`seomate audit`) , the one thing that is built |
| **Strategist** | Turn findings + goals into a prioritised plan | **You** , read the data, reason, write the playbook |
| **Executor** | Apply the fixes | **You** , edit the repo + open PRs directly (you already have repo access) |
| **Loop** | Re-audit, compare, track what moved | **You** , re-run, diff, and log to the vault |

Do **not** build heavy autonomous infrastructure (git-integration services,
multi-agent paid-LLM strategists, monitoring daemons). Humza's roadmap described
those for a no-human-in-loop product; our plan is **you in the loop**.

---

## Prerequisites (what a session needs to run anything)

1. This repo cloned + a Python venv: `python -m venv .venv` then `pip install -e .`
2. A `.env` at the repo parent with credentials (these gate everything):
   `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, `DATAFORSEO_USE_SANDBOX=false`,
   `GEMINI_API_KEY`, `GOOGLE_PSI_API_KEY`, `GOOGLE_KG_API_KEY`,
   `ANTHROPIC_API_KEY`, `GOOGLE_OAUTH_CLIENT_ID/SECRET/REFRESH_TOKEN` (GSC),
   `DATABASE_URL` (the shared cloud Postgres).
   Without these you fail on e.g. "DATAFORSEO_LOGIN Field required".
3. Cloud + dashboard: results write to the shared DB and show at the live
   dashboard (`seomate-fe.vercel.app`, basic-auth). The BE API is `seomate-be`.

---

## How YOU do each layer

### 1. Audit any site (the tool)
The auditor is fully site-agnostic , it audits whatever domain is in a config.
```
cp configs/pixelette.yml configs/<site>.yml   # edit domain + brand + competitors
seomate audit -c configs/<site>.yml            # runs all 224 extractors -> cloud DB
seomate audit -c configs/<site>.yml --only "P1-01,P2-04"   # fast subset
```
Caveats: heuristics are pixelette-tuned (expect a few debatable verdicts on very
different verticals , walk FAILED vars before trusting). GSC + owner-data vars
only return data for sites the OAuth account owns (see GSC below).

### 2. GSC / owner data for a new site
GSC vars (P2-03 sitemap, P2-04 indexation) work for any site **once the site
owner adds `temurahsan@gmail.com` as a user in their Google Search Console
property.** No code change , the adapter queries `sc-domain:{domain}` and the
shared OAuth token gains access the moment the account is added.

### 3. Strategist (you)
Read the inputs, then write a prioritised playbook:
- audit findings: `GET /api/audits/{id}/captures` (or the DB)
- the fix plan: `GET /api/audits/{id}/plan` (every failure + how to fix + who)
- competitive: `GET /api/competitive?target=...&competitors=...`
- the operator's objective (e.g. "win local pack" vs "win AI Overview")
Synthesise: rank the fixes by impact toward the objective, cite the capture each
recommendation addresses, sequence them. Save the playbook to the vault
(`C:/Users/hp/SEOMateVault/`) and/or as a doc for the operator. The SAME audit
should yield different playbooks for different objectives.

### 4. Executor (you)
You already have repo access , don't build a PR bot. Read the fix plan, and for
each actionable item: edit the target files, run the repo's build/tests, open a
PR (`gh pr create`). The fix plan tells you the concrete change, where, and the
verify step. The 10 "auto-generatable" items have helper generators in
`seomate/agent/execute.py`; the rest you write yourself with judgement.

### 5. Competitive (platform finds them, you interpret)
`run_competitive(target, competitors)` (or the `/api/competitive` endpoint).
If you don't pass competitors, it discovers them by **keyword intelligence**
(the site's ranked keywords -> SERP -> recurring real domains, minus
aggregators) , not the old keyword-overlap that returned giants. Then YOU write
the positioning recommendations from the visibility + keyword-gap data.

### 6. Loop (you + the vault)
A weekly cron re-audits pixelette automatically. Each session: read the latest
audit, compare to the previous one (what regressed / improved), apply fixes,
and **log findings to the vault every time** , the vault is the memory and the
"what actually moved" history. The vault IS the loop's durability.

---

## Hard rules
- The taxonomy (`docs/o1-taxonomy.md`) is the constitution. Prefer an honest
  `unmeasurable` (with a remediation note) over a fake `passed`.
- Push only to `temurkhan13/seomate-internal-{ai,be,fe}` (NOT the old
  `h-chishty/seomate` or `seomate-ai/be/fe`).
- Never commit `.env` or the scratch creds file.
- After meaningful work, update `C:/Users/hp/SEOMateVault/State/changelog.md`.
