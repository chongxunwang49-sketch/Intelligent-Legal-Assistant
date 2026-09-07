# -*- coding: utf-8 -*-
"""
智法通 V2 —— 合同审查工具集（Function Calling / 工具注册表）
search_law_database / check_clause_legality / get_standard_clause /
calculate_damages / get_legal_time_limit —— 均可被 Agent 节点与外部调用。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from app.agent import rules as R
from app.config import settings

# ---------------- 具体实现 ----------------

async def search_law_database(query: str, top_k: int = 3) -> dict:
    """在本地法律向量库检索相关法条（不依赖 MySQL，直接查 Chroma）。"""
    from app.rag.embedding import embedding_service
    from app.rag.vector_store import vector_store

    where = {"effectiveness": "有效"}
    emb = await embedding_service.embed_text(query)
    res = vector_store.query([emb], n_results=top_k, where=where)
    ids = (res.get("ids") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    items = []
    for i in range(len(ids)):
        m = metas[i] if i < len(metas) else {}
        items.append(
            {
                "law": m.get("law_name") or m.get("title") or "",
                "article": m.get("article_no") or "",
                "content": (docs[i] if i < len(docs) else "")[:300],
            }
        )
    return {"results": items}


def check_clause_legality(clause_text: str) -> dict:
    """用确定性规则库核查条款合法性，返回命中风险。"""
    hits = R.match_risk_rules(clause_text or "")
    return {"hits": hits}


def get_standard_clause(contract_type: str, name: str = "") -> dict:
    """返回合同类型的必备条款提示（供完整性审查参考）。"""
    required = R.required_clauses(contract_type or "买卖")
    return {"contract_type": contract_type or "买卖", "required_clauses": required, "query": name}


def calculate_damages(kind: str = "labor", **kwargs: Any) -> dict:
    """基础法律计算：labor=违法解除赔偿/经济补偿；interest=利息(LPR四倍)；违约金封顶提示。"""
    if kind == "labor":
        years = float(kwargs.get("years", 0) or 0)
        salary = float(kwargs.get("monthly_salary", 0) or 0)
        base_months = int(years) + (1 if years % 1 >= 0.5 else 0)
        base_months = min(base_months, 12)
        compensation = base_months * salary
        return {
            "kind": "labor",
            "economic_compensation_months": base_months,
            "economic_compensation": round(compensation, 2),
            "note": "按《劳动合同法》第四十七条，月工资高于当地社平三倍的按三倍封顶且年限≤12年。",
        }
    if kind == "interest":
        principal = float(kwargs.get("principal", 0) or 0)
        rate = float(kwargs.get("annual_rate", 0) or 0)
        days = float(kwargs.get("days", 0) or 0)
        interest = principal * rate / 100 * days / 365
        return {"kind": "interest", "interest_estimate": round(interest, 2), "note": "利率超过合同成立时一年期LPR四倍的部分不受保护。"}
    return {"kind": kind, "note": "未支持的计算类型"}


def get_legal_time_limit(topic: str = "") -> dict:
    limits = {
        "劳动争议仲裁": "1 年（自知道或应当知道权利被侵害之日起）",
        "普通诉讼时效": "3 年",
        "租赁押金返还": "租赁关系终止后及时主张（受3年诉讼时效约束）",
        "工伤认定申请": "单位30日内，个人/近亲属1年内",
        "劳动合同解除后仲裁": "1 年",
    }
    for k, v in limits.items():
        if k.split()[0] in topic or topic in k:
            return {"topic": k, "limit": v}
    return {"topic": topic, "limit": "请咨询律师确认具体时效"}


# ---------------- 注册表 ----------------
def _noop(name):  # pragma: no cover
    return {"error": f"工具 {name} 未实现"}


TOOL_DEFS: list[dict] = [
    {"name": "search_law_database", "description": "在法律向量库中检索相关法条条文",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "top_k": {"type": "integer"}}}},
    {"name": "check_clause_legality", "description": "用规则库核查合同条款是否含格式条款/风险情形",
     "parameters": {"type": "object", "properties": {"clause_text": {"type": "string"}}}},
    {"name": "get_standard_clause", "description": "获取某类合同的必备条款清单",
     "parameters": {"type": "object", "properties": {"contract_type": {"type": "string"}}}},
    {"name": "calculate_damages", "description": "计算经济补偿/利息等",
     "parameters": {"type": "object", "properties": {"kind": {"type": "string"}, "years": {"type": "number"}, "monthly_salary": {"type": "number"}}}},
    {"name": "get_legal_time_limit", "description": "查询常见法律时效",
     "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}}},
]

TOOL_FUNCTIONS: dict[str, Callable] = {
    "search_law_database": search_law_database,
    "check_clause_legality": check_clause_legality,
    "get_standard_clause": get_standard_clause,
    "calculate_damages": calculate_damages,
    "get_legal_time_limit": get_legal_time_limit,
}


async def call_tool(name: str, arguments: Optional[dict] = None) -> dict:
    fn = TOOL_FUNCTIONS.get(name)
    if fn is None:
        return {"error": f"未注册的工具: {name}"}
    try:
        args = dict(arguments or {})
        if name == "search_law_database":
            return await fn(args.get("query", ""), int(args.get("top_k", 3)))
        if name == "check_clause_legality":
            return fn(args.get("clause_text", ""))
        if name == "get_standard_clause":
            return fn(args.get("contract_type", "买卖"))
        if name == "calculate_damages":
            return fn(args.get("kind", "labor"), years=args.get("years"), monthly_salary=args.get("monthly_salary"), principal=args.get("principal"))
        if name == "get_legal_time_limit":
            return fn(args.get("topic", ""))
        return fn(**args)
    except Exception as exc:
        return {"error": str(exc)}
