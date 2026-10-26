"""Attributable research snapshots, tasks and nullable unknown SKU. Revision 0004."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("claim_sources", sa.Column("locator", sa.Text))
    op.alter_column("products", "sku", existing_type=sa.Text(), nullable=True)
    op.drop_constraint("sources_evidence_kind", "sources", type_="check")
    op.create_check_constraint("sources_evidence_kind", "sources", "evidence_kind IN ('search_snippet','page_excerpt','robots_policy')")
    def common():
        return [sa.Column("id", UUID(as_uuid=True), primary_key=True), sa.Column("owner_id", UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("run_id", UUID(as_uuid=True), nullable=False, index=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["owner_id"], ["auth.users.id"]), sa.ForeignKeyConstraint(["run_id", "owner_id"], ["runs.id", "runs.owner_id"]),
            sa.UniqueConstraint("id", "owner_id"), sa.UniqueConstraint("id", "run_id", "owner_id")]
    op.create_table("source_documents", *common(), sa.Column("source_id", UUID(as_uuid=True), nullable=False), sa.Column("body", sa.Text), sa.Column("excerpt", sa.Text),
        sa.Column("text_hash", sa.String(64)), sa.Column("structured", JSONB, nullable=False), sa.Column("links", JSONB, nullable=False), sa.Column("reason", sa.String(100)),
        sa.UniqueConstraint("source_id"), sa.ForeignKeyConstraint(["source_id", "run_id", "owner_id"], ["sources.id", "sources.run_id", "sources.owner_id"]))
    op.create_table("research_tasks", *common(), sa.Column("competitor_id", UUID(as_uuid=True), nullable=False), sa.Column("state", sa.String(16), nullable=False),
        sa.Column("data", JSONB, nullable=False), sa.UniqueConstraint("run_id", "competitor_id"), sa.CheckConstraint("state IN ('complete','partial')"),
        sa.ForeignKeyConstraint(["competitor_id", "run_id", "owner_id"], ["competitors.id", "competitors.run_id", "competitors.owner_id"]))
    for name in ("source_documents", "research_tasks"):
        op.execute(f'ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{name} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON public.{name} FROM PUBLIC, anon, authenticated')
        op.execute(f"CREATE POLICY owner_read ON public.{name} FOR SELECT TO lather_api USING (owner_id = (SELECT auth.uid()))")
        op.execute(f"CREATE POLICY owner_write ON public.{name} FOR INSERT TO lather_api WITH CHECK (owner_id = (SELECT auth.uid()))")
        op.execute(f'GRANT SELECT, INSERT ON public.{name} TO lather_api')


def downgrade() -> None:
    # Never manufacture SKUs or delete evidence to force compatibility with the older schema.
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM products WHERE sku IS NULL)")).scalar_one():
        raise RuntimeError("unknown_sku_prevents_lossless_downgrade")
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM sources WHERE evidence_kind='robots_policy')")).scalar_one():
        raise RuntimeError("robots_evidence_prevents_lossless_downgrade")
    op.drop_table("research_tasks")
    op.drop_table("source_documents")
    op.drop_constraint("sources_evidence_kind", "sources", type_="check")
    op.create_check_constraint("sources_evidence_kind", "sources", "evidence_kind IN ('search_snippet','page_excerpt')")
    op.alter_column("products", "sku", existing_type=sa.Text(), nullable=False)
    op.drop_column("claim_sources", "locator")
