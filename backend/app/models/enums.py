# -*- coding: utf-8 -*-
"""智法通 V2 —— 领域枚举（统一以字符串落库，便于迁移与兼容）。"""
from __future__ import annotations

import enum


class ConversationStatus(str, enum.Enum):
    ACTIVE = "active"
    DELETED = "deleted"


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContractStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    PARSING = "parsing"
    PARSED = "parsed"
    REVIEWING = "reviewing"
    REVIEWED = "reviewed"
    FAILED = "failed"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentSource(str, enum.Enum):
    UPLOAD = "upload"
    CRAWL = "crawl"
    MANUAL = "manual"
    API = "api"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentEffectiveness(str, enum.Enum):
    """法条/法规效力状态（时间旅行查询语义）。"""

    EFFECTIVE = "有效"
    PARTIALLY_REVISED = "部分修订"
    ABOLISHED = "已废止"


class NotificationType(str, enum.Enum):
    SYSTEM = "system"
    CONTRACT = "contract"
    LEGAL_UPDATE = "legal_update"
    QA = "qa"
    WARNING = "warning"
