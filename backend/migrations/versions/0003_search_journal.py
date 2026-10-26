"""Owner-scoped durable search reservations/results. Revision ID: 0003."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("evidence_kind", sa.String(24), nullable=False, server_default="page_excerpt"))
    op.create_check_constraint("sources_evidence_kind", "sources", "evidence_kind IN ('search_snippet','page_excerpt')")
    op.create_table("tool_attempts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True), sa.Column("owner_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False, index=True), sa.Column("operation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False), sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("cost_upper_bound_usd", sa.Numeric(18, 8), nullable=False), sa.Column("state", sa.String(16), nullable=False), sa.Column("outcome", JSONB(none_as_null=True)),
        sa.ForeignKeyConstraint(["owner_id"], ["auth.users.id"]), sa.ForeignKeyConstraint(["run_id", "owner_id"], ["runs.id", "runs.owner_id"]),
        sa.UniqueConstraint("id", "owner_id"), sa.UniqueConstraint("id", "run_id", "owner_id"), sa.UniqueConstraint("run_id", "operation_id", "attempt"),
        sa.CheckConstraint("attempt BETWEEN 1 AND 3"), sa.CheckConstraint("cost_upper_bound_usd >= 0 AND cost_upper_bound_usd <> 'NaN'::numeric"),
        sa.CheckConstraint("state IN ('reserved','completed')"), sa.CheckConstraint("(state='completed') = (outcome IS NOT NULL)"))
    op.execute('ALTER TABLE public.tool_attempts ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE public.tool_attempts FORCE ROW LEVEL SECURITY')
    op.execute('REVOKE ALL ON public.tool_attempts FROM PUBLIC, anon, authenticated')
    op.execute("CREATE POLICY owner_read ON public.tool_attempts FOR SELECT TO lather_api USING (owner_id = (SELECT auth.uid()))")
    op.execute("CREATE POLICY owner_write ON public.tool_attempts FOR INSERT TO lather_api WITH CHECK (owner_id = (SELECT auth.uid()))")
    op.execute("CREATE POLICY owner_update ON public.tool_attempts FOR UPDATE TO lather_api USING (owner_id = (SELECT auth.uid())) WITH CHECK (owner_id = (SELECT auth.uid()))")
    op.execute('GRANT SELECT, INSERT, UPDATE ON public.tool_attempts TO lather_api')


def downgrade() -> None:
    op.drop_table("tool_attempts")
    op.drop_constraint("sources_evidence_kind", "sources", type_="check")
    op.drop_column("sources", "evidence_kind")
