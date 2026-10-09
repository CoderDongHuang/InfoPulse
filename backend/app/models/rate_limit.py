"""Shared fixed-window counters; no per-process security state."""
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    requests: Mapped[int] = mapped_column(Integer, default=0)
