"""Core intelligence-domain models introduced by the platform refactor."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_string() -> str:
    return str(uuid.uuid4())


class PortableVector(TypeDecorator):
    """Use pgvector in PostgreSQL and JSON in SQLite development/tests."""
    impl = JSON
    cache_ok = True
    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            return dialect.type_descriptor(Vector(96))
        return dialect.type_descriptor(JSON())


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    encrypted_credentials: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    health_status: Mapped[str] = mapped_column(String(20), default="unknown", nullable=False)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    sync_runs = relationship("SyncRun", back_populates="source", cascade="all, delete-orphan")
    content_items = relationship("ContentItem", back_populates="source")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), index=True)
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    cursor: Mapped[dict] = mapped_column(JSON, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnostic_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    source = relationship("DataSource", back_populates="sync_runs")


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_content_source_external"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    source_id: Mapped[str] = mapped_column(ForeignKey("data_sources.id", ondelete="RESTRICT"), index=True)
    external_id: Mapped[str] = mapped_column(String(500), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str] = mapped_column(String(300), default="")
    author_external_id: Mapped[str] = mapped_column(String(500), default="")
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), default="und", index=True)
    region: Mapped[str] = mapped_column(String(80), default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    view_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    comment_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    like_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    share_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    is_original: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    sentiment: Mapped[str] = mapped_column(String(20), default="unknown", index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    entities: Mapped[list] = mapped_column(JSON, default=list)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    source = relationship("DataSource", back_populates="content_items")
    event_links = relationship("EventContent", back_populates="content", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(600), unique=True, nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(80), default="uncategorized", index=True)
    status: Mapped[str] = mapped_column(String(20), default="detected", index=True)
    heat_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    risk_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    manual_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    risk_notes: Mapped[str] = mapped_column(Text, default="")

    content_links = relationship("EventContent", back_populates="event", cascade="all, delete-orphan")


class EventContent(Base):
    __tablename__ = "event_contents"

    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), primary_key=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    added_by: Mapped[str] = mapped_column(String(20), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    event = relationship("Event", back_populates="content_links")
    content = relationship("ContentItem", back_populates="event_links")


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    query: Mapped[str] = mapped_column(String(500), default="")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EventEntity(Base):
    __tablename__ = "event_entities"
    __table_args__ = (UniqueConstraint("event_id", "name", name="uq_event_entity_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(40), default="keyword")
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    before_data: Mapped[dict] = mapped_column(JSON, default=dict)
    after_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id", name="uq_favorite_target"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class RecentView(Base):
    __tablename__ = "recent_views"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id", name="uq_recent_view_target"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)

class WatchTopic(Base):
    __tablename__ = "watch_topics"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_watch_topic_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

class ChannelFollow(Base):
    __tablename__ = "channel_follows"
    __table_args__ = (UniqueConstraint("user_id", "channel_id", name="uq_channel_follow"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[str] = mapped_column(String(60), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class RecommendationFeedback(Base):
    __tablename__ = "recommendation_feedback"
    __table_args__ = (UniqueConstraint("user_id", "target_type", "target_id", name="uq_recommendation_feedback"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_type: Mapped[str] = mapped_column(String(20), default="content")
    target_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class Analysis(Base):
    __tablename__ = "analyses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("analyses.id", ondelete="SET NULL"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    analysis_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="running")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evidence_coverage: Mapped[float] = mapped_column(Float, default=0)
    model_name: Mapped[str] = mapped_column(String(120), default="")
    prompt_version: Mapped[str] = mapped_column(String(30), default="analysis-v1")
    data_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

class AnalysisCitation(Base):
    __tablename__ = "analysis_citations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="RESTRICT"), index=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[dict] = mapped_column(JSON, default=dict)
    claim_index: Mapped[int] = mapped_column(Integer, nullable=False)

class Conversation(Base):
    __tablename__="conversations"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_string)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    title: Mapped[str]=mapped_column(String(200),default="新会话")
    event_id: Mapped[str|None]=mapped_column(ForeignKey("events.id",ondelete="SET NULL"),index=True)
    context_config: Mapped[dict]=mapped_column(JSON,default=dict)
    model_name: Mapped[str]=mapped_column(String(120),default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,onupdate=utc_now)
    deleted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class AgentMessage(Base):
    __tablename__="agent_messages"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_string)
    conversation_id: Mapped[str]=mapped_column(ForeignKey("conversations.id",ondelete="CASCADE"),index=True)
    role: Mapped[str]=mapped_column(String(20),nullable=False)
    content: Mapped[str]=mapped_column(Text,default="")
    status: Mapped[str]=mapped_column(String(20),default="completed")
    tool_name: Mapped[str]=mapped_column(String(60),default="")
    tool_payload: Mapped[dict]=mapped_column(JSON,default=dict)
    model_name: Mapped[str]=mapped_column(String(120),default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,index=True)

class MessageCitation(Base):
    __tablename__="message_citations"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_string)
    message_id: Mapped[str]=mapped_column(ForeignKey("agent_messages.id",ondelete="CASCADE"),index=True)
    content_item_id: Mapped[str]=mapped_column(ForeignKey("content_items.id",ondelete="RESTRICT"),index=True)
    quote: Mapped[str]=mapped_column(Text,nullable=False)
    locator: Mapped[dict]=mapped_column(JSON,default=dict)
    claim_index: Mapped[int]=mapped_column(Integer,default=0)

class MessageFeedback(Base):
    __tablename__="message_feedback"
    __table_args__=(UniqueConstraint("message_id","user_id",name="uq_message_feedback"),)
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_string)
    message_id: Mapped[str]=mapped_column(ForeignKey("agent_messages.id",ondelete="CASCADE"),index=True)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    rating: Mapped[str]=mapped_column(String(10),nullable=False)
    reason: Mapped[str]=mapped_column(String(500),default="")
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)

class Report(Base):
 __tablename__="reports"
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_string);user_id:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True);title:Mapped[str]=mapped_column(String(300));report_type:Mapped[str]=mapped_column(String(30));status:Mapped[str]=mapped_column(String(20),default="draft");source_config:Mapped[dict]=mapped_column(JSON,default=dict);current_version_id:Mapped[str|None]=mapped_column(String(36));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now);updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now,onupdate=utc_now);deleted_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
class ReportVersion(Base):
 __tablename__="report_versions";__table_args__=(UniqueConstraint("report_id","version_number",name="uq_report_version"),)
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_string);report_id:Mapped[str]=mapped_column(ForeignKey("reports.id",ondelete="CASCADE"),index=True);version_number:Mapped[int]=mapped_column(Integer);content_markdown:Mapped[str]=mapped_column(Text,default="");structured_content:Mapped[dict]=mapped_column(JSON,default=dict);citations:Mapped[list]=mapped_column(JSON,default=list);created_by:Mapped[str]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"));created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)
class ReportExport(Base):
 __tablename__="report_exports"
 id:Mapped[str]=mapped_column(String(36),primary_key=True,default=uuid_string);report_id:Mapped[str]=mapped_column(ForeignKey("reports.id",ondelete="CASCADE"),index=True);version_id:Mapped[str]=mapped_column(ForeignKey("report_versions.id",ondelete="CASCADE"));format:Mapped[str]=mapped_column(String(20));status:Mapped[str]=mapped_column(String(20),default="queued");storage_key:Mapped[str]=mapped_column(String(1000),default="");file_size:Mapped[int]=mapped_column(BigInteger,default=0);error_message:Mapped[str]=mapped_column(Text,default="");created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utc_now)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_type: Mapped[str] = mapped_column(String(30), nullable=False)
    target_id: Mapped[str | None] = mapped_column(String(36), index=True)
    query: Mapped[str] = mapped_column(String(500), default="")
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    channels: Mapped[list] = mapped_column(JSON, default=lambda: ["in_app"])
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    task_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[str | None] = mapped_column(ForeignKey("subscriptions.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule: Mapped[dict] = mapped_column(JSON, default=dict)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    max_concurrency: Mapped[int] = mapped_column(Integer, default=1)
    cost_limit: Mapped[float] = mapped_column(Float, default=1.0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0.0)
    high_risk: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmation_status: Mapped[str] = mapped_column(String(20), default="not_required")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class TaskRun(Base):
    __tablename__ = "task_runs"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_task_run_idempotency"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    task_id: Mapped[str] = mapped_column(ForeignKey("agent_tasks.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    trigger: Mapped[str] = mapped_column(String(20), default="schedule")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    logs: Mapped[list] = mapped_column(JSON, default=list)
    error_message: Mapped[str] = mapped_column(Text, default="")
    diagnostic_id: Mapped[str] = mapped_column(String(36), default="")
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    notification_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), default="info")
    status: Mapped[str] = mapped_column(String(20), default="unread", index=True)
    group_key: Mapped[str] = mapped_column(String(200), default="", index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    scheduled_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preference_user"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Shanghai")
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_end: Mapped[str] = mapped_column(String(5), default="08:00")
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    email_address: Mapped[str] = mapped_column(String(320), default="")
    webhook_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_url: Mapped[str] = mapped_column(String(1000), default="")
    webhook_secret: Mapped[str] = mapped_column(String(300), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class DeliveryAttempt(Base):
    __tablename__ = "delivery_attempts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    notification_id: Mapped[str] = mapped_column(ForeignKey("notifications.id", ondelete="CASCADE"), index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    response_code: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str] = mapped_column(Text, default="")
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_url: Mapped[str] = mapped_column(String(2000), default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    byte_size: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    active_version_id: Mapped[str | None] = mapped_column(String(36), index=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class KnowledgeDocumentVersion(Base):
    __tablename__ = "knowledge_document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number", name="uq_knowledge_document_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document_versions.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    knowledge_base_id: Mapped[str] = mapped_column(ForeignKey("knowledge_bases.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    paragraph_index: Mapped[int | None] = mapped_column(Integer)
    heading: Mapped[str] = mapped_column(String(500), default="")
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list] = mapped_column(PortableVector(), default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class KnowledgeProcessingRun(Base):
    __tablename__ = "knowledge_processing_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    stage: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    error_message: Mapped[str] = mapped_column(Text, default="")
    diagnostic_id: Mapped[str] = mapped_column(String(36), default=uuid_string)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeCitation(Base):
    __tablename__ = "knowledge_citations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    message_id: Mapped[str] = mapped_column(ForeignKey("agent_messages.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("knowledge_chunks.id", ondelete="RESTRICT"), index=True)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    claim_index: Mapped[int] = mapped_column(Integer, default=0)


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("entity_type", "normalized_name", name="uq_entity_type_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (UniqueConstraint("entity_id", "normalized_alias", name="uq_entity_alias"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(16), default="und")


class EventEntityLink(Base):
    __tablename__ = "event_entity_links"
    __table_args__ = (UniqueConstraint("event_id", "entity_id", "role", name="uq_event_entity_link"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(40), default="mentioned")
    mention_count: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evidence_content_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class EntityRelation(Base):
    __tablename__ = "entity_relations"
    __table_args__ = (UniqueConstraint("event_id", "from_entity_id", "to_entity_id", "relation_type", name="uq_entity_relation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    from_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    to_entity_id: Mapped[str] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evidence_content_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(20), default="system")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PropagationNode(Base):
    __tablename__ = "propagation_nodes"
    __table_args__ = (UniqueConstraint("event_id", "content_item_id", name="uq_propagation_event_content"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    content_item_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(30), default="media")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    influence_score: Mapped[float] = mapped_column(Float, default=0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class PropagationEdge(Base):
    __tablename__ = "propagation_edges"
    __table_args__ = (UniqueConstraint("from_node_id", "to_node_id", "relation_type", name="uq_propagation_edge"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    from_node_id: Mapped[str] = mapped_column(ForeignKey("propagation_nodes.id", ondelete="CASCADE"), index=True)
    to_node_id: Mapped[str] = mapped_column(ForeignKey("propagation_nodes.id", ondelete="CASCADE"), index=True)
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    evidence_content_id: Mapped[str] = mapped_column(ForeignKey("content_items.id", ondelete="RESTRICT"), index=True)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(20), default="system")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GraphQualitySnapshot(Base):
    __tablename__ = "graph_quality_snapshots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), index=True)
    entity_precision: Mapped[float] = mapped_column(Float, default=0)
    evidence_coverage: Mapped[float] = mapped_column(Float, default=0)
    verified_ratio: Mapped[float] = mapped_column(Float, default=0)
    unresolved_count: Mapped[int] = mapped_column(Integer, default=0)
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
