# -*- coding: utf-8 -*-
"""
智法通 V2 —— LangGraph 合同审查工作流（12 节点线性流水线）

parse_doc → split_clauses → completeness_check → classify_clauses → risk_detect →
compliance_check → consistency_check → adverse_attack → debate → risk_score →
suggestions → report_generate
"""
from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.state import ContractReviewState

logger = logging.getLogger(__name__)

NODE_ORDER = [
    ("parse_doc", nodes.parse_doc),
    ("split_clauses", nodes.split_clauses),
    ("completeness_check", nodes.completeness_check),
    ("classify_clauses", nodes.classify_clauses),
    ("risk_detect", nodes.risk_detect),
    ("compliance_check", nodes.compliance_check),
    ("consistency_check", nodes.consistency_check),
    ("adverse_attack", nodes.adverse_agent_attack),
    ("debate", nodes.debate_round),
    ("risk_score", nodes.risk_score_node),
    ("suggestions", nodes.generate_suggestions),
    ("report_generate", nodes.report_generate),
]


def _build_graph():
    builder = StateGraph(ContractReviewState)
    for name, fn in NODE_ORDER:
        builder.add_node(name, fn)
    builder.add_edge(START, NODE_ORDER[0][0])
    for i in range(len(NODE_ORDER) - 1):
        builder.add_edge(NODE_ORDER[i][0], NODE_ORDER[i + 1][0])
    builder.add_edge(NODE_ORDER[-1][0], END)
    return builder.compile()


graph = _build_graph()


class ContractReviewWorkflow:
    async def run(self, contract_content: str, contract_type: str = "") -> dict:
        initial: ContractReviewState = {
            "contract_content": contract_content or "",
            "contract_text": contract_content or "",
            "contract_type": contract_type or "",
        }
        result = await graph.ainvoke(initial)
        report = result.get("review_report")
        if not report:
            report = {
                "summary": "审查失败或合同为空，未能生成报告。",
                "overall_score": 0.0,
                "risk_level": "critical",
                "risk_clause_count": 0,
                "completeness": 0,
                "compliance": 0,
                "consistency": 0,
                "suggestions": ["请提供有效合同文本后重试。"],
                "primary_risks": [],
                "review_check": [],
                "adverse_opinions": [],
                "debate_log": [],
                "unresolved_issues": [],
                "needs_manual_review": True,
            }
        return report


contract_review_workflow = ContractReviewWorkflow()
