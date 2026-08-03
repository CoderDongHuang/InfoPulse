"""Add planetary intelligence resilience."""
from alembic import op
from app.core.database import Base
import app.models  # noqa: F401
revision="20260803_0027";down_revision="20260803_0026";branch_labels=None;depends_on=None
TABLES=("proof_mesh_envelopes","policy_proof_registry","post_quantum_migrations","planetary_twin_runs","agent_constitution_runs","crisis_resource_listings","crisis_resource_trades","autonomous_insurance_policies","verifiable_memory_transfers","edge_mesh_messages","public_interest_audits")
def upgrade():
 bind=op.get_bind()
 for name in TABLES:Base.metadata.tables[name].create(bind=bind,checkfirst=False)
def downgrade():
 bind=op.get_bind()
 for name in reversed(TABLES):Base.metadata.tables[name].drop(bind=bind,checkfirst=True)
