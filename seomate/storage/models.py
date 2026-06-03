"""SQLAlchemy 2.0 ORM models.

Single source of truth for the SEOMATE database schema. Shared by:

- the auditor (writer) — for inserting Audit / Capture / AdapterCall rows
- the API (reader) — for serving captures to the Next.js UI
- Alembic — for autogenerating future migrations against ``Base.metadata``

Schema matches docs/site-auditor-architecture.md §8 exactly. The first
migration in ``alembic/versions/0001_initial.py`` creates this schema
including pgvector extension and the ivfflat index that SQLAlchemy
cannot express declaratively.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all SEOMATE ORM models."""


class Audit(Base):
    """An audit run on a single site at a single point in time."""

    __tablename__ = "audits"

    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    site_domain: Mapped[str] = mapped_column(String, nullable=False)
    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    taxonomy_version: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    total_cost_gbp: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 4),
        nullable=True,
    )
    variables_attempted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    variables_passed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    variables_failed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    variables_errored: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    variables_partial: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    variables_unmeasurable: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    anomalies: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    consistency_violations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    captures: Mapped[list["Capture"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    adapter_calls: Mapped[list["AdapterCall"]] = relationship(
        back_populates="audit",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'completed', 'partial', 'failed', 'cost_capped')",
            name="audits_status_check",
        ),
        Index("idx_audits_site_started", "site_domain", "started_at"),
    )


class Capture(Base):
    """A single variable's capture for one audit/subject pair."""

    __tablename__ = "captures"

    capture_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.audit_id", ondelete="CASCADE"),
        nullable=False,
    )
    variable_id: Mapped[str] = mapped_column(String, nullable=False)
    pillar: Mapped[str] = mapped_column(String, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    taxonomy_version: Mapped[str] = mapped_column(String, nullable=False)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    rules: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    evidence_weight: Mapped[str] = mapped_column(String, nullable=False)
    data_sources_used: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    )
    cost_incurred_gbp: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    staleness_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    errors: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    raw_response_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)

    audit: Mapped["Audit"] = relationship(back_populates="captures")

    __table_args__ = (
        CheckConstraint(
            "status IN ('passed', 'failed', 'partial', 'not_applicable', "
            "'error', 'unmeasurable')",
            name="captures_status_check",
        ),
        CheckConstraint(
            "evidence_weight IN ('Consensus', 'Probable', 'Contested', 'Speculative')",
            name="captures_evidence_weight_check",
        ),
        Index("idx_captures_audit", "audit_id"),
        Index("idx_captures_variable", "audit_id", "variable_id"),
        Index("idx_captures_subject_time", "subject_type", "subject_id", "captured_at"),
        Index("idx_captures_status", "audit_id", "status"),
        Index("idx_captures_pillar_status", "audit_id", "pillar", "status"),
        Index("idx_captures_value_gin", "value", postgresql_using="gin"),
        Index("idx_captures_rules_gin", "rules", postgresql_using="gin"),
        # Note: ivfflat index on `embedding` is created in the initial
        # migration via raw SQL because SQLAlchemy/Alembic do not emit
        # vector_cosine_ops + lists option declaratively yet.
    )


class AdapterCall(Base):
    """Log of every external adapter call for cost attribution and debugging."""

    __tablename__ = "adapter_calls"

    call_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    audit_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("audits.audit_id", ondelete="CASCADE"),
        nullable=False,
    )
    capture_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("captures.capture_id", ondelete="SET NULL"),
        nullable=True,
    )
    adapter: Mapped[str] = mapped_column(String, nullable=False)
    endpoint: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_gbp: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    audit: Mapped["Audit"] = relationship(back_populates="adapter_calls")

    __table_args__ = (
        Index("idx_adapter_calls_audit", "audit_id"),
        Index("idx_adapter_calls_adapter", "audit_id", "adapter"),
        Index("idx_adapter_calls_started", "started_at"),
    )


class SavedAnalysis(Base):
    """A persisted competitive or strategy analysis run.

    The auditor owns the audit tables; this stores the platform's own derived /
    paid analyses (competitive runs, strategy snapshots) so the UI can list past
    runs (like audits) and revisit them for free instead of re-paying DataForSEO.
    """

    __tablename__ = "saved_analyses"

    analysis_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    target: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    cost_gbp: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('competitive', 'strategy')",
            name="saved_analyses_kind_check",
        ),
        Index("idx_saved_kind_target_created", "kind", "target", "created_at"),
    )
