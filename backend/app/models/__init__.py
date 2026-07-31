"""
InfoPulse — Models Package
===========================
Import all models here to ensure they are registered with SQLAlchemy's
Base metadata before any relationships are resolved.
"""

from app.models.user import User
from app.models.analysis_history import AnalysisHistory
from app.models.enterprise import ApprovalRequest, CustomRole, IdentityProvider, LegalHold, Organization, OrganizationMember, Team, TeamMember, TenantPolicy, TenantQuota, TenantSLA, Workspace, WorkspaceMember
from app.models.platform import APIUsageMeter, BillingAccount, ConnectorDefinition, ConnectorInstallation, DeveloperAPIKey, OAuthAccessGrant, OAuthApplication, OAuthAuthorizationCode, SecurityReview, SubscriptionPlan, WebhookDelivery, WebhookEndpoint
from app.models.orchestration import AgentMemory, EvaluationDataset, EvaluationRun, ModelRoute, OrchestrationAudit, PromptDefinition, ToolDefinition, ToolPolicy, Workflow, WorkflowApproval, WorkflowRun, WorkflowStepRun, WorkflowTemplate, WorkflowVersion
from app.models.multimodal import CollaborationAudit,CollaborationComment,CollaborationTicket,CollaborativeChange,CollaborativeDocument,LiveStream,LiveUpdate,MediaAsset,MediaCitation,MediaEvidence,MediaProcessingRun
from app.models.global_intelligence import ContentTranslation,GlobalNarrative,NarrativeSignal,Scenario,DecisionRoom,DecisionOption,DecisionAudit
from app.models.intelligence import (
    AgentMessage, Analysis, AnalysisCitation, AuditLog, ChannelFollow, ContentItem, Conversation, DataSource, Event, EventContent, EventEntity, Favorite, MessageCitation, MessageFeedback,
    AgentTask, DeliveryAttempt, Notification, NotificationPreference, RecentView, RecommendationFeedback,
    Report, ReportExport, ReportVersion, SavedSearch, Subscription, SyncRun, TaskRun, WatchTopic,
    KnowledgeBase, KnowledgeDocument, KnowledgeDocumentVersion, KnowledgeChunk, KnowledgeProcessingRun, KnowledgeCitation,
    Entity, EntityAlias, EventEntityLink, EntityRelation, PropagationNode, PropagationEdge, GraphQualitySnapshot,
    AlertRule, AlertIncident, AlertAction, AlertReplayRun, BIQueryHistory, ModelUsage, ProductEvent, UserFeedback, ReleaseRecord,
)

__all__ = [
    "User", "AnalysisHistory", "DataSource", "SyncRun", "ContentItem", "Event", "EventContent",
    "SavedSearch", "EventEntity", "AuditLog", "Favorite", "RecentView", "WatchTopic",
    "ChannelFollow", "RecommendationFeedback", "Analysis", "AnalysisCitation", "Conversation", "AgentMessage", "MessageCitation", "MessageFeedback", "Report", "ReportVersion", "ReportExport",
    "Subscription", "AgentTask", "TaskRun", "Notification", "NotificationPreference", "DeliveryAttempt",
    "KnowledgeBase", "KnowledgeDocument", "KnowledgeDocumentVersion", "KnowledgeChunk", "KnowledgeProcessingRun", "KnowledgeCitation",
    "Entity", "EntityAlias", "EventEntityLink", "EntityRelation", "PropagationNode", "PropagationEdge", "GraphQualitySnapshot",
    "AlertRule", "AlertIncident", "AlertAction", "AlertReplayRun", "BIQueryHistory", "ModelUsage", "ProductEvent", "UserFeedback", "ReleaseRecord",
    "Organization", "Workspace", "OrganizationMember", "WorkspaceMember", "Team", "TeamMember", "CustomRole", "IdentityProvider", "ApprovalRequest", "LegalHold", "TenantPolicy", "TenantQuota", "TenantSLA",
    "DeveloperAPIKey", "OAuthApplication", "OAuthAuthorizationCode", "OAuthAccessGrant", "WebhookEndpoint", "WebhookDelivery", "ConnectorDefinition", "ConnectorInstallation", "SecurityReview", "SubscriptionPlan", "BillingAccount", "APIUsageMeter",
    "ToolDefinition", "ToolPolicy", "PromptDefinition", "ModelRoute", "Workflow", "WorkflowVersion", "WorkflowRun", "WorkflowStepRun", "WorkflowApproval", "AgentMemory", "EvaluationDataset", "EvaluationRun", "WorkflowTemplate", "OrchestrationAudit",
    "MediaAsset","MediaProcessingRun","MediaEvidence","MediaCitation","LiveStream","LiveUpdate","CollaborativeDocument","CollaborativeChange","CollaborationComment","CollaborationTicket","CollaborationAudit",
    "ContentTranslation","GlobalNarrative","NarrativeSignal","Scenario","DecisionRoom","DecisionOption","DecisionAudit",
]
