"""Enforce the case-insensitive identity contract at the database boundary."""
from alembic import op
import sqlalchemy as sa

revision = "20261014_0034"
down_revision = "20261009_0033"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Keep writers out between the preflight and creation of both indexes.
        connection.execute(sa.text("LOCK TABLE users IN SHARE ROW EXCLUSIVE MODE"))
    users = sa.table("users", sa.column("username", sa.String), sa.column("email", sa.String))
    for field in ("username", "email"):
        key = sa.func.lower(users.c[field])
        duplicate = connection.execute(sa.select(sa.func.count()).select_from(users)
                                       .group_by(key).having(sa.func.count() > 1).limit(1)).first()
        if duplicate:
            raise RuntimeError(
                f"Case-insensitive users.{field} collision: resolve conflicting accounts with "
                "their owners before retrying migration 20261014_0034. No accounts were renamed or removed."
            )
    op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)


def downgrade():
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_index("uq_users_username_lower", table_name="users")
