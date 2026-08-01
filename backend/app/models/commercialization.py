"""Stage 20 commercial operations, governance and product controls."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)


class TemplatePackage(Base):
    __tablename__ = "template_packages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80)); name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default=""); visibility: Mapped[str] = mapped_column(String(20), default="private")
    status: Mapped[str] = mapped_column(String(20), default="draft"); current_version: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT")); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("organization_id", "key", name="uq_template_package_key"),)


class TemplatePackageVersion(Base):
    __tablename__ = "template_package_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    package_id: Mapped[str] = mapped_column(ForeignKey("template_packages.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer); definition: Mapped[dict] = mapped_column(JSON, default=dict)
    change_note: Mapped[str] = mapped_column(String(500), default=""); rollback_of_version: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64)); created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT")); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("package_id", "version", name="uq_template_package_version"),)


class ApprovalFlow(Base):
    __tablename__ = "approval_flows"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160)); trigger: Mapped[str] = mapped_column(String(60)); graph: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True); version: Mapped[int] = mapped_column(Integer, default=1); created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT")); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class MetricCollector(Base):
    __tablename__ = "metric_collectors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    metric_id: Mapped[str] = mapped_column(ForeignKey("impact_metric_definitions.id", ondelete="CASCADE")); source_type: Mapped[str] = mapped_column(String(40)); config: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True); last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True)); created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))


class AttributionAudit(Base):
    __tablename__ = "attribution_audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    measurement_id: Mapped[str] = mapped_column(ForeignKey("impact_measurements.id", ondelete="CASCADE"), index=True); method: Mapped[str] = mapped_column(String(40)); assumptions: Mapped[list] = mapped_column(JSON, default=list)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict); confidence: Mapped[float] = mapped_column(Float); conclusion: Mapped[str] = mapped_column(String(30), default="correlation_only"); created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT")); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SLAPolicy(Base):
    __tablename__ = "sla_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160)); target_type: Mapped[str] = mapped_column(String(50)); target_minutes: Mapped[int] = mapped_column(Integer); warning_minutes: Mapped[int] = mapped_column(Integer)
    escalation_steps: Mapped[list] = mapped_column(JSON, default=list); enabled: Mapped[bool] = mapped_column(Boolean, default=True); created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT")); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class UsageEntitlement(Base):
    __tablename__ = "usage_entitlements"
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    plan_key: Mapped[str] = mapped_column(String(40), default="starter"); limits: Mapped[dict] = mapped_column(JSON, default=dict); feature_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active"); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


class ProductUsage(Base):
    __tablename__ = "product_usage"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    period: Mapped[str] = mapped_column(String(7)); feature: Mapped[str] = mapped_column(String(80)); quantity: Mapped[int] = mapped_column(Integer, default=0); cost_cents: Mapped[int] = mapped_column(Integer, default=0); dimensions: Mapped[dict] = mapped_column(JSON, default=dict); updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("organization_id", "period", "feature", name="uq_product_usage_feature"),)


class ConnectorExecution(Base):
    __tablename__ = "connector_executions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    installation_id: Mapped[str] = mapped_column(ForeignKey("connector_installations.id", ondelete="CASCADE")); action_id: Mapped[str | None] = mapped_column(ForeignKey("response_actions.id", ondelete="SET NULL")); provider: Mapped[str] = mapped_column(String(20)); idempotency_key: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default="pending"); response_code: Mapped[int | None] = mapped_column(Integer); external_reference: Mapped[str] = mapped_column(String(300), default=""); error: Mapped[str] = mapped_column(String(500), default=""); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key", name="uq_connector_execution_idempotency"),)
