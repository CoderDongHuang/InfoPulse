"""Add privacy-controlled analytics, feedback and release records."""
from alembic import op
import sqlalchemy as sa
revision="20260729_0014";down_revision="20260729_0013";branch_labels=None;depends_on=None

def upgrade():
    op.create_table("product_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("event_name",sa.String(60),nullable=False),sa.Column("route",sa.String(120),nullable=False),sa.Column("properties",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("user_feedback",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("category",sa.String(30),nullable=False),sa.Column("rating",sa.Integer(),nullable=False),sa.Column("message",sa.Text(),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False))
    op.create_table("release_records",sa.Column("id",sa.String(36),primary_key=True),sa.Column("version",sa.String(80),nullable=False,unique=True),sa.Column("environment",sa.String(20),nullable=False),sa.Column("status",sa.String(20),nullable=False),sa.Column("commit_sha",sa.String(64),nullable=False),sa.Column("notes",sa.Text(),nullable=False),sa.Column("metrics",sa.JSON(),nullable=False),sa.Column("deployed_by",sa.String(36),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("completed_at",sa.DateTime(timezone=True)))
    for table,columns in {"product_events":["user_id","event_name","route","created_at"],"user_feedback":["user_id","category","status","created_at"],"release_records":["version","environment","status","deployed_by","created_at"]}.items():
        for column in columns:op.create_index(f"ix_{table}_{column}",table,[column])

def downgrade():
    for table in ("release_records","user_feedback","product_events"):op.drop_table(table)
