"""Add versioned analyses and citations."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
revision="20260728_0006"; down_revision="20260728_0005"; branch_labels=None; depends_on=None
def upgrade():
    op.create_table("analyses",sa.Column("id",sa.String(36),primary_key=True),sa.Column("event_id",sa.String(36),sa.ForeignKey("events.id",ondelete="SET NULL")),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("parent_id",sa.String(36),sa.ForeignKey("analyses.id",ondelete="SET NULL")),sa.Column("version",sa.Integer(),nullable=False),sa.Column("analysis_type",sa.String(30),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("result",sa.JSON(),nullable=False),sa.Column("summary",sa.Text(),nullable=False),sa.Column("confidence",sa.Float(),nullable=False),sa.Column("evidence_coverage",sa.Float(),nullable=False),sa.Column("model_name",sa.String(120),nullable=False),sa.Column("prompt_version",sa.String(30),nullable=False),sa.Column("data_from",sa.DateTime(timezone=True)),sa.Column("data_to",sa.DateTime(timezone=True)),sa.Column("generated_at",sa.DateTime(timezone=True)),sa.Column("error_message",sa.Text(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    for x in ("event_id","user_id"): op.create_index(f"ix_analyses_{x}","analyses",[x])
    op.create_table("analysis_citations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("analysis_id",sa.String(36),sa.ForeignKey("analyses.id",ondelete="CASCADE"),nullable=False),sa.Column("content_item_id",sa.String(36),sa.ForeignKey("content_items.id",ondelete="RESTRICT"),nullable=False),sa.Column("quote",sa.Text(),nullable=False),sa.Column("locator",sa.JSON(),nullable=False),sa.Column("claim_index",sa.Integer(),nullable=False))
    op.create_index("ix_analysis_citations_analysis_id","analysis_citations",["analysis_id"]);op.create_index("ix_analysis_citations_content_item_id","analysis_citations",["content_item_id"])
def downgrade(): op.drop_table("analysis_citations");op.drop_table("analyses")
