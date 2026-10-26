"""Persist reference price segment and optional own-bar inputs without rewriting v1.

Revision ID: 0002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("briefs", sa.Column("preferences", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")))


def downgrade() -> None:
    op.drop_column("briefs", "preferences")
