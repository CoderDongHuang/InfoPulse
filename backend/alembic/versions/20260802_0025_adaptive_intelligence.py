"""Add the adaptive global intelligence operating system."""
from alembic import op
from app.core.database import Base
import app.models  # noqa: F401

revision = "20260802_0025"
down_revision = "20260802_0024"
branch_labels = None
depends_on = None
TABLES = ("protocol_rollouts", "policy_syntheses", "transparency_logs", "twin_simulations", "market_risk_controls", "sovereign_routes", "incident_orchestrations", "assurance_snapshots", "sustainability_ledgers", "governance_proposals", "governance_votes")


def upgrade():
    bind = op.get_bind()
    for name in TABLES: Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade():
    bind = op.get_bind()
    for name in reversed(TABLES): Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
