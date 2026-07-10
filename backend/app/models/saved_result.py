"""
InfoPulse — Saved Result Model
================================
SQLAlchemy ORM model for the `saved_results` table.
Users can bookmark/favorite analysis results.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SavedResult(Base):
    __tablename__ = "saved_results"

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
    history_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("analysis_histories.id", ondelete="CASCADE"),
        nullable=False,
    )
    note: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    user = relationship("User", back_populates="saved_results")
    history = relationship("AnalysisHistory", back_populates="saved_results")

    def __repr__(self) -> str:
        return f"<SavedResult(id={self.id}, history_id={self.history_id})>"
