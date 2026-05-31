"""Ingest a session-produced audit into the SEOMATE database.

This is the write-back path for the agent-driven audit model: instead of
the Python orchestrator computing captures by calling the Claude API per
variable, a Claude *session* performs the 226-variable diagnostic itself
(using SEOMATE's taxonomy as its understanding) and emits the results as a
single JSON document. This module validates that document against the
existing ``CaptureRecord`` contract and writes one ``audits`` row plus N
``captures`` rows, so the result appears on the dashboard exactly like a
natively-run audit.

It deliberately reuses the auditor's own schema (``Audit`` / ``Capture``),
session management (``session_scope``) and per-variable data contract
(``CaptureRecord``). It does NOT import the orchestrator (which pulls in
all the network adapters); the tiny ORM mapper is duplicated here so the
ingest path has no heavy dependencies.

Contract: see ``docs/ingest-contract.md``.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import update

from seomate.data_contract import AuditStatus, CaptureRecord, CaptureStatus
from seomate.storage import Audit, Capture, session_scope

# Audit-level statuses the DB CHECK constraint accepts (migration 0002).
_ALLOWED_AUDIT_STATUS = {
    "running",
    "completed",
    "completed_with_anomalies",
    "partial",
    "failed",
    "cost_capped",
}


class IngestError(ValueError):
    """Raised when the ingest payload is structurally invalid.

    Carries a list of human-readable problems so the caller (CLI or the
    Claude session) can fix the document and retry, rather than getting a
    half-written audit.
    """

    def __init__(self, problems: list[str]) -> None:
        self.problems = problems
        super().__init__("; ".join(problems))


def _capture_orm_from_record(record: CaptureRecord) -> Capture:
    """Map a validated CaptureRecord to a Capture ORM row.

    Mirrors ``orchestrator._capture_orm_from_record`` exactly; duplicated
    here so ingest does not import the orchestrator (and its adapters).
    """
    return Capture(
        capture_id=record.capture_id,
        audit_id=record.audit_id,
        variable_id=record.variable_id,
        pillar=record.pillar,
        captured_at=record.captured_at,
        taxonomy_version=record.taxonomy_version,
        subject_type=record.subject_type.value,
        subject_id=record.subject_id,
        status=record.status.value,
        value=record.value,
        rules=[r.model_dump() for r in record.rules] if record.rules else None,
        evidence_weight=record.evidence_weight.value,
        data_sources_used=record.data_sources_used,
        cost_incurred_gbp=Decimal(str(record.cost_incurred_gbp)),
        staleness_seconds=record.staleness_seconds,
        errors=record.errors,
        raw_response_ref=record.raw_response_ref,
    )


def _derive_final_status(
    captures: list[CaptureRecord],
    requested: str | None,
    anomalies: list[dict[str, Any]],
) -> AuditStatus:
    """Pick the audit's closing status.

    If the session explicitly set a valid status, honour it. Otherwise
    derive one the same way the orchestrator does: errors downgrade a
    clean run to ``partial``; anomalies promote ``completed`` to
    ``completed_with_anomalies``.
    """
    if requested:
        if requested not in _ALLOWED_AUDIT_STATUS:
            raise IngestError(
                [
                    f"audit status {requested!r} is not one of "
                    f"{sorted(_ALLOWED_AUDIT_STATUS)}"
                ]
            )
        return AuditStatus(requested)

    has_error = any(r.status is CaptureStatus.ERROR for r in captures)
    if has_error:
        return AuditStatus.PARTIAL
    if anomalies:
        return AuditStatus.COMPLETED_WITH_ANOMALIES
    return AuditStatus.COMPLETED


def parse_payload(payload: dict[str, Any]) -> tuple[UUID, dict[str, Any], list[CaptureRecord]]:
    """Validate an ingest payload and return (audit_id, audit_meta, captures).

    Raises ``IngestError`` with all problems collected, so the caller sees
    every issue at once rather than one-at-a-time. Nothing is written to
    the database here.
    """
    problems: list[str] = []

    if not isinstance(payload, dict):
        raise IngestError(["payload must be a JSON object"])

    site_domain = payload.get("site_domain")
    if not site_domain or not isinstance(site_domain, str):
        problems.append("site_domain is required and must be a non-empty string")

    taxonomy_version = payload.get("taxonomy_version")
    if not taxonomy_version or not isinstance(taxonomy_version, str):
        problems.append("taxonomy_version is required and must be a non-empty string")

    raw_captures = payload.get("captures")
    if not isinstance(raw_captures, list) or not raw_captures:
        problems.append("captures is required and must be a non-empty array")
        raw_captures = []

    # One audit_id for the whole run. Accept a caller-provided one (lets the
    # session reference it before the write) or mint a fresh one.
    audit_id_raw = payload.get("audit_id")
    if audit_id_raw is not None:
        try:
            audit_id = UUID(str(audit_id_raw))
        except (ValueError, AttributeError, TypeError):
            problems.append(f"audit_id {audit_id_raw!r} is not a valid UUID")
            audit_id = uuid4()
    else:
        audit_id = uuid4()

    captures: list[CaptureRecord] = []
    seen_variables: set[str] = set()
    for i, raw in enumerate(raw_captures):
        if not isinstance(raw, dict):
            problems.append(f"captures[{i}] must be an object")
            continue
        # Force every capture onto this audit + supply per-record defaults
        # the session need not repeat.
        raw = {**raw}
        raw["audit_id"] = str(audit_id)
        raw.setdefault("taxonomy_version", taxonomy_version)
        raw.setdefault("captured_at", datetime.now(timezone.utc).isoformat())
        try:
            record = CaptureRecord.model_validate(raw)
        except Exception as exc:  # noqa: BLE001 - surface a readable message per row
            vid = raw.get("variable_id", "?")
            problems.append(f"captures[{i}] (variable {vid}): {exc}")
            continue
        if record.variable_id in seen_variables:
            problems.append(
                f"captures[{i}]: duplicate variable_id {record.variable_id} "
                "(each variable may appear once per audit)"
            )
        seen_variables.add(record.variable_id)
        captures.append(record)

    if problems:
        raise IngestError(problems)

    audit_meta = {
        "site_domain": site_domain,
        "taxonomy_version": taxonomy_version,
        "config_snapshot": payload.get("config_snapshot") or {"source": "claude-session-ingest"},
        "status": payload.get("status"),
        "total_cost_gbp": payload.get("total_cost_gbp"),
        "anomalies": payload.get("anomalies") or [],
        "consistency_violations": payload.get("consistency_violations") or [],
        "started_at": payload.get("started_at"),
        "completed_at": payload.get("completed_at"),
    }
    return audit_id, audit_meta, captures


async def ingest_audit(payload: dict[str, Any]) -> UUID:
    """Validate and persist a session-produced audit. Returns the audit_id.

    Writes the full audit atomically per phase, mirroring the orchestrator:
    open the audit row, bulk-insert captures, then close the audit with the
    final status and outcome counts. On any DB error nothing is left
    half-open because each ``session_scope`` block commits or rolls back as
    a unit and the audit row is only marked terminal in the final block.
    """
    audit_id, meta, captures = parse_payload(payload)

    anomalies = meta["anomalies"]
    final_status = _derive_final_status(captures, meta["status"], anomalies)

    # 1. Open the audit row (running).
    async with session_scope() as s:
        s.add(
            Audit(
                audit_id=audit_id,
                site_domain=meta["site_domain"],
                config_snapshot=meta["config_snapshot"],
                taxonomy_version=meta["taxonomy_version"],
                status=AuditStatus.RUNNING.value,
            )
        )

    # 2. Bulk-insert captures.
    async with session_scope() as s:
        for record in captures:
            s.add(_capture_orm_from_record(record))

    # 3. Close the audit with final status + outcome counts.
    counts: Counter[CaptureStatus] = Counter(r.status for r in captures)
    total_cost = meta["total_cost_gbp"]
    if total_cost is None:
        total_cost = sum((r.cost_incurred_gbp for r in captures), 0.0)

    async with session_scope() as s:
        await s.execute(
            update(Audit)
            .where(Audit.audit_id == audit_id)
            .values(
                status=final_status.value,
                completed_at=datetime.now(timezone.utc),
                total_cost_gbp=Decimal(str(total_cost)),
                variables_attempted=len(captures),
                variables_passed=counts[CaptureStatus.PASSED],
                variables_failed=counts[CaptureStatus.FAILED],
                variables_partial=counts[CaptureStatus.PARTIAL],
                variables_errored=counts[CaptureStatus.ERROR],
                variables_unmeasurable=counts[CaptureStatus.UNMEASURABLE],
                anomalies=anomalies,
                consistency_violations=meta["consistency_violations"],
            )
        )

    return audit_id


def load_payload(path: Path) -> dict[str, Any]:
    """Read and JSON-parse an ingest document from disk.

    Uses ``utf-8-sig`` so a leading byte-order mark (common when a file is
    produced by a Windows tool or some editors) is tolerated rather than
    rejected as invalid JSON.
    """
    text = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError([f"{path} is not valid JSON: {exc}"]) from exc
    return data
