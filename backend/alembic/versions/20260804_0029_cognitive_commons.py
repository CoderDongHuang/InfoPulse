"""Add global cognitive commons."""
from alembic import op
from app.core.database import Base
import app.models
revision="20260804_0029";down_revision="20260804_0028";branch_labels=None;depends_on=None
TABLES=("proof_consensus_rounds","federated_constitution_protocols","evidence_preservations","causal_signal_validations","dissent_markets","public_treasuries","allocation_appeals","century_risk_scenarios","civilization_safety_valves","sovereign_federated_releases")
def upgrade():
 bind=op.get_bind()
 for n in TABLES:Base.metadata.tables[n].create(bind=bind,checkfirst=False)
def downgrade():
 bind=op.get_bind()
 for n in reversed(TABLES):Base.metadata.tables[n].drop(bind=bind,checkfirst=True)
