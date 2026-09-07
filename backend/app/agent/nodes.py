# -*- coding: utf-8 -*-
"""
智法通 V2 —— LangGraph 合同审查节点（12 节点，规则+工具驱动，稳健确定性）

parse_doc → split_clauses →(completeness_check, classify_clauses)→ risk_detect →
(compliance_check, consistency_check)→ adverse_attack → debate → risk_score →
suggestions → report_generate
"""
from __future__ import annotations

import re
from typing import Any

from app.agent import rules as R
from app.agent.state import ContractReviewState
from app.agent.tools import call_tool

_CN_NUM_HEAD = re.compile(
    r"^\s*(第[零一二三四五六七八九十百千0-9]+条|第[零一二三四五六七八九十百千0-9]+章|[一二三四五六七八九十]+、|\d+[、.])",
)
_PARTY_RE = re.compile(r"甲方[：:)\s]*([一-龥（）()A-Za-z0-9·公司厂店集团]{2,40})")
_PARTY2_RE = re.compile(r"乙方[：:)\s]*([一-龥（）()A-Za-z0-9·公司厂店集团]{2,40})")
_AMOUNT_RE = re.compile(r"((?:人民币)?[¥￥]?)\s*(\d[\d,，.]*)\s*(万|万元|元|圆)?")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def split_clauses_text(text: str) -> list[dict]:
    """按“第X条 / 中文编号”切分条款。"""
    text = (text or "").strip()
    if not text:
        return []
    # 定位所有条/款级标题
    markers = []
    for m in re.finditer(r"(?m)(?=^\s*(?:第[零一二三四五六七八九十百千0-9]+条|[一二三四五六七八九十]+、|\d+[、.])\s*)", text):
        markers.append(m.start())
    if not markers:
        return [{"index": 0, "header": "", "text": _clean(text)[:4000]}]
    if markers[0] != 0:
        markers = [0] + markers
    clauses = []
    for i, start in enumerate(markers):
        end = markers[i + 1] if i + 1 < len(markers) else len(text)
        seg = text[start:end].strip()
        if len(seg) < 4:
            continue
        seg_clean = _clean(seg)
        head_m = _CN_NUM_HEAD.match(seg_clean)
        header = head_m.group(0).strip() if head_m else ""
        clauses.append({"index": len(clauses), "header": header, "text": seg_clean})
    return clauses[:80]


# ---------------- 节点 1：解析 ----------------
async def parse_doc(state: ContractReviewState) -> dict:
    content = state.get("contract_content") or state.get("contract_text") or ""
    # 保留换行以支持按“第X条”切分；仅统一换行符与首尾空白
    text = re.sub(r"\r\n?", "\n", content or "").strip()
    flat = _clean(text)
    ctype = R.detect_contract_type(flat)
    parties = []
    m = _PARTY_RE.search(flat)
    if m:
        parties.append(f"甲方：{_clean(m.group(1))}")
    m2 = _PARTY2_RE.search(flat)
    if m2:
        parties.append(f"乙方：{_clean(m2.group(1))}")
    amount = None
    am = _AMOUNT_RE.search(flat)
    if am:
        try:
            num = float(am.group(2).replace(",", "").replace("，", ""))
            unit = am.group(3) or ""
            amount = num * 10000 if "万" in unit else num
        except Exception:
            amount = None
    return {
        "contract_text": text,
        "contract_type": ctype,
        "parties": parties,
        "amount": amount,
    }


# ---------------- 节点 2：切分条款 ----------------
async def split_clauses(state: ContractReviewState) -> dict:
    text = state.get("contract_text") or state.get("contract_content") or ""
    clauses = split_clauses_text(text)
    return {"clauses": clauses, "clauses_count": len(clauses)}


# ---------------- 节点 3：完整性审查 ----------------
async def completeness_check(state: ContractReviewState) -> dict:
    text = state.get("contract_text") or ""
    ctype = state.get("contract_type") or "买卖"
    required = R.required_clauses(ctype)
    missing = [k for k in required if k not in text]
    score = max(0.0, 100.0 - 8.0 * len(missing))
    return {"completeness_missing": missing, "completeness_score": round(score, 1)}


# ---------------- 节点 4：条款分类（供报告展示） ----------------
async def classify_clauses(state: ContractReviewState) -> dict:
    cats: list[dict] = []
    for cl in state.get("clauses", []):
        t = cl.get("text", "")
        if any(k in t for k in ["付款", "价款", "价格", "支付", "费用", "报酬"]):
            cat = "付款与价款"
        elif any(k in t for k in ["交付", "验收", "交付时间", "交货", "到货"]):
            cat = "交付与验收"
        elif any(k in t for k in ["违约", "赔偿", "解除", "终止"]):
            cat = "违约与解除"
        elif any(k in t for k in ["保密", "知识产权", "数据"]):
            cat = "保密与知识产权"
        else:
            cat = "其他"
        cats.append({"index": cl.get("index"), "header": cl.get("header"), "category": cat})
    return {"clause_categories": cats}


# ---------------- 节点 5：风险条款识别（规则引擎） ----------------
async def risk_detect(state: ContractReviewState) -> dict:
    risk_clauses: list[dict] = []
    sev_score = {"low": 0.25, "medium": 0.5, "high": 0.8, "critical": 0.95}
    for cl in state.get("clauses", []):
        t = cl.get("text", "")
        hits = R.match_risk_rules(t)
        if not hits:
            continue
        # 同条款多风险合并：取最高级别
        worst = max(hits, key=lambda h: {"low": 0, "medium": 1, "high": 2, "critical": 3}[h["level"]])
        risk_clauses.append(
            {
                "clause_index": cl.get("index", 0),
                "clause_header": cl.get("header", ""),
                "original_text": t[:400],
                "risk_type": worst["risk_type"],
                "risk_level": worst["level"],
                "risk_score": sev_score[worst["level"]],
                "risk_description": worst["risk_description"],
                "suggestion": worst["suggestion"],
                "legal_basis": worst["legal_basis"],
                "extra_hits": [h["risk_type"] for h in hits[1:]][:3],
            }
        )
    max_level = "low"
    for rc in risk_clauses:
        cur = {"low": 0, "medium": 1, "high": 2, "critical": 3}[rc["risk_level"]]
        if cur > {"low": 0, "medium": 1, "high": 2, "critical": 3}[max_level]:
            max_level = rc["risk_level"]
    return {"risk_clauses": risk_clauses, "max_risk_level": max_level}


# ---------------- 节点 6：合规审查（基于法条规则 + 法条检索佐证） ----------------
async def compliance_check(state: ContractReviewState) -> dict:
    issues = []
    for rc in state.get("risk_clauses", []):
        issues.append(
            {
                "clause_index": rc["clause_index"],
                "issue": rc["risk_type"],
                "level": rc["risk_level"],
                "basis": rc["legal_basis"],
                "description": rc["risk_description"],
            }
        )
    # 规则未覆盖的补充：尝试检索佐证（轻量，失败不阻塞）
    try:
        law_hint = await call_tool(
            "search_law_database",
            {"query": state.get("contract_type") + "合同 违约责任 变更", "top_k": 2},
        )
        law_note = law_hint.get("results", [])
    except Exception:
        law_note = []
    penalty = 12 * len({i["issue"] for i in issues})
    score = max(20.0, 100.0 - penalty)
    return {
        "compliance_issues": issues,
        "compliance_score": round(score, 1),
        "_law_note": law_note,
    }


# ---------------- 节点 7：一致性审查 ----------------
async def consistency_check(state: ContractReviewState) -> dict:
    issues: list[dict] = []
    clauses = state.get("clauses", [])
    # 提取每条款中的百分数与金额，跨条款比对冲突
    text_by_idx = {c.get("index"): c.get("text", "") for c in clauses}
    for a_idx in list(text_by_idx):
        for b_idx in list(text_by_idx):
            if a_idx >= b_idx:
                continue
            pa = set(re.findall(r"(?:百分之|%)\s*(\d{1,3})", text_by_idx[a_idx]))
            pb = set(re.findall(r"(?:百分之|%)\s*(\d{1,3})", text_by_idx[b_idx]))
            common = pa & pb
            # 同百分数出现在不同语义条款少见冲突，仅当两处都含'付款'
            if common and "付款" in text_by_idx[a_idx] and "付款" in text_by_idx[b_idx]:
                issues.append(
                    {
                        "clause_pair": [a_idx, b_idx],
                        "issue": "付款相关条款中同时出现相同比例数字，需核对是否语义冲突或重复约定",
                        "level": "low",
                    }
                )
    score = max(50.0, 100.0 - 6.0 * len(issues))
    return {"consistency_issues": issues, "consistency_score": round(score, 1)}


# ---------------- 节点 8：反方 Agent 攻击（弱势方立场） ----------------
async def adverse_agent_attack(state: ContractReviewState) -> dict:
    opinions: list[dict] = []
    review_check: list[dict] = []
    primary_risks: list[dict] = []
    stance = "乙方（弱势方）" if state.get("parties") else "相对弱势一方"
    for rc in state.get("risk_clauses", []):
        primary_risks.append(
            {
                "clause": rc["clause_index"],
                "risk": rc["risk_type"],
                "level": rc["risk_level"],
            }
        )
        if rc["risk_level"] in ("high", "critical"):
            opinions.append(
                {
                    "clause": rc["clause_index"],
                    "clause_text": (rc["original_text"] or "")[:80],
                    "stance": stance,
                    "opinion": f"该条款（{rc['risk_type']}）从{stance}立场明显不公：{rc['risk_description']}建议按'{rc['suggestion']}'修改。",
                }
            )
            review_check.append(
                {"clause": rc["clause_index"], "risk": rc["risk_type"], "verdict": "disputed", "reason": rc["legal_basis"]}
            )
        else:
            review_check.append(
                {"clause": rc["clause_index"], "risk": rc["risk_type"], "verdict": "approved", "reason": "规则引擎确认在合理范围内，建议关注表述"}
            )
    return {
        "primary_risks": primary_risks,
        "review_check": review_check,
        "adverse_opinions": opinions,
        "adverse_opinion_count": len(opinions),
    }


# ---------------- 节点 9：对抗辩论 / 仲裁 ----------------
async def debate_round(state: ContractReviewState) -> dict:
    debate_log: list[dict] = []
    unresolved: list[str] = []
    for rc in state.get("risk_clauses", []):
        if rc["risk_level"] not in ("high", "critical"):
            continue
        issue = f"第{rc['clause_index'] + 1}条的 {rc['risk_type']}"
        debate_log.append(
            {
                "round": 1,
                "issue": issue,
                "main_audit": f"主审判定存在{rc['risk_level']}风险：{rc['risk_description']}",
                "adversary": f"反方质疑：{rc['suggestion'].split('，')[0]}；若不修改将显失公平。",
                "arbiter": f"仲裁结论：维持{rc['risk_level']}风险提示，建议采纳修改意见（依据{rc['legal_basis']}）。",
            }
        )
        if rc["risk_type"] in ("单方变更权", "违约金比例过高"):
            unresolved.append(f"条款{rc['clause_index'] + 1}：{rc['risk_type']}的修改幅度需与对方协商确定")
    return {"debate_log": debate_log, "unresolved_issues": unresolved, "unresolved_count": len(unresolved)}


# ---------------- 节点 10：风险评分 ----------------
async def risk_score_node(state: ContractReviewState) -> dict:
    score = 100.0
    for rc in state.get("risk_clauses", []):
        score -= {"low": 2, "medium": 6, "high": 10, "critical": 15}.get(rc["risk_level"], 5)
    score -= 3.0 * len(state.get("completeness_missing", []))
    score -= 4.0 * len(state.get("unresolved_issues", []))
    score = max(0.0, min(100.0, score))
    # 与三维度健康分融合：健康分 = (完整+合规+一致)/3
    health = (state.get("completeness_score", 70) + state.get("compliance_score", 60) + state.get("consistency_score", 60)) / 3
    overall = round(health * 0.4 + score * 0.6, 1)
    if overall >= 80:
        level = "low"
    elif overall >= 60:
        level = "medium"
    elif overall >= 40:
        level = "high"
    else:
        level = "critical"
    return {"risk_score": round(score, 1), "overall_score": overall, "risk_level": level}


# ---------------- 节点 11：修改建议 ----------------
async def generate_suggestions(state: ContractReviewState) -> dict:
    suggestions: list[str] = []
    for rc in state.get("risk_clauses", []):
        suggestions.append(
            f"【第{rc['clause_index'] + 1}条 · {rc['risk_type']}({rc['risk_level']})】{rc['suggestion']}（依据{rc['legal_basis']}）"
        )
    for miss in state.get("completeness_missing", []):
        suggestions.append(f"【完整性】建议补充“{miss}”相关条款。")
    # 工具增强：劳动类给出经济补偿测算提示
    if state.get("contract_type") == "劳动":
        try:
            r = await call_tool("calculate_damages", {"kind": "labor", "years": 2, "monthly_salary": 8000})
            if "economic_compensation" in r:
                suggestions.append(f"【测算参考】按工作满 2 年、月薪 8000 元估算，合法解除经济补偿约 {r['economic_compensation']} 元（仅供参考）。")
        except Exception:
            pass
    if not suggestions:
        suggestions.append("未发现重大风险条款，仍建议保留沟通记录并请法务复核。")
    return {"suggestions": suggestions}


# ---------------- 节点 12：报告生成 ----------------
async def report_generate(state: ContractReviewState) -> dict:
    risks = state.get("risk_clauses", [])
    if state.get("overall_score", 100) >= 80:
        tone = "合同整体风险较低"
    elif state.get("overall_score", 60) >= 60:
        tone = "合同整体存在一定风险，需重点修改所列条款"
    else:
        tone = "合同风险较高，强烈建议修改后再签署"
    summary = (
        f"共审查 {state.get('clauses_count', 0)} 个条款，识别风险条款 {len(risks)} 处"
        f"（最高级别：{state.get('max_risk_level', 'low')}）。{tone}。"
        f"完整性缺失 {len(state.get('completeness_missing', []))} 项；"
        f"合规得分 {state.get('compliance_score', 0)}；一致性得分 {state.get('consistency_score', 0)}。"
        f"经主审/复核/反方对抗与仲裁：{state.get('adverse_opinion_count', 0)} 项高风险意见，"
        f"{state.get('unresolved_count', 0)} 项待协商事项。"
    )
    report = {
        "summary": summary,
        "overall_score": state.get("overall_score", 0),
        "risk_level": state.get("risk_level", "medium"),
        "risk_clause_count": len(risks),
        "risk_clauses_detail": [
            {
                "clause_index": r.get("clause_index", 0),
                "clause_header": r.get("clause_header", ""),
                "original_text": r.get("original_text", ""),
                "risk_type": r.get("risk_type", ""),
                "risk_level": r.get("risk_level", "low"),
                "risk_score": r.get("risk_score", 0),
                "risk_description": r.get("risk_description", ""),
                "suggestion": r.get("suggestion", ""),
                "legal_basis": r.get("legal_basis", ""),
            }
            for r in risks
        ],
        "completeness": state.get("completeness_score", 0),
        "compliance": state.get("compliance_score", 0),
        "consistency": state.get("consistency_score", 0),
        "suggestions": state.get("suggestions", []),
        "primary_risks": state.get("primary_risks", []),
        "review_check": state.get("review_check", []),
        "adverse_opinions": state.get("adverse_opinions", []),
        "adverse_opinion_count": state.get("adverse_opinion_count", 0),
        "debate_log": state.get("debate_log", []),
        "unresolved_issues": state.get("unresolved_issues", []),
        "unresolved_count": state.get("unresolved_count", 0),
        "parties": state.get("parties", []),
        "amount": state.get("amount"),
        "clauses_count": state.get("clauses_count", 0),
        "needs_manual_review": (state.get("overall_score", 100) < 60),
    }
    return {"review_report": report, "summary": summary}


# 导出别名（文档命名的同时保持 graph 节点一致）
parse_document = parse_doc
compliance_check_node = compliance_check
consistency_check_node = consistency_check
adverse_attack = adverse_agent_attack
debate = debate_round
risk_score_calc = risk_score_node
suggestions_node = generate_suggestions
report_generate_node = report_generate
