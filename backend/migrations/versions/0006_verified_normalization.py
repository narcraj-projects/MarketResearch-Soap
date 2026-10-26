"""Only verified purchase-item weights enable normalized prices. Revision 0006."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_observations", sa.Column("normalization_data", JSONB))
    # Existing evidence remains immutable; legacy arithmetic without a verified basis
    # becomes unavailable rather than being silently certified by a backfill.
    op.drop_column("price_observations", "unit_price_100g")
    op.add_column("price_observations", sa.Column("unit_price_100g", sa.Numeric(24, 8),
        sa.Computed("CASE WHEN normalization_data->>'eligible' = 'true' THEN amount * 100 / NULLIF(total_weight_g, 0) END", persisted=True)))
    op.create_check_constraint("price_normalization_shape", "price_observations", "normalization_data IS NULL OR (jsonb_typeof(normalization_data)='object' AND normalization_data ?& ARRAY['schema_version','eligible'] AND normalization_data->>'schema_version'='normalization-1.0' AND jsonb_typeof(normalization_data->'eligible')='boolean' AND (normalization_data->>'eligible'='false' OR total_weight_g IS NOT NULL))")


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM price_observations WHERE total_weight_g IS NOT NULL AND coalesce(normalization_data->>'eligible','false') <> 'true')")).scalar_one():
        raise RuntimeError("unverified_weight_prevents_safe_downgrade")
    op.drop_constraint("price_normalization_shape", "price_observations", type_="check")
    op.drop_column("price_observations", "unit_price_100g")
    op.add_column("price_observations", sa.Column("unit_price_100g", sa.Numeric(24, 8), sa.Computed("amount * 100 / NULLIF(total_weight_g, 0)", persisted=True)))
    op.drop_column("price_observations", "normalization_data")
