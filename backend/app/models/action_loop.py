"""Tenant-scoped response actions and impact validation records."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

def uid(): return str(uuid.uuid4())
def now(): return datetime.now(timezone.utc)

class ResponseAction(Base):
    __tablename__ = "response_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str|None] = mapped_column(ForeignKey("enterprise_workspaces.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str|None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), index=True)
    scenario_id: Mapped[str|None] = mapped_column(ForeignKey("scenarios.id", ondelete="SET NULL"), index=True)
    decision_room_id: Mapped[str|None] = mapped_column(ForeignKey("decision_rooms.id", ondelete="SET NULL"), index=True)
    title: Mapped[str] = mapped_column(String(300)); description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    approved_by: Mapped[str|None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    due_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True)); sla_minutes: Mapped[int|None] = mapped_column(Integer)
    budget_cents: Mapped[int] = mapped_column(Integer, default=0); spent_cents: Mapped[int] = mapped_column(Integer, default=0)
    escalation_policy: Mapped[dict] = mapped_column(JSON, default=dict); stop_conditions: Mapped[list] = mapped_column(JSON, default=list)
    dependency_ids: Mapped[list] = mapped_column(JSON, default=list); evidence_content_ids: Mapped[list] = mapped_column(JSON, default=list)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium"); completed_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True)); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ActionStep(Base):
    __tablename__ = "action_steps"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); action_id: Mapped[str] = mapped_column(ForeignKey("response_actions.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer); channel: Mapped[str] = mapped_column(String(40)); tool_key: Mapped[str|None] = mapped_column(String(120)); payload: Mapped[dict] = mapped_column(JSON, default=dict); requires_approval: Mapped[bool] = mapped_column(default=False); status: Mapped[str] = mapped_column(String(20), default="pending"); error_message: Mapped[str] = mapped_column(Text, default=""); started_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True)); finished_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

class ActionRun(Base):
    __tablename__ = "action_runs"; __table_args__ = (UniqueConstraint("action_id", "idempotency_key", name="uq_action_run_idempotency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); action_id: Mapped[str] = mapped_column(ForeignKey("response_actions.id", ondelete="CASCADE"), index=True); idempotency_key: Mapped[str] = mapped_column(String(200)); status: Mapped[str] = mapped_column(String(20), default="running"); attempt: Mapped[int] = mapped_column(Integer, default=1); output: Mapped[dict] = mapped_column(JSON, default=dict); error_message: Mapped[str] = mapped_column(Text, default=""); started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now); finished_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True))

class ActionReceipt(Base):
    __tablename__ = "action_receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); action_id: Mapped[str] = mapped_column(ForeignKey("response_actions.id", ondelete="CASCADE"), index=True); run_id: Mapped[str|None] = mapped_column(ForeignKey("action_runs.id", ondelete="SET NULL")); step_id: Mapped[str|None] = mapped_column(ForeignKey("action_steps.id", ondelete="SET NULL")); channel: Mapped[str] = mapped_column(String(40)); external_reference: Mapped[str] = mapped_column(String(300), default=""); response_code: Mapped[int|None] = mapped_column(Integer); receipt_payload: Mapped[dict] = mapped_column(JSON, default=dict); evidence_content_ids: Mapped[list] = mapped_column(JSON, default=list); received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ImpactMetricDefinition(Base):
    __tablename__ = "impact_metric_definitions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); key: Mapped[str] = mapped_column(String(100)); name: Mapped[str] = mapped_column(String(200)); unit: Mapped[str] = mapped_column(String(40)); direction: Mapped[str] = mapped_column(String(20), default="higher_is_better"); definition: Mapped[dict] = mapped_column(JSON, default=dict); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ImpactMeasurement(Base):
    __tablename__ = "impact_measurements"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); action_id: Mapped[str] = mapped_column(ForeignKey("response_actions.id", ondelete="CASCADE"), index=True); metric_id: Mapped[str] = mapped_column(ForeignKey("impact_metric_definitions.id", ondelete="CASCADE")); before_value: Mapped[float] = mapped_column(Float); after_value: Mapped[float] = mapped_column(Float); attribution_confidence: Mapped[float] = mapped_column(Float, default=0); attribution_boundary: Mapped[str] = mapped_column(Text); source_content_ids: Mapped[list] = mapped_column(JSON, default=list); notes: Mapped[str] = mapped_column(Text, default=""); observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ActionReview(Base):
    __tablename__ = "action_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); action_id: Mapped[str] = mapped_column(ForeignKey("response_actions.id", ondelete="CASCADE"), index=True); reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT")); outcome: Mapped[str] = mapped_column(String(30)); failure_mode: Mapped[str] = mapped_column(String(120), default=""); lessons: Mapped[str] = mapped_column(Text, default=""); stop_condition_met: Mapped[bool] = mapped_column(default=False); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class AnonymousBenchmark(Base):
    __tablename__ = "anonymous_benchmarks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); metric_key: Mapped[str] = mapped_column(String(100)); cohort: Mapped[str] = mapped_column(String(100)); sample_size: Mapped[int] = mapped_column(Integer); aggregate_value: Mapped[float] = mapped_column(Float); k_anonymity: Mapped[int] = mapped_column(Integer, default=5); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ActionDrill(Base):
    __tablename__ = "action_drills"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); action_id: Mapped[str|None] = mapped_column(ForeignKey("response_actions.id", ondelete="SET NULL")); drill_type: Mapped[str] = mapped_column(String(50)); input_snapshot: Mapped[dict] = mapped_column(JSON, default=dict); expected_result: Mapped[dict] = mapped_column(JSON, default=dict); actual_result: Mapped[dict] = mapped_column(JSON, default=dict); status: Mapped[str] = mapped_column(String(20), default="planned"); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ActionAudit(Base):
    __tablename__ = "action_audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); action_id: Mapped[str|None] = mapped_column(ForeignKey("response_actions.id", ondelete="SET NULL")); actor_id: Mapped[str|None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL")); action: Mapped[str] = mapped_column(String(80)); details: Mapped[dict] = mapped_column(JSON, default=dict); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class ActionTemplate(Base):
    __tablename__ = "action_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid); organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True); name: Mapped[str] = mapped_column(String(200)); version: Mapped[int] = mapped_column(Integer, default=1); definition: Mapped[dict] = mapped_column(JSON, default=dict); status: Mapped[str] = mapped_column(String(20), default="active"); created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT")); created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
