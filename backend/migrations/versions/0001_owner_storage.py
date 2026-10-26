"""Owner-scoped research storage and RLS; Supabase auth schema is pre-existing.

Revision ID: 0001
"""
from alembic import op
from sqlalchemy import text

from migrations.schema_v1 import TABLES, metadata

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("CREATE ROLE lather_api NOLOGIN NOINHERIT NOBYPASSRLS"))
    bind.execute(text("GRANT USAGE ON SCHEMA public, auth TO lather_api"))
    bind.execute(text("GRANT EXECUTE ON FUNCTION auth.uid() TO lather_api"))
    for table in metadata.sorted_tables:
        if table.name not in TABLES:
            continue
        table.create(bind)
        name = table.name  # immutable names declared in this revision's model metadata
        bind.execute(text(f'ALTER TABLE public."{name}" ENABLE ROW LEVEL SECURITY'))
        bind.execute(text(f'ALTER TABLE public."{name}" FORCE ROW LEVEL SECURITY'))
        bind.execute(text(f'REVOKE ALL ON public."{name}" FROM PUBLIC, anon, authenticated'))
        bind.execute(text(f'CREATE POLICY owner_read ON public."{name}" FOR SELECT TO authenticated, lather_api USING (owner_id = (SELECT auth.uid()))'))
        bind.execute(text(f'CREATE POLICY owner_write ON public."{name}" FOR INSERT TO lather_api WITH CHECK (owner_id = (SELECT auth.uid()))'))
        bind.execute(text(f'GRANT SELECT, INSERT ON public."{name}" TO lather_api'))
        if name != "idempotency_keys":
            bind.execute(text(f'GRANT SELECT ON public."{name}" TO authenticated'))
        if name in {"runs", "approval_requests", "run_jobs"}:
            bind.execute(text(f'CREATE POLICY owner_update ON public."{name}" FOR UPDATE TO lather_api USING (owner_id = (SELECT auth.uid())) WITH CHECK (owner_id = (SELECT auth.uid()))'))
            bind.execute(text(f'GRANT UPDATE ON public."{name}" TO lather_api'))


def downgrade() -> None:
    bind = op.get_bind()
    for table in reversed(metadata.sorted_tables):
        if table.name in TABLES:
            table.drop(bind)
    bind.execute(text("REVOKE ALL ON SCHEMA public, auth FROM lather_api"))
    bind.execute(text("REVOKE EXECUTE ON FUNCTION auth.uid() FROM lather_api"))
    bind.execute(text("DROP ROLE lather_api"))

