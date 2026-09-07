# -*- coding: utf-8 -*-
"""合同审查模型（合同 / 审查报告 / 风险条款）。"""
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
from app.models.enums import ContractStatus, RiskLevel


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="未命名合同")
    file_name: Mapped[str] = mapped_column(String(255), default="")
    file_path: Mapped[str] = mapped_column(String(500), default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    file_type: Mapped[str] = mapped_column(String(20), default="")
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default=ContractStatus.UPLOADED.value
    )
    contract_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    party_a: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    party_b: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=naive_utcnow, onupdate=naive_utcnow
    )


class ReviewReport(Base):
    __tablename__ = "review_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    contract_id: Mapped[int] = mapped_column(
        ForeignKey("contracts.id", ondelete="CASCADE"), index=True
    )
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_level: Mapped[str] = mapped_column(
        String(20), default=RiskLevel.MEDIUM.value
    )
    risk_clause_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 三维度健康分（越高越健康，0-100）
    completeness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    compliance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    consistency: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    review_duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # V4.0 多 Agent 对抗式审查字段（Text/JSON）
    primary_risks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_check: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    adverse_opinions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    debate_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unresolved_issues: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    adverse_opinion_count: Mapped[int] = mapped_column(Integer, default=0)
    unresolved_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)


class RiskClause(Base):
    __tablename__ = "risk_clauses"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        ForeignKey("review_reports.id", ondelete="CASCADE"), index=True
    )
    clause_index: Mapped[int] = mapped_column(Integer, default=0)
    original_text: Mapped[str] = mapped_column(Text)
    risk_type: Mapped[str] = mapped_column(String(100), default="")
    risk_level: Mapped[str] = mapped_column(
        String(20), default=RiskLevel.MEDIUM.value
    )
    # risk_score 0-1，越高越危险
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggestion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    legal_basis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
