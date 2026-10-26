"""Owner-scoped graph checkpoints and fenced worker leases. Revision 0005."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in [sa.Column("managed", sa.Boolean, nullable=False, server_default="false"), sa.Column("worker_id", UUID(as_uuid=True)),
        sa.Column("generation", sa.Integer, nullable=False, server_default="0"), sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)), sa.Column("deadline", sa.DateTime(timezone=True)), sa.Column("workflow", JSONB)]:
        op.add_column("run_jobs", column)
    op.create_check_constraint("run_jobs_generation", "run_jobs", "generation >= 0")
    op.create_check_constraint("run_jobs_managed", "run_jobs", "NOT managed OR (deadline IS NOT NULL AND workflow IS NOT NULL)")
    op.create_index("ix_run_jobs_recovery", "run_jobs", ["owner_id", "state", "lease_until"])

    def common():
        return [sa.Column("id", UUID(as_uuid=True), primary_key=True), sa.Column("owner_id", UUID(as_uuid=True), nullable=False, index=True),
            sa.Column("run_id", UUID(as_uuid=True), nullable=False, index=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["owner_id"], ["auth.users.id"]), sa.ForeignKeyConstraint(["run_id", "owner_id"], ["runs.id", "runs.owner_id"]),
            sa.UniqueConstraint("id", "owner_id"), sa.UniqueConstraint("id", "run_id", "owner_id")]
    op.create_table("graph_checkpoints", *common(), sa.Column("namespace", sa.Text, nullable=False), sa.Column("checkpoint_id", sa.String(64), nullable=False),
        sa.Column("parent_id", sa.String(64)), sa.Column("encoding", sa.String(16), nullable=False), sa.Column("payload", sa.LargeBinary, nullable=False),
        sa.Column("metadata", JSONB, nullable=False), sa.Column("graph_version", sa.String(32), nullable=False),
        sa.UniqueConstraint("run_id", "namespace", "checkpoint_id"))
    op.create_table("graph_writes", *common(), sa.Column("namespace", sa.Text, nullable=False), sa.Column("checkpoint_id", sa.String(64), nullable=False),
        sa.Column("task_id", sa.Text, nullable=False), sa.Column("write_index", sa.Integer, nullable=False), sa.Column("channel", sa.Text, nullable=False),
        sa.Column("encoding", sa.String(16), nullable=False), sa.Column("payload", sa.LargeBinary, nullable=False), sa.Column("task_path", sa.Text, nullable=False),
        sa.UniqueConstraint("run_id", "namespace", "checkpoint_id", "task_id", "write_index"),
        sa.ForeignKeyConstraint(["run_id", "namespace", "checkpoint_id"], ["graph_checkpoints.run_id", "graph_checkpoints.namespace", "graph_checkpoints.checkpoint_id"]))
    for name in ("graph_checkpoints", "graph_writes"):
        op.execute(f'ALTER TABLE public.{name} ENABLE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE public.{name} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON public.{name} FROM PUBLIC, anon, authenticated')
        op.execute(f"CREATE POLICY owner_read ON public.{name} FOR SELECT TO lather_api USING (owner_id = (SELECT auth.uid()))")
        op.execute(f"CREATE POLICY owner_write ON public.{name} FOR INSERT TO lather_api WITH CHECK (owner_id = (SELECT auth.uid()))")
        op.execute(f'GRANT SELECT, INSERT ON public.{name} TO lather_api')
    op.execute("CREATE POLICY owner_update ON public.graph_writes FOR UPDATE TO lather_api USING (owner_id = (SELECT auth.uid())) WITH CHECK (owner_id = (SELECT auth.uid()))")
    op.execute("GRANT UPDATE ON public.graph_writes TO lather_api")


def downgrade() -> None:
    # Explicit rollback removes graph state; domain evidence/approvals remain intact.
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM run_jobs WHERE managed AND state='claimed' AND lease_until > clock_timestamp())")).scalar_one():
        raise RuntimeError("active_worker_prevents_downgrade")
    op.drop_table("graph_writes")
    op.drop_table("graph_checkpoints")
    op.drop_index("ix_run_jobs_recovery", "run_jobs")
    op.drop_constraint("run_jobs_managed", "run_jobs", type_="check")
    op.drop_constraint("run_jobs_generation", "run_jobs", type_="check")
    for name in ("workflow", "deadline", "lease_until", "heartbeat_at", "generation", "worker_id", "managed"):
        op.drop_column("run_jobs", name)
