"""Add provable autonomy and global continuity."""
from alembic import op
from app.core.database import Base
import app.models  # noqa: F401

revision = "20260803_0026"; down_revision = "20260802_0025"; branch_labels = None; depends_on = None
TABLES = ("decision_proofs", "policy_model_checks", "region_replicas", "regulatory_partitions", "memory_governance_records", "agent_collective_runs", "prediction_markets", "forecast_positions", "disaster_kernel_snapshots", "green_schedules", "liability_settlements")


def upgrade():
    bind = op.get_bind()
    for name in TABLES: Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade():
    bind = op.get_bind()
    for name in reversed(TABLES): Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
