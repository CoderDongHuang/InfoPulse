"""Add the trusted intelligence network and ecosystem marketplace."""
from alembic import op
from app.core.database import Base
import app.models  # noqa: F401

revision="20260801_0023";down_revision="20260801_0022";branch_labels=None;depends_on=None
TABLES=("abuse_reports","data_contracts","ecosystem_drills","federation_agreements","intelligence_products","provenance_nodes","regulatory_packs","responsibility_events","supply_artifacts","trust_scores","federated_computations","federation_envelopes","marketplace_orders","provenance_edges","marketplace_disputes")

def upgrade():
    bind=op.get_bind()
    for name in TABLES:
        Base.metadata.tables[name].create(bind=bind,checkfirst=False)

def downgrade():
    bind=op.get_bind()
    for name in reversed(TABLES):
        Base.metadata.tables[name].drop(bind=bind,checkfirst=True)
