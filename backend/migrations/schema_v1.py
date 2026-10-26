"""Domain metadata; auth.users belongs to Supabase, never to our migrations."""
from sqlalchemy import Boolean, CheckConstraint, Column, Computed, DateTime, ForeignKeyConstraint, Integer, Numeric, String, Table, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql.schema import SchemaItem

from sqlalchemy.orm import DeclarativeBase

class SnapshotBase(DeclarativeBase):
    pass

metadata = SnapshotBase.metadata
auth_users = Table("users", metadata, Column("id", UUID(as_uuid=True), primary_key=True), schema="auth")
TABLES: dict[str, Table] = {}


def owned(name: str, *columns, run: bool = True, constraints=()) -> Table:
    common: list[SchemaItem] = [
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("owner_id", UUID(as_uuid=True), nullable=False, index=True),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        ForeignKeyConstraint(["owner_id"], ["auth.users.id"]),
        UniqueConstraint("id", "owner_id"),
    ]
    if run:
        common += [Column("run_id", UUID(as_uuid=True), nullable=False, index=True),
                   ForeignKeyConstraint(["run_id", "owner_id"], ["runs.id", "runs.owner_id"]),
                   UniqueConstraint("id", "run_id", "owner_id")]
    table = Table(name, metadata, *common, *columns, *constraints)
    TABLES[name] = table
    return table


def scoped_fk(column: str, target: str):
    return ForeignKeyConstraint([column, "run_id", "owner_id"], [f"{target}.id", f"{target}.run_id", f"{target}.owner_id"])


briefs = owned("briefs", Column("category", Text, nullable=False), Column("geography", Text, nullable=False),
    Column("customer", Text, nullable=False), Column("objective", Text, nullable=False),
    Column("known_competitors", JSONB, nullable=False), Column("version", Integer, nullable=False), run=False,
    constraints=(CheckConstraint("version > 0"),))
runs = owned("runs", Column("brief_id", UUID(as_uuid=True), nullable=False), Column("status", String(32), nullable=False),
    Column("version", Integer, nullable=False), Column("budget", JSONB, nullable=False),
    Column("checkpoint", JSONB), Column("failure_code", String(64)), run=False,
    constraints=(ForeignKeyConstraint(["brief_id", "owner_id"], ["briefs.id", "briefs.owner_id"]),
        CheckConstraint("version > 0"), CheckConstraint("status IN ('queued','shortlist_review','researching','report_review','complete','cancelled','partial','failed')")))
events = owned("run_events", Column("sequence", Integer, nullable=False), Column("kind", String(64), nullable=False),
    Column("data", JSONB, nullable=False), constraints=(UniqueConstraint("run_id", "sequence"), CheckConstraint("sequence > 0")))
competitors = owned("competitors", Column("name", Text, nullable=False), Column("canonical_url", Text, nullable=False))
sources = owned("sources", Column("canonical_url", Text, nullable=False), Column("title", Text, nullable=False),
    Column("publisher", Text, nullable=False), Column("retrieved_at", DateTime(timezone=True), nullable=False),
    Column("content_hash", String(64)), Column("access_status", String(20), nullable=False), Column("excerpt", Text),
    constraints=(CheckConstraint("access_status IN ('ok','denied','unavailable')"),
        CheckConstraint("access_status <> 'ok' OR (content_hash IS NOT NULL AND content_hash ~ '^[a-f0-9]{64}$')")))
claims = owned("claims", Column("text", Text, nullable=False), Column("kind", String(40), nullable=False),
    Column("material", Boolean, nullable=False), Column("review_status", String(24), nullable=False),
    constraints=(CheckConstraint("kind IN ('fact','interpretation','hypothesis','competitor_marketing_claim')"),
        CheckConstraint("review_status IN ('unreviewed','supported','flagged')")))
claim_sources = owned("claim_sources", Column("claim_id", UUID(as_uuid=True), nullable=False), Column("source_id", UUID(as_uuid=True), nullable=False),
    Column("quote", Text, nullable=False), Column("excerpt_hash", String(64), nullable=False),
    constraints=(scoped_fk("claim_id", "claims"), scoped_fk("source_id", "sources"), UniqueConstraint("claim_id", "source_id")))
products = owned("products", Column("competitor_id", UUID(as_uuid=True), nullable=False), Column("sku", Text, nullable=False),
    Column("name", Text, nullable=False), Column("ingredients", JSONB), Column("attributes", JSONB, nullable=False),
    constraints=(scoped_fk("competitor_id", "competitors"),))
prices = owned("price_observations", Column("product_id", UUID(as_uuid=True), nullable=False), Column("source_id", UUID(as_uuid=True), nullable=False),
    Column("amount", Numeric(18, 4), nullable=False), Column("currency", String(3), nullable=False),
    Column("total_weight_g", Numeric(18, 4)), Column("pack_qty", Integer), Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("unit_price_100g", Numeric(24, 8), Computed("amount * 100 / NULLIF(total_weight_g, 0)", persisted=True)),
    constraints=(scoped_fk("product_id", "products"), scoped_fk("source_id", "sources"), CheckConstraint("amount >= 0 AND amount <> 'NaN'::numeric"),
        CheckConstraint("total_weight_g IS NULL OR (total_weight_g > 0 AND total_weight_g <> 'NaN'::numeric)"), CheckConstraint("pack_qty IS NULL OR pack_qty > 0"),
        CheckConstraint("currency ~ '^[A-Z]{3}$'")))
reports = owned("reports", Column("version", Integer, nullable=False), Column("content_hash", String(64), nullable=False),
    Column("data", JSONB, nullable=False), constraints=(UniqueConstraint("run_id", "version"), CheckConstraint("version > 0"),
        CheckConstraint("content_hash ~ '^[a-f0-9]{64}$'")))
approval_requests = owned("approval_requests", Column("gate", String(16), nullable=False), Column("artifact_version", Integer, nullable=False),
    Column("artifact_hash", String(64), nullable=False), Column("state", String(16), nullable=False), Column("artifact", JSONB, nullable=False),
    constraints=(CheckConstraint("gate IN ('shortlist','report')"), CheckConstraint("state IN ('pending','decided','superseded')"),
        CheckConstraint("artifact_version > 0"), CheckConstraint("artifact_hash ~ '^[a-f0-9]{64}$'")))
approval_decisions = owned("approval_decisions", Column("request_id", UUID(as_uuid=True), nullable=False),
    Column("decision", String(24), nullable=False), Column("artifact_version", Integer, nullable=False), Column("artifact_hash", String(64), nullable=False),
    constraints=(scoped_fk("request_id", "approval_requests"), UniqueConstraint("request_id"),
        CheckConstraint("decision IN ('approve','reject','request_changes')")))
evaluation_cases = owned("evaluation_cases", Column("case_id", String(64), nullable=False), Column("dataset_version", String(64), nullable=False),
    Column("data", JSONB, nullable=False), run=False)
evaluation_results = owned("evaluation_results", Column("case_id", UUID(as_uuid=True), nullable=False), Column("outcome", String(24), nullable=False),
    Column("data", JSONB, nullable=False), constraints=(ForeignKeyConstraint(["case_id", "owner_id"], ["evaluation_cases.id", "evaluation_cases.owner_id"]),))
usage = owned("usage_records", Column("operation_id", UUID(as_uuid=True), nullable=False), Column("attempt", Integer, nullable=False),
    Column("calls", Integer, nullable=False), Column("tokens", Integer, nullable=False), Column("cost_usd", Numeric(18, 8), nullable=False),
    constraints=(UniqueConstraint("run_id", "operation_id", "attempt"), CheckConstraint("attempt > 0 AND calls >= 0 AND tokens >= 0 AND cost_usd >= 0 AND cost_usd <> 'NaN'::numeric")))
jobs = owned("run_jobs", Column("state", String(16), nullable=False), constraints=(UniqueConstraint("run_id"), CheckConstraint("state IN ('queued','claimed','done')")))
idempotency = owned("idempotency_keys", Column("operation", String(128), nullable=False), Column("key_hash", String(64), nullable=False),
    Column("request_hash", String(64), nullable=False), Column("response", JSONB, nullable=False), run=False,
    constraints=(UniqueConstraint("owner_id", "operation", "key_hash"),))

