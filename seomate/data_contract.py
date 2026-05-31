"""Data contract for SEOMATE captures.

Every variable extractor produces a CaptureRecord. This module is the
constitutional reference for the shape of that record. Downstream layers
(API, UI, future analyser) consume against this contract; they do not
inspect raw API responses or per-variable special cases.

See docs/site-auditor-architecture.md §5 for the design rationale and
docs/o1-taxonomy.md for the variable definitions.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class CaptureStatus(str, Enum):
    """The outcome of attempting to capture a single variable."""

    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"
    UNMEASURABLE = "unmeasurable"


class EvidenceWeight(str, Enum):
    """Per o1-taxonomy.md Evidence Weight Rubric. Drives Model B treatment."""

    CONSENSUS = "Consensus"
    PROBABLE = "Probable"
    CONTESTED = "Contested"
    SPECULATIVE = "Speculative"


class SubjectType(str, Enum):
    """What the variable is being measured against."""

    SITE = "site"
    URL = "url"
    BUSINESS = "business"
    BRAND = "brand"
    QUERY = "query"


class AuditStatus(str, Enum):
    """Lifecycle state of a single audit run."""

    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_ANOMALIES = "completed_with_anomalies"
    PARTIAL = "partial"
    FAILED = "failed"
    COST_CAPPED = "cost_capped"


class RuleResult(BaseModel):
    """One Step 1.5 evaluation rule's outcome."""

    model_config = ConfigDict(frozen=True)

    rule_id: int = Field(ge=1, description="1-indexed rule number from the variable's Step 1.5")
    rule_text: str = Field(description="Human-readable rule statement")
    passed: bool
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured proof: list of failing URLs, count, expected vs actual, etc.",
    )
    notes: str | None = None


class CaptureRecord(BaseModel):
    """The uniform per-variable contract.

    Every variable in o1-taxonomy.md produces one CaptureRecord per
    (audit, subject) pair. Append-only ledger: never mutated after write.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Identity
    capture_id: UUID = Field(default_factory=uuid4)
    audit_id: UUID
    variable_id: str = Field(
        pattern=r"^P[0-6]-\d{2}$",
        description="Variable identifier from o1-taxonomy.md, e.g. 'P1-01'",
    )
    pillar: str = Field(pattern=r"^P[0-6]$", description="Pillar identifier, e.g. 'P1'")
    captured_at: datetime
    taxonomy_version: str = Field(description="Frozen at audit start; survives later taxonomy revisions")

    # Subject of measurement
    subject_type: SubjectType
    subject_id: str = Field(description="Canonical identifier (URL/domain/place_id/query)")

    # Result
    status: CaptureStatus
    value: Any | None = Field(
        default=None,
        description="Raw measurement; type varies per variable per its documented value schema",
    )
    rules: list[RuleResult] | None = Field(
        default=None,
        description="Per-rule outcomes for variables with Step 1.5 evaluation rules",
    )

    # Methodology metadata (denormalised onto the capture for downstream filterability)
    evidence_weight: EvidenceWeight
    data_sources_used: list[str] = Field(
        default_factory=list,
        description=(
            "Adapter+endpoint identifiers that fired, e.g. "
            "['dataforseo.on_page.instant_pages', 'composition.duplicate_title_aggregation']"
        ),
    )
    cost_incurred_gbp: float = Field(
        default=0.0,
        ge=0.0,
        description="Incremental cost of this single capture",
    )
    staleness_seconds: int | None = Field(
        default=None,
        description="Age of the underlying data when captured (None = real-time)",
    )
    errors: list[str] | None = Field(
        default=None,
        description="Populated for status in {error, partial, unmeasurable}",
    )
    raw_response_ref: str | None = Field(
        default=None,
        description="Path to debug snapshot if retain_raw_responses is enabled",
    )
