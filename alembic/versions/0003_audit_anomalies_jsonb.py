"""Add anomalies + consistency_violations JSONB columns to audits.

The completeness gate and consistency rules emit structured anomaly /
violation dicts. Migration 0002 added the
``completed_with_anomalies`` status enum but the anomalies themselves
were only logged, not persisted. This migration adds the two JSONB
columns so the API can expose them and the UI can render them.

Revision ID: 0003
Revises: 0002
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audits",
        sa.Column(
            "anomalies",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "audits",
        sa.Column(
            "consistency_violations",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("audits", "consistency_violations")
    op.drop_column("audits", "anomalies")
