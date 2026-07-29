"""Add enterprise multi-tenancy and governance.

Revision ID: 20260729_0015
Revises: 20260729_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20260729_0015"
down_revision = "20260729_0014"
branch_labels = None
depends_on = None


def tenant_columns(*extra):
    return [sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False), *extra]


def upgrade():
    op.create_table("organizations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("slug", sa.String(80), nullable=False, unique=True), sa.Column("data_region", sa.String(24), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("enterprise_workspaces", *tenant_columns(sa.Column("name", sa.String(160), nullable=False), sa.Column("slug", sa.String(80), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)), sa.UniqueConstraint("organization_id", "slug", name="uq_enterprise_workspace_slug"))
    op.create_table("organization_members", *tenant_columns(sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("role_key", sa.String(40), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False)), sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_member"))
    op.create_table("workspace_members", *tenant_columns(sa.Column("workspace_id", sa.String(36), sa.ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("role_key", sa.String(40), nullable=False)), sa.UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"))
    op.create_table("enterprise_teams", *tenant_columns(sa.Column("name", sa.String(120), nullable=False), sa.Column("description", sa.String(500), nullable=False)), sa.UniqueConstraint("organization_id", "name", name="uq_enterprise_team_name"))
    op.create_table("enterprise_team_members", *tenant_columns(sa.Column("team_id", sa.String(36), sa.ForeignKey("enterprise_teams.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)), sa.UniqueConstraint("team_id", "user_id", name="uq_enterprise_team_member"))
    op.create_table("enterprise_roles", *tenant_columns(sa.Column("key", sa.String(40), nullable=False), sa.Column("name", sa.String(80), nullable=False), sa.Column("permissions", sa.JSON(), nullable=False), sa.Column("is_system", sa.Boolean(), nullable=False)), sa.UniqueConstraint("organization_id", "key", name="uq_enterprise_role_key"))
    op.create_table("identity_providers", *tenant_columns(sa.Column("provider_type", sa.String(20), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("enabled", sa.Boolean(), nullable=False), sa.Column("issuer", sa.String(500), nullable=False), sa.Column("client_id", sa.String(200), nullable=False), sa.Column("metadata", sa.JSON(), nullable=False), sa.Column("scim_token_hash", sa.String(64), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)))
    op.create_table("approval_requests", *tenant_columns(sa.Column("workspace_id", sa.String(36), sa.ForeignKey("enterprise_workspaces.id", ondelete="CASCADE")), sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("action_type", sa.String(60), nullable=False), sa.Column("risk_level", sa.String(20), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("decided_by", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("decision_note", sa.String(1000), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("decided_at", sa.DateTime(timezone=True))))
    op.create_table("legal_holds", *tenant_columns(sa.Column("name", sa.String(160), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("scope", sa.JSON(), nullable=False), sa.Column("status", sa.String(20), nullable=False), sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)))
    op.create_table("tenant_policies", sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True), sa.Column("require_sso", sa.Boolean(), nullable=False), sa.Column("require_mfa", sa.Boolean(), nullable=False), sa.Column("approval_for_high_risk", sa.Boolean(), nullable=False), sa.Column("session_minutes", sa.Integer(), nullable=False), sa.Column("allowed_email_domains", sa.JSON(), nullable=False), sa.Column("retention_days", sa.Integer(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("tenant_quotas", sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True), sa.Column("member_limit", sa.Integer(), nullable=False), sa.Column("storage_bytes", sa.BigInteger(), nullable=False), sa.Column("monthly_model_tokens", sa.BigInteger(), nullable=False), sa.Column("monthly_cost_limit", sa.Float(), nullable=False), sa.Column("alert_at_percent", sa.Integer(), nullable=False))
    op.create_table("tenant_sla_snapshots", *tenant_columns(sa.Column("period", sa.String(10), nullable=False), sa.Column("availability", sa.Float(), nullable=False), sa.Column("p95_latency_ms", sa.Float(), nullable=False), sa.Column("incidents", sa.Integer(), nullable=False), sa.Column("error_budget_remaining", sa.Float(), nullable=False), sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False)))
    with op.batch_alter_table("audit_logs") as batch:
        batch.add_column(sa.Column("organization_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_audit_logs_organization_id", "organizations", ["organization_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_audit_logs_organization_id", "audit_logs", ["organization_id"])
    for table in ("enterprise_workspaces", "organization_members", "workspace_members", "enterprise_teams", "enterprise_team_members", "enterprise_roles", "identity_providers", "approval_requests", "legal_holds", "tenant_sla_snapshots"):
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY organizations_tenant_policy ON organizations USING (created_by = current_setting('app.user_id', true) OR id = current_setting('app.organization_id', true))")
        for table in ("enterprise_workspaces", "workspace_members", "enterprise_teams", "enterprise_team_members", "enterprise_roles", "approval_requests", "legal_holds", "tenant_policies", "tenant_quotas", "tenant_sla_snapshots"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"CREATE POLICY {table}_tenant_policy ON {table} USING (organization_id = current_setting('app.organization_id', true)) WITH CHECK (organization_id = current_setting('app.organization_id', true))")
        op.execute("ALTER TABLE organization_members ENABLE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY organization_members_tenant_policy ON organization_members USING (user_id = current_setting('app.user_id', true) OR organization_id = current_setting('app.organization_id', true)) WITH CHECK (organization_id = current_setting('app.organization_id', true))")
        op.execute("ALTER TABLE identity_providers ENABLE ROW LEVEL SECURITY")
        op.execute("CREATE POLICY identity_providers_tenant_policy ON identity_providers USING (organization_id = current_setting('app.organization_id', true) OR scim_token_hash = current_setting('app.scim_token_hash', true)) WITH CHECK (organization_id = current_setting('app.organization_id', true))")


def downgrade():
    op.drop_index("ix_audit_logs_organization_id", table_name="audit_logs")
    with op.batch_alter_table("audit_logs") as batch:
        batch.drop_constraint("fk_audit_logs_organization_id", type_="foreignkey")
        batch.drop_column("organization_id")
    for table in ("tenant_sla_snapshots", "tenant_quotas", "tenant_policies", "legal_holds", "approval_requests", "identity_providers", "enterprise_roles", "enterprise_team_members", "enterprise_teams", "workspace_members", "organization_members", "enterprise_workspaces", "organizations"):
        op.drop_table(table)
