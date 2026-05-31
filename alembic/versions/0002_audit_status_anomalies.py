"""Add completed_with_anomalies to audits.status check constraint.

The audit-completeness gate (orchestrator._check_audit_completeness)
marks audits with detected silent-regression patterns as
``completed_with_anomalies`` so they're visually distinguishable from
clean completions. The original CHECK constraint didn't allow this
value, so the orchestrator's audit-close UPDATE failed with
IntegrityError when the gate fired.

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

from alembic import op


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("audits_status_check", "audits", type_="check")
    op.create_check_constraint(
        "audits_status_check",
        "audits",
        "status IN ("
        "'running', 'completed', 'completed_with_anomalies', "
        "'partial', 'failed', 'cost_capped'"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint("audits_status_check", "audits", type_="check")
    op.create_check_constraint(
        "audits_status_check",
        "audits",
        "status IN ('running', 'completed', 'partial', 'failed', 'cost_capped')",
    )
