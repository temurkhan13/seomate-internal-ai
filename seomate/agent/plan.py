"""Build a remediation plan from a completed audit.

``plan_fixes(audit_id)`` reads the audit's failed + partial captures, joins each
with its remediation spec (``remediation.get_spec``), and produces a structured,
prioritised fix plan: per-finding work orders grouped by who can action them
(session / human / budget / owner / offsite), ordered so the cheap automatable
wins surface first and dependencies come before dependents.

Findings are gated by evidence weight per the taxonomy's Model B: Speculative
variables are segregated into ``watchlist`` (measured and visible, but not work),
and Contested variables stay actionable but are flagged ``requires_human_signoff``
and held out of ``session_automatable``.

This is the diagnostic -> execution handoff. The executor (a fixing session or a
human) consumes the plan; nothing here makes changes.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import select

from seomate.agent.remediation import FixClass, get_spec, has_spec
from seomate.data_contract import EvidenceWeight
from seomate.storage import Audit, Capture, session_scope

# statuses that warrant a fix (passed/n/a/unmeasurable do not)
_ACTIONABLE = {"failed", "partial"}

# ── Model B: evidence weight gates what we may DO with a finding ──────────────
# Per o1-taxonomy.md "Operational Mapping (Model B)", the weight never gates
# measurement, only operational behaviour:
#
#   Consensus   trusted scoring input, standard approval ladder
#   Probable    same ladder, flagged for outcome tracking
#   Contested   "surfaced as recommendations ... Never auto-approved without
#               human sign-off" , so it stays actionable but can never be
#               auto-shipped
#   Speculative "Surfaces as a hypothesis on a watchlist. Does not drive
#               recommendation generation directly."
#
# The planner previously ignored evidence_weight entirely (it read the column
# and dropped it), so every failing Speculative variable was presented as work
# the evidence does not support. Speculative findings are therefore segregated
# into `watchlist` rather than filtered out: still measured, still visible,
# just not presented as actionable work.
_WATCHLIST_WEIGHTS = {EvidenceWeight.SPECULATIVE.value}
_SIGNOFF_WEIGHTS = {EvidenceWeight.CONTESTED.value}


def is_watchlist_only(evidence_weight: str | None) -> bool:
    """True when the weight forbids the finding driving recommendations.

    Speculative only. An unknown or missing weight is treated as actionable:
    failing open here would silently hide real work, which is the worse error.
    """
    return evidence_weight in _WATCHLIST_WEIGHTS


def requires_human_signoff(evidence_weight: str | None) -> bool:
    """True when the taxonomy forbids auto-approving the fix (Contested)."""
    return evidence_weight in _SIGNOFF_WEIGHTS


def partition_by_evidence_weight(
    orders: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split work orders into ``(actionable, watchlist)`` per Model B.

    Order within each list is preserved, so an already-sorted input stays sorted.
    """
    actionable = [w for w in orders if not is_watchlist_only(w.get("evidence_weight"))]
    watchlist = [w for w in orders if is_watchlist_only(w.get("evidence_weight"))]
    return actionable, watchlist

# ordering: cheapest, highest-leverage first
_CLASS_ORDER = {
    FixClass.SESSION: 0,
    FixClass.OWNER: 1,
    FixClass.HUMAN: 2,
    FixClass.OFFSITE: 3,
    FixClass.BUDGET: 4,
}
_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


async def plan_fixes(audit_id: str | UUID) -> dict[str, Any]:
    """Return a remediation plan dict for the given audit.

    Raises ValueError if the audit isn't found.
    """
    aid = UUID(str(audit_id))
    async with session_scope() as s:
        audit = (await s.execute(select(Audit).where(Audit.audit_id == aid))).scalar_one_or_none()
        if audit is None:
            raise ValueError(f"audit {audit_id} not found")
        rows = (
            await s.execute(
                select(Capture).where(Capture.audit_id == aid, Capture.status.in_(_ACTIONABLE))
            )
        ).scalars().all()
        # snapshot the fields we need before the session closes
        findings = [
            {
                "variable_id": c.variable_id,
                "pillar": c.pillar,
                "status": c.status,
                "evidence_weight": c.evidence_weight,
                "value": c.value,
                "rules": c.rules,
                "errors": c.errors,
            }
            for c in rows
        ]
        site_domain = audit.site_domain
        audit_started = audit.started_at
        # D4: is this the latest audit for the domain? planning against a stale
        # audit is how the wrong-audit branch name slipped in. Surface it so the
        # caller (and the target adapter) can refuse/warn rather than ship blind.
        latest_id = (
            await s.execute(
                select(Audit.audit_id)
                .where(Audit.site_domain == site_domain)
                .order_by(Audit.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        is_latest = str(latest_id) == str(aid)

    work_orders = []
    for f in findings:
        spec = get_spec(f["variable_id"])
        # The SPECIFIC rules that failed. A variable is multi-rule (e.g. P6-19 has
        # Organization + page-type + BreadcrumbList + ...); it fails because some
        # of its rules did. Surfacing exactly which ones stops the executor (and
        # the artifact generators) acting on an already-passing rule , the
        # remediation-spec mismatch where P6-19 got an Organization fix when its
        # only failing rule was BreadcrumbList.
        failing_rules = [
            (r.get("rule_text") or "").strip()
            for r in (f.get("rules") or [])
            if isinstance(r, dict)
            and r.get("passed") is False
            and (r.get("rule_text") or "").strip()
        ]
        # Evidence: prefer the actual failing-rule texts; fall back to errors/value.
        if failing_rules:
            evidence = "; ".join(failing_rules[:3])
        elif f.get("errors"):
            evidence = f["errors"][0]
        elif isinstance(f.get("value"), dict):
            rule = (f["value"] or {})
            evidence = "; ".join(f"{k}={v}" for k, v in list(rule.items())[:3] if not isinstance(v, (list, dict)))
        else:
            evidence = ""
        weight = f["evidence_weight"]
        work_orders.append(
            {
                "variable_id": f["variable_id"],
                "pillar": f["pillar"],
                "diagnostic_status": f["status"],
                "evidence_weight": weight,
                # Contested: reputable sources disagree. Actionable, but the
                # taxonomy forbids auto-approval , a human signs it off and the
                # framing must be honest about what the change actually does.
                "requires_human_signoff": requires_human_signoff(weight),
                "evidence": evidence[:240],
                "failing_rules": failing_rules,
                "has_authored_spec": has_spec(f["variable_id"]),
                "remediation": asdict(spec),
            }
        )

    # sort: fix_class order, then automatable-first, then risk, then dependency-count
    def sort_key(w: dict) -> tuple:
        r = w["remediation"]
        return (
            _CLASS_ORDER.get(FixClass(r["fix_class"]), 9),
            0 if r["automatable"] else 1,
            _RISK_ORDER.get(r["risk"], 1),
            len(r["depends_on"]),
            w["variable_id"],
        )

    work_orders.sort(key=sort_key)

    # Model B split. Speculative findings are measured and stay visible, but the
    # taxonomy forbids them driving recommendation generation, so they move to
    # `watchlist` rather than being dropped: nothing disappears from the audit,
    # it just stops being presented as work the evidence does not support.
    work_orders, watchlist = partition_by_evidence_weight(work_orders)

    # group summary
    by_class: dict[str, int] = {}
    for w in work_orders:
        c = w["remediation"]["fix_class"]
        by_class[c] = by_class.get(c, 0) + 1
    # Contested findings are never auto-approved, so they are held out of the
    # ship-straight-away list even when their spec is technically automatable.
    automatable_now = [
        w["variable_id"]
        for w in work_orders
        if w["remediation"]["automatable"] and not w["requires_human_signoff"]
    ]
    needs_signoff = [w["variable_id"] for w in work_orders if w["requires_human_signoff"]]
    needs_authoring = [w["variable_id"] for w in work_orders if not w["has_authored_spec"]]

    return {
        "audit_id": str(aid),
        "site_domain": site_domain,
        "audit_started_at": str(audit_started) if audit_started else None,
        "is_latest_audit": is_latest,
        "latest_audit_id": str(latest_id) if latest_id else None,
        "actionable_findings": len(work_orders),
        "by_fix_class": by_class,
        "session_automatable": automatable_now,
        "requires_human_signoff": needs_signoff,
        "needs_remediation_authoring": needs_authoring,
        "work_orders": work_orders,
        "watchlist_findings": len(watchlist),
        "watchlist": watchlist,
    }


# ── strategy view ─────────────────────────────────────────────────────────────
# Where the site stands (pillar health) + the fix work sequenced into waves. This
# is the Strategist surface, parallel to the audit (findings) + plan (fixes)
# pages. It is DETERMINISTIC , derived from the stored audit + the remediation
# plan. The objective-driven narrative (re-sequencing for a specific goal, the
# "binding constraint is X" call) stays a session's job, saved to the vault.

_PILLAR_LABEL = {
    "P0": "Relevance & structure",
    "P1": "On-page",
    "P2": "Technical",
    "P3": "Off-page authority",
    "P4": "Content & E-E-A-T",
    "P5": "Local",
    "P6": "AI search / GEO",
}

_WAVE_META = [
    ("quick_wins", "Quick wins (now)",
     "Session-automatable fixes a Claude session can ship straight away."),
    ("session_content", "Content & on-page (session-drafted)",
     "A session drafts these; you review and approve the PR."),
    ("needs_people", "Needs people or owners",
     "Real facts, editorial, or owner-only access (e.g. Google Business Profile)."),
    ("authority", "Authority & spend (ongoing)",
     "Off-site work and paid items: PR, backlinks, entity-building."),
]


def _wave_key(fix_class: str, automatable: bool) -> str:
    if fix_class == "session":
        return "quick_wins" if automatable else "session_content"
    if fix_class in ("human", "owner"):
        return "needs_people"
    return "authority"  # offsite, budget


async def build_strategy(audit_id: str | UUID) -> dict[str, Any]:
    """Strategy view for an audit: pillar health + the fix work in sequenced waves.

    Deterministic and free (no new paid calls): reuses ``plan_fixes`` for the work
    orders and reads the stored captures for pillar health. Keyword targeting
    (ranked keywords + opportunities) is a paid, competitor-dependent surface and
    lives on the competitive page; this view links to it rather than duplicating it.

    Raises ValueError if the audit isn't found (via ``plan_fixes``).
    """
    aid = UUID(str(audit_id))
    plan = await plan_fixes(aid)

    async with session_scope() as s:
        rows = (
            await s.execute(
                select(Capture.pillar, Capture.status).where(Capture.audit_id == aid)
            )
        ).all()

    health: dict[str, dict[str, int]] = {}
    for pillar, status in rows:
        d = health.setdefault(pillar, {})
        d[status] = d.get(status, 0) + 1

    # Per-pillar actionable findings , the "why this score" + "how to fix"
    # drill-down: each failed/partial finding with its evidence + remediation.
    from seomate.taxonomy import Catalog
    cat = Catalog.from_file()
    findings_by_pillar: dict[str, list[dict[str, Any]]] = {}
    for w in plan["work_orders"]:
        r = w["remediation"]
        v = cat.get(w["variable_id"])
        findings_by_pillar.setdefault(w["pillar"], []).append({
            "variable_id": w["variable_id"],
            "name": v.name if v else "",
            "status": w["diagnostic_status"],
            "evidence": w["evidence"],
            "fix_class": r["fix_class"],
            "concrete_change": r["concrete_change"],
        })

    positioning = []
    for p in sorted(_PILLAR_LABEL):
        d = health.get(p, {})
        passed, failed, partial = d.get("passed", 0), d.get("failed", 0), d.get("partial", 0)
        # "unmeasured" = everything with no pass/fail bar (unmeasurable, not-applicable,
        # error). Surfaced so a health % over a tiny graded sample (e.g. P3 backlinks,
        # 1 graded + 34 unmeasured without the subscription) is not misread as "broken".
        unmeasured = d.get("unmeasurable", 0) + d.get("not_applicable", 0) + d.get("error", 0)
        graded = passed + failed + partial
        positioning.append({
            "pillar": p,
            "label": _PILLAR_LABEL[p],
            "passed": passed,
            "failed": failed,
            "partial": partial,
            "graded": graded,
            "unmeasured": unmeasured,
            "health_pct": round(100 * passed / graded) if graded else None,
            "findings": findings_by_pillar.get(p, []),
        })

    buckets: dict[str, list[dict[str, Any]]] = {k: [] for k, _, _ in _WAVE_META}
    for w in plan["work_orders"]:
        r = w["remediation"]
        buckets[_wave_key(r["fix_class"], r["automatable"])].append({
            "variable_id": w["variable_id"],
            "pillar": w["pillar"],
            "fix_class": r["fix_class"],
            "concrete_change": r["concrete_change"],
        })
    waves = [
        {"key": k, "title": t, "blurb": b, "count": len(buckets[k]), "items": buckets[k]}
        for k, t, b in _WAVE_META
    ]

    return {
        "audit_id": str(aid),
        "site_domain": plan["site_domain"],
        "audit_started_at": plan["audit_started_at"],
        "is_latest_audit": plan["is_latest_audit"],
        "actionable_findings": plan["actionable_findings"],
        "by_fix_class": plan["by_fix_class"],
        # Speculative findings never enter the waves (they are not work), but the
        # count is surfaced so the strategy view does not look like it lost them.
        "watchlist_findings": plan["watchlist_findings"],
        "positioning": positioning,
        "waves": waves,
    }


async def audit_diff(site_domain: str) -> dict[str, Any] | None:
    """Compare the latest two audits for a domain , the Loop's "what moved".

    Returns per-pillar health deltas + the variables that newly passed or newly
    failed since the previous audit. Returns None when the domain has fewer than
    two audits. Free (DB reads only). Robust to a taxonomy-version change between
    the two audits: variables present in only one audit are simply not counted as
    a pass/fail transition.
    """
    from datetime import timedelta

    from seomate.taxonomy import Catalog

    # Skip same-session re-runs: the "previous" audit should be a real prior state,
    # not a re-run a few hours earlier (whose deltas are LLM-judgment variance, not
    # real change). Pick the most recent audit at least MIN_GAP older than the latest;
    # if none exists, fall back to the immediate previous and flag it as a re-run.
    MIN_GAP = timedelta(hours=12)

    async with session_scope() as s:
        rows = (
            await s.execute(
                select(Audit.audit_id, Audit.started_at)
                .where(Audit.site_domain == site_domain)
                .order_by(Audit.started_at.desc())
                .limit(12)
            )
        ).all()
        if len(rows) < 2:
            return None
        cur_id, cur_at = rows[0]
        prev_row = next(
            (r for r in rows[1:] if cur_at and r[1] and (cur_at - r[1]) >= MIN_GAP),
            None,
        )
        rerun_warning = prev_row is None
        if prev_row is None:
            prev_row = rows[1]
        prev_id, prev_at = prev_row

        async def _statuses(aid: UUID) -> dict[str, tuple[str, str]]:
            r = (
                await s.execute(
                    select(Capture.variable_id, Capture.pillar, Capture.status).where(
                        Capture.audit_id == aid
                    )
                )
            ).all()
            return {vid: (pillar, status) for vid, pillar, status in r}

        cur = await _statuses(cur_id)
        prev = await _statuses(prev_id)

    cat = Catalog.from_file()

    def _name(vid: str) -> str:
        v = cat.get(vid)
        return v.name if v else ""

    def _pillar_health(m: dict[str, tuple[str, str]]) -> dict[str, dict[str, int]]:
        h: dict[str, dict[str, int]] = {}
        for _vid, (pillar, status) in m.items():
            d = h.setdefault(pillar, {"passed": 0, "graded": 0})
            if status in ("passed", "failed", "partial"):
                d["graded"] += 1
                if status == "passed":
                    d["passed"] += 1
        return h

    ph_cur, ph_prev = _pillar_health(cur), _pillar_health(prev)
    pillars = []
    for p in sorted(_PILLAR_LABEL):
        c = ph_cur.get(p, {"passed": 0, "graded": 0})
        pv = ph_prev.get(p, {"passed": 0, "graded": 0})
        cur_pct = round(100 * c["passed"] / c["graded"]) if c["graded"] else None
        prev_pct = round(100 * pv["passed"] / pv["graded"]) if pv["graded"] else None
        delta = (
            cur_pct - prev_pct
            if (cur_pct is not None and prev_pct is not None)
            else None
        )
        # Suppress the delta when either side has too small a graded base: the % is
        # then dominated by a couple of vars, so a "swing" (e.g. P3 backlinks going
        # 58% -> 0% as the sub lapsed) is a measurability artefact, not real change.
        # Variable-level newly-passed/failed below stays accurate regardless.
        if delta is not None and min(c["graded"], pv["graded"]) < 3:
            delta = None
        pillars.append({
            "pillar": p,
            "label": _PILLAR_LABEL[p],
            "prev_pct": prev_pct,
            "cur_pct": cur_pct,
            "delta": delta,
        })

    newly_passed, newly_failed = [], []
    for vid, (pillar, status) in cur.items():
        prev_status = prev.get(vid, (None, None))[1]
        if prev_status in ("failed", "partial") and status == "passed":
            newly_passed.append({"variable_id": vid, "name": _name(vid), "pillar": pillar})
        elif prev_status == "passed" and status in ("failed", "partial"):
            newly_failed.append({"variable_id": vid, "name": _name(vid), "pillar": pillar})

    return {
        "has_diff": True,
        "rerun_warning": rerun_warning,
        "current_started_at": str(cur_at) if cur_at else None,
        "previous_started_at": str(prev_at) if prev_at else None,
        "pillars": pillars,
        "newly_passed": sorted(newly_passed, key=lambda x: x["variable_id"]),
        "newly_failed": sorted(newly_failed, key=lambda x: x["variable_id"]),
    }
