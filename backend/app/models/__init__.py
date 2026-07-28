"""
InfoPulse — Models Package
===========================
Import all models here to ensure they are registered with SQLAlchemy's
Base metadata before any relationships are resolved.
"""

from app.models.user import User
from app.models.analysis_history import AnalysisHistory
from app.models.intelligence import (
    AuditLog, ChannelFollow, ContentItem, DataSource, Event, EventContent, EventEntity, Favorite,
    RecentView, RecommendationFeedback, SavedSearch, SyncRun, WatchTopic,
)

__all__ = [
    "User", "AnalysisHistory", "DataSource", "SyncRun", "ContentItem", "Event", "EventContent",
    "SavedSearch", "EventEntity", "AuditLog", "Favorite", "RecentView", "WatchTopic",
    "ChannelFollow", "RecommendationFeedback",
]
