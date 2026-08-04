"""Add global cognitive infrastructure."""
from alembic import op
from app.core.database import Base
import app.models  # noqa: F401
revision="20260804_0028";down_revision="20260803_0027";branch_labels=None;depends_on=None
TABLES=("proof_certifications","constitution_upgrades","quantum_transparency_archives","public_intelligence_signals","epistemic_assessments","autonomous_clearing_batches","fair_resource_allocations","long_horizon_scenarios","intergenerational_commitments","sovereign_stack_builds","sovereign_stack_upgrades")
def upgrade():
 bind=op.get_bind()
 for name in TABLES:Base.metadata.tables[name].create(bind=bind,checkfirst=False)
def downgrade():
 bind=op.get_bind()
 for name in reversed(TABLES):Base.metadata.tables[name].drop(bind=bind,checkfirst=True)
