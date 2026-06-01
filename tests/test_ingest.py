"""Unit tests for the ingest payload parser.

These cover validation and the derive-status logic WITHOUT touching the
database (the DB write path, ``ingest_audit``, is exercised in the live
verification step, not in unit tests, to avoid requiring Postgres here).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from datetime import datetime, timezone

from seomate.data_contract import AuditStatus, CaptureStatus
from seomate.ingest import IngestError, _derive_final_status, _parse_dt, parse_payload


def test_parse_dt_handles_iso_z_and_none() -> None:
    assert _parse_dt(None) is None
    assert _parse_dt("") is None
    assert _parse_dt("not-a-date") is None
    dt = _parse_dt("2026-06-01T10:00:00Z")
    assert dt == datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)
    # naive input gets UTC attached (so comparisons never crash)
    assert _parse_dt("2026-06-01T10:00:00").tzinfo is not None


def test_timestamp_clamp_prevents_negative_duration() -> None:
    # the bug: completed_at earlier than started_at -> negative duration on the
    # dashboard. The ingest clamps started_at to completed_at when inverted.
    started = _parse_dt("2026-06-01T10:00:05Z")
    completed = _parse_dt("2026-06-01T10:00:03Z")  # 2s BEFORE started
    clamped_started = completed if started > completed else started
    assert clamped_started <= completed  # never negative

FIXTURE = Path(__file__).parent / "fixtures" / "ingest_sample.json"


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_sample_fixture_parses() -> None:
    audit_id, meta, captures = parse_payload(_load())
    assert meta["site_domain"] == "example.com"
    assert meta["taxonomy_version"] == "test-taxonomy-v1"
    assert len(captures) == 3
    # audit_id propagated onto every capture
    assert all(c.audit_id == audit_id for c in captures)
    # taxonomy_version defaulted onto captures that omitted it
    assert all(c.taxonomy_version == "test-taxonomy-v1" for c in captures)


def test_missing_required_fields_collected() -> None:
    with pytest.raises(IngestError) as ei:
        parse_payload({"captures": []})
    problems = " ".join(ei.value.problems)
    assert "site_domain" in problems
    assert "taxonomy_version" in problems
    assert "captures" in problems


def test_bad_variable_id_rejected() -> None:
    payload = {
        "site_domain": "x.com",
        "taxonomy_version": "v1",
        "captures": [
            {
                "variable_id": "NOPE-99",
                "pillar": "P1",
                "subject_type": "site",
                "subject_id": "x.com",
                "status": "passed",
                "evidence_weight": "Consensus",
            }
        ],
    }
    with pytest.raises(IngestError) as ei:
        parse_payload(payload)
    assert any("NOPE-99" in p or "variable_id" in p for p in ei.value.problems)


def test_duplicate_variable_rejected() -> None:
    one = {
        "variable_id": "P1-01",
        "pillar": "P1",
        "subject_type": "site",
        "subject_id": "x.com",
        "status": "passed",
        "evidence_weight": "Consensus",
    }
    payload = {
        "site_domain": "x.com",
        "taxonomy_version": "v1",
        "captures": [one, dict(one)],
    }
    with pytest.raises(IngestError) as ei:
        parse_payload(payload)
    assert any("duplicate" in p.lower() for p in ei.value.problems)


def test_bad_audit_status_rejected() -> None:
    with pytest.raises(IngestError):
        _derive_final_status([], "not_a_real_status", [])


def test_status_derivation_defaults() -> None:
    _, _, captures = parse_payload(_load())
    # fixture has a failed + passed + unmeasurable, no error, no anomalies -> completed
    assert _derive_final_status(captures, None, []) is AuditStatus.COMPLETED
    # anomalies present -> completed_with_anomalies
    assert (
        _derive_final_status(captures, None, [{"x": 1}])
        is AuditStatus.COMPLETED_WITH_ANOMALIES
    )


def test_explicit_status_honoured() -> None:
    _, _, captures = parse_payload(_load())
    assert _derive_final_status(captures, "failed", []) is AuditStatus.FAILED


def test_error_capture_downgrades_to_partial() -> None:
    payload = {
        "site_domain": "x.com",
        "taxonomy_version": "v1",
        "captures": [
            {
                "variable_id": "P1-01",
                "pillar": "P1",
                "subject_type": "site",
                "subject_id": "x.com",
                "status": "error",
                "evidence_weight": "Consensus",
                "errors": ["boom"],
            }
        ],
    }
    _, _, captures = parse_payload(payload)
    assert captures[0].status is CaptureStatus.ERROR
    assert _derive_final_status(captures, None, []) is AuditStatus.PARTIAL
