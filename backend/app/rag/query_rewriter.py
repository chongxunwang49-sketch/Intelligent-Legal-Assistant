# -*- coding: utf-8 -*-
"""智法通 V2 —— 查询重写：对话指代消解 + 口语化→法律术语（LLM，失败回退原问）。"""
from __future__ import annotations

from app.rag.llm import llm_client


class QueryRewriter:
    async def resolve_coreference(self, question: str, history: str) -> str:
        """结合最近对话历史，把指代（这个/它/对方/公司 等）补全成明确表述。"""
        if not history or not question.strip():
            return question.strip()
        sys = "你是一个法律问答系统的查询改写器。结合对话历史，将用户最新问题中的指代补全为明确的表述，只输出改写后的单个问题，不要任何解释。"
        usr = f"对话历史：\n{history}\n\n用户最新问题：{question}\n改写后的问题："
        out = await llm_client.complete(
            [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            temperature=0.1,
            max_tokens=120,
        )
        out = out.strip().strip('"')
        return out if out else question.strip()

    async def legalize(self, question: str) -> str:
        """口语 → 规范法律术语（仅在明显口语时轻量改写）。"""
        if not question.strip():
            return question
        sys = (
            "你是法律检索改写器。把用户口语化问题改写为更利于法规检索的规范表述，"
            "补充关键法律术语但不要新增问题，只输出改写后文本。若已规范则原样输出。"
        )
        out = await llm_client.complete(
            [{"role": "system", "content": sys}, {"role": "user", "content": question}],
            temperature=0.1,
            max_tokens=120,
        )
        out = out.strip().strip('"')
        return out if out else question.strip()


query_rewriter = QueryRewriter()
