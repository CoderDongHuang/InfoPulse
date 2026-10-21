"""Durable storage deletion requests, intentionally independent of user lifetime."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class StorageCleanup(Base):
    __tablename__ = "storage_cleanup"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    backend: Mapped[str] = mapped_column(String(20), default="knowledge")
    storage_key: Mapped[str] = mapped_column(String(1000))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
