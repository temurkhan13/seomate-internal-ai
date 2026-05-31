"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-06

Creates the SEOMATE database schema:
- Extensions: uuid-ossp, pgcrypto, vector
- Tables: audits, captures, adapter_calls
- Indexes including JSONB GIN and pgvector ivfflat

This migration matches the DDL in docs/site-auditor-architecture.md §8 exactly.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Required Postgres extensions.
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # ─── audits ─────────────────────────────────────────────────────────────
    op.create_table(
        "audits",
        sa.Column(
            "audit_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("site_domain", sa.String(), nullable=False),
        sa.Column("config_snapshot", JSONB, nullable=False),
        sa.Column("taxonomy_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_cost_gbp", sa.Numeric(12, 4), nullable=True),
        sa.Column(
            "variables_attempted",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "variables_passed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "variables_failed",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "variables_errored",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "variables_partial",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "variables_unmeasurable",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'partial', 'failed', 'cost_capped')",
            name="audits_status_check",
        ),
    )
    op.create_index(
        "idx_audits_site_started",
        "audits",
        ["site_domain", sa.text("started_at DESC")],
    )

    # ─── captures ───────────────────────────────────────────────────────────
    op.create_table(
        "captures",
        sa.Column(
            "capture_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "audit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audits.audit_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("variable_id", sa.String(), nullable=False),
        sa.Column("pillar", sa.String(), nullable=False),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("taxonomy_version", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("value", JSONB, nullable=True),
        sa.Column("rules", JSONB, nullable=True),
        sa.Column("evidence_weight", sa.String(), nullable=False),
        sa.Column(
            "data_sources_used",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "cost_incurred_gbp",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("staleness_seconds", sa.Integer(), nullable=True),
        sa.Column("errors", JSONB, nullable=True),
        sa.Column("raw_response_ref", sa.String(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'partial', 'not_applicable', "
            "'error', 'unmeasurable')",
            name="captures_status_check",
        ),
        sa.CheckConstraint(
            "evidence_weight IN ('Consensus', 'Probable', 'Contested', 'Speculative')",
            name="captures_evidence_weight_check",
        ),
    )
    op.create_index("idx_captures_audit", "captures", ["audit_id"])
    op.create_index("idx_captures_variable", "captures", ["audit_id", "variable_id"])
    op.create_index(
        "idx_captures_subject_time",
        "captures",
        ["subject_type", "subject_id", sa.text("captured_at DESC")],
    )
    op.create_index("idx_captures_status", "captures", ["audit_id", "status"])
    op.create_index(
        "idx_captures_pillar_status",
        "captures",
        ["audit_id", "pillar", "status"],
    )
    op.create_index(
        "idx_captures_value_gin",
        "captures",
        ["value"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_captures_rules_gin",
        "captures",
        ["rules"],
        postgresql_using="gin",
    )
    # ivfflat for embedding similarity. SQLAlchemy/Alembic do not yet
    # express vector_cosine_ops + lists declaratively, so raw SQL.
    op.execute(
        "CREATE INDEX idx_captures_embedding_ivfflat "
        "ON captures USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )

    # ─── adapter_calls ──────────────────────────────────────────────────────
    op.create_table(
        "adapter_calls",
        sa.Column(
            "call_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "audit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audits.audit_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "capture_id",
            UUID(as_uuid=True),
            sa.ForeignKey("captures.capture_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("adapter", sa.String(), nullable=False),
        sa.Column("endpoint", sa.String(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "cost_gbp",
            sa.Numeric(12, 6),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error", sa.String(), nullable=True),
    )
    op.create_index("idx_adapter_calls_audit", "adapter_calls", ["audit_id"])
    op.create_index(
        "idx_adapter_calls_adapter",
        "adapter_calls",
        ["audit_id", "adapter"],
    )
    op.create_index(
        "idx_adapter_calls_started",
        "adapter_calls",
        [sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_adapter_calls_started", table_name="adapter_calls")
    op.drop_index("idx_adapter_calls_adapter", table_name="adapter_calls")
    op.drop_index("idx_adapter_calls_audit", table_name="adapter_calls")
    op.drop_table("adapter_calls")

    op.execute("DROP INDEX IF EXISTS idx_captures_embedding_ivfflat")
    op.drop_index("idx_captures_rules_gin", table_name="captures")
    op.drop_index("idx_captures_value_gin", table_name="captures")
    op.drop_index("idx_captures_pillar_status", table_name="captures")
    op.drop_index("idx_captures_status", table_name="captures")
    op.drop_index("idx_captures_subject_time", table_name="captures")
    op.drop_index("idx_captures_variable", table_name="captures")
    op.drop_index("idx_captures_audit", table_name="captures")
    op.drop_table("captures")

    op.drop_index("idx_audits_site_started", table_name="audits")
    op.drop_table("audits")

    # Extensions intentionally not dropped — they may be used elsewhere.
