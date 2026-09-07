# -*- coding: utf-8 -*-
"""数据分析模型（查询日志 / 法条引用统计）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, naive_utcnow


class QueryLog(Base):
    __tablename__ = "query_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    query_text: Mapped[str] = mapped_column(Text)
    rewritten_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    sub_queries: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    retrieved_count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    self_eval_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # 沿用旧表类型：Integer(0/1)，避免异构
    is_streaming: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback_score: Mapped[int] = mapped_column(Integer, default=0)  # 1/-1/0
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow, index=True)


class CitationStat(Base):
    __tablename__ = "citation_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("legal_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("document_chunks.id", ondelete="SET NULL"), nullable=True
    )
    stat_date: Mapped[datetime] = mapped_column(DateTime, index=True)  # 按天
    citation_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
