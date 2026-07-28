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

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def uuid_string() -> str:
    return str(uuid.uuid4())


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
