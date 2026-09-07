# -*- coding: utf-8 -*-
"""智法通 V2 —— 子查询分解：启发式判定复杂 + LLM 拆分（失败回退单查询）。"""
from __future__ import annotations

import json
import re

from app.rag.llm import llm_client

_COMPLEX_HINTS = ["和", "以及", "与", "、", "分别", "同时", "既", "又", "还是", "吗？", "如何处理"]


class SubQueryDecomposer:
    def is_complex_heuristic(self, question: str) -> bool:
        q = question.strip()
        if len(q) > 40:
            return True
        cnt = sum(1 for h in _COMPLEX_HINTS if h in q)
        return cnt >= 2

    async def decompose(self, question: str) -> list[str]:
        if not self.is_complex_heuristic(question):
            return [question]
        sys = (
            "你是法律问答子问题拆解器。若问题包含多个可独立检索的法律要点，拆成 2-4 个独立子问题；"
            "否则只输出原问题一个。只输出 JSON 数组字符串，不要其它内容。"
        )
        raw = await llm_client.complete(
            [{"role": "system", "content": sys}, {"role": "user", "content": question}],
            json_mode=True,
            temperature=0.1,
            max_tokens=200,
        )
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                items = [str(x).strip() for x in data if str(x).strip()]
                return items[:4] or [question]
            if isinstance(data, dict):
                items = data.get("sub_queries") or data.get("queries") or []
                if items:
                    return [str(x) for x in items][:4]
        except Exception:
            pass
        return [question]


sub_query_decomposer = SubQueryDecomposer()
