"""Build a remediation plan from a completed audit.

``plan_fixes(audit_id)`` reads the audit's failed + partial captures, joins each
with its remediation spec (``remediation.get_spec``), and produces a structured,
prioritised fix plan: per-finding work orders grouped by who can action them
(session / human / budget / owner / offsite), ordered so the cheap automatable
wins surface first and dependencies come before dependents.

This is the diagnostic -> execution handoff. The executor (a fixing session or a
human) consumes the plan; nothing here makes changes.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import UUID

from sqlalchemy import select

from seomate.agent.remediation import FixClass, get_spec, has_spec
from seomate.storage import Audit, Capture, session_scope

# statuses that warrant a fix (passed/n/a/unmeasurable do not)
_ACTIONABLE = {"failed", "partial"}

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
        work_orders.append(
            {
                "variable_id": f["variable_id"],
                "pillar": f["pillar"],
                "diagnostic_status": f["status"],
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

    # group summary
    by_class: dict[str, int] = {}
    for w in work_orders:
        c = w["remediation"]["fix_class"]
        by_class[c] = by_class.get(c, 0) + 1
    automatable_now = [w["variable_id"] for w in work_orders if w["remediation"]["automatable"]]
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
        "needs_remediation_authoring": needs_authoring,
        "work_orders": work_orders,
    }
