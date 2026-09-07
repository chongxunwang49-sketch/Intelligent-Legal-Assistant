# -*- coding: utf-8 -*-
"""法律知识库模型（文档 / 分块），含时间旅行扩展字段。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, naive_utcnow
from app.models.enums import (
    DocumentEffectiveness,
    DocumentSource,
    DocumentStatus,
)


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    doc_type: Mapped[str] = mapped_column(String(50), index=True, default="法律")
    source: Mapped[str] = mapped_column(
        String(20), default=DocumentSource.UPLOAD.value
    )
    file_path: Mapped[str] = mapped_column(String(500), default="")
    file_name: Mapped[str] = mapped_column(String(255), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=DocumentStatus.PENDING.value
    )
    indexing_progress: Mapped[int] = mapped_column(Integer, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    uploaded_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    publish_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # ---------- 时间旅行 / 版本化扩展 ----------
    # 生效/废止时间点（naive UTC）；NULL 表示自始生效 / 至今有效
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    abolished_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 效力状态：有效 / 部分修订 / 已废止
    effectiveness: Mapped[str] = mapped_column(
        String(20), default=DocumentEffectiveness.EFFECTIVE.value, index=True
    )
    is_effective: Mapped[bool] = mapped_column(Boolean, default=True)
    # 文本版本标识，如 "2012修正"
    version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=naive_utcnow, onupdate=naive_utcnow
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_chunks_doc_idx", "document_id", "chunk_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("legal_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text)
    vector_id: Mapped[str] = mapped_column(String(100), unique=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    start_char: Mapped[int] = mapped_column(Integer, default=0)
    end_char: Mapped[int] = mapped_column(Integer, default=0)
    # 条款级结构化（GraphRAG 实体链接用）
    law_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    article_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    # Chroma 写入元数据的 JSON 快照
    chunk_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
