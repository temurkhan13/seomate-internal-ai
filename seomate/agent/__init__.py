"""Agent-side audit tooling.

The agent-driven model splits the audit into three parts:

1. ``seomate export-brief`` - exports the taxonomy as the session's instruction
   set (already exists, ``seomate/brief.py``).
2. ``seomate gather`` (this package) - deterministically collects every
   reachable data source for a target domain into a cache directory, so the
   session does not have to hand-roll fetch logic per audit. Auto-derives
   keyword seeds and market from the site itself; degrades gracefully when a
   source is unconfigured (records it ``unavailable`` so dependent variables
   are marked ``unmeasurable``, never guessed).
3. ``seomate ingest`` - validates + writes the session's audit document back
   to the dashboard (already exists, ``seomate/ingest.py``).

The session is still the auditor: it reads the brief, reads the gathered cache,
applies semantic judgment per variable, and emits the ingest document. This
package is the "data plumbing" so that judgment is all the session must supply.
"""
from seomate.agent.execute import build_apply_manifest, execute_work_order
from seomate.agent.gather import GatherResult, gather
from seomate.agent.plan import audit_diff, build_strategy, plan_fixes
from seomate.agent.remediation import RemediationSpec, get_spec
from seomate.agent.target import GitHubPRTarget, TargetResult

__all__ = [
    "gather", "GatherResult", "plan_fixes", "build_strategy", "audit_diff",
    "get_spec", "RemediationSpec", "build_apply_manifest", "execute_work_order",
    "GitHubPRTarget", "TargetResult",
]
