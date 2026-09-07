# -*- coding: utf-8 -*-
"""模型包：导入全部模型，供 Base.metadata.create_all 建表。"""
from app.models.user import (
    Permission,
    Role,
    User,
    role_permission,
    user_role,
)
from app.models.qa import Conversation, Message, QAFeedback
from app.models.contract import Contract, ReviewReport, RiskClause
from app.models.knowledge import LegalDocument, DocumentChunk
from app.models.analysis import QueryLog, CitationStat
from app.models.notification import Notification
from app.models.enums import (
    ContractStatus,
    ConversationStatus,
    DocumentEffectiveness,
    DocumentSource,
    DocumentStatus,
    MessageRole,
    NotificationType,
    RiskLevel,
)

__all__ = [
    "User",
    "Role",
    "Permission",
    "role_permission",
    "user_role",
    "Conversation",
    "Message",
    "QAFeedback",
    "Contract",
    "ReviewReport",
    "RiskClause",
    "LegalDocument",
    "DocumentChunk",
    "QueryLog",
    "CitationStat",
    "Notification",
    "ContractStatus",
    "ConversationStatus",
    "DocumentEffectiveness",
    "DocumentSource",
    "DocumentStatus",
    "MessageRole",
    "NotificationType",
    "RiskLevel",
]
