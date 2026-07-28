"""
InfoPulse — Analysis History Model
====================================
SQLAlchemy ORM model for the `analysis_histories` table.
Records every analysis task a user runs.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AnalysisHistory(Base):
    __tablename__ = "analysis_histories"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    module: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Module name: insight / mouthpiece / timeline / hot_search",
    )
    input_params: Mapped[dict] = mapped_column(JSON, default=dict)
    output_result: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        comment="Status: pending / running / completed / failed",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="histories")

    def __repr__(self) -> str:
        return f"<AnalysisHistory(id={self.id}, module={self.module}, status={self.status})>"
