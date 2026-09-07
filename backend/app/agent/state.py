# -*- coding: utf-8 -*-
"""智法通 V2 —— LangGraph 合同审查状态定义（线性流水线，无并行写冲突）。"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class ContractReviewState(TypedDict, total=False):
    # 输入
    contract_content: str
    contract_text: str
    contract_type: str
    # 解析
    parties: list[str]
    amount: Optional[float]
    clauses: list[dict]
    clauses_count: int
    # 完整性
    completeness_missing: list[str]
    completeness_score: float
    # 分类
    clause_categories: list[dict]
    # 风险
    risk_clauses: list[dict]
    max_risk_level: str
    # 合规 / 一致性
    compliance_issues: list[dict]
    compliance_score: float
    consistency_issues: list[dict]
    consistency_score: float
    # 对抗
    primary_risks: list[dict]
    review_check: list[dict]
    adverse_opinions: list[dict]
    debate_log: list[dict]
    unresolved_issues: list[str]
    adverse_opinion_count: int
    unresolved_count: int
    # 评分 / 建议
    risk_score: float
    overall_score: float
    risk_level: str
    suggestions: list[str]
    # 报告
    summary: str
    review_report: dict[str, Any]
    error: Optional[str]
