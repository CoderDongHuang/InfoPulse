"""Add global intelligence coordination and continuous verification."""
from alembic import op
from app.core.database import Base
import app.models  # noqa: F401

revision = "20260802_0024"
down_revision = "20260801_0023"
branch_labels = None
depends_on = None
TABLES = ("federation_nodes", "capability_negotiations", "proof_verifications", "contract_negotiations", "regulatory_subscriptions", "regulatory_updates", "systemic_risk_signals", "control_observations", "arbitration_cases", "federated_evaluations", "global_settlements", "crisis_rooms", "crisis_commands")


def upgrade():
    bind = op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind, checkfirst=False)


def downgrade():
    bind = op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind, checkfirst=True)
