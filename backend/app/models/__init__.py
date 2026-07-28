"""
InfoPulse — Models Package
===========================
Import all models here to ensure they are registered with SQLAlchemy's
Base metadata before any relationships are resolved.
"""

from app.models.user import User
from app.models.analysis_history import AnalysisHistory
from app.models.intelligence import (
    AgentMessage, Analysis, AnalysisCitation, AuditLog, ChannelFollow, ContentItem, Conversation, DataSource, Event, EventContent, EventEntity, Favorite, MessageCitation, MessageFeedback,
    RecentView, RecommendationFeedback, Report, ReportExport, ReportVersion, SavedSearch, SyncRun, WatchTopic,
)

__all__ = [
    "User", "AnalysisHistory", "DataSource", "SyncRun", "ContentItem", "Event", "EventContent",
    "SavedSearch", "EventEntity", "AuditLog", "Favorite", "RecentView", "WatchTopic",
    "ChannelFollow", "RecommendationFeedback", "Analysis", "AnalysisCitation", "Conversation", "AgentMessage", "MessageCitation", "MessageFeedback", "Report", "ReportVersion", "ReportExport",
]
