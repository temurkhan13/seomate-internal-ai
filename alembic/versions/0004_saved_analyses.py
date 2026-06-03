"""Add saved_analyses table , persisted competitive runs + strategy snapshots.

Lets the UI list past competitive / strategy analyses (like audits) and revisit
them for free instead of re-running paid DataForSEO queries. Additive: does not
touch the existing audit / capture tables.

Revision ID: 0004
Revises: 0003
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "saved_analyses",
        sa.Column(
            "analysis_id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("target", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("cost_gbp", sa.Numeric(12, 6), nullable=True),
        sa.Column("payload", JSONB, nullable=False),
        sa.CheckConstraint(
            "kind IN ('competitive', 'strategy')",
            name="saved_analyses_kind_check",
        ),
    )
    op.create_index(
        "idx_saved_kind_target_created",
        "saved_analyses",
        ["kind", "target", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_saved_kind_target_created", table_name="saved_analyses")
    op.drop_table("saved_analyses")
