# -*- coding: utf-8 -*-
"""
智法通 V2 —— Self-RAG LLM 自评估
6 维评分 + 幻觉检测 + verdict(pass/revise/reject) + 重检索查询改写；
低置信度/需重检索 → pipeline 触发二次检索-生成（最多 2 轮）。
"""
from __future__ import annotations

import json
import logging

from app.rag.llm import llm_client

logger = logging.getLogger(__name__)

_DIMS = ["law_accuracy", "completeness", "logic", "timeliness", "practicality", "risk_warning"]
_WEIGHTS = [0.25, 0.2, 0.15, 0.15, 0.15, 0.1]


def _fmt_context(contexts: list[dict], limit: int = 6) -> str:
    lines = []
    for c in contexts[:limit]:
        name = c.get("law_name") or c.get("title") or ""
        art = c.get("article_no") or ""
        text = (c.get("text") or "")[:180].replace("\n", " ")
        lines.append(f"[{name}{art}] {text}")
    return "\n".join(lines) if lines else "(无可参考法条)"


class SelfEvaluator:
    async def evaluate(self, question: str, contexts: list[dict], answer: str) -> dict:
        ans_trunc = (answer or "")[:1200]
        prompt_ctx = _fmt_context(contexts)
        sys = (
            "你是法律回答质量评估器。基于检索到的法条上下文评判 AI 回答。输出 JSON，含字段：\n"
            "law_accuracy/completeness/logic/timeliness/practicality/risk_warning（0-10 整数），"
            "hallucination_detected(bool，回答有无脱离上下文虚构), "
            "missing_key_points(str), need_reretrieval(bool), reretrieval_queries(字符串数组), "
            "overall_verdict(仅 pass/revise/reject)。只输出 JSON。"
        )
        usr = (
            f"法条上下文：\n{prompt_ctx}\n\n"
            f"用户问题：{question}\n\nAI 回答：{ans_trunc}\n\n评估 JSON："
        )
        raw = await llm_client.complete(
            [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            json_mode=True,
            temperature=0.1,
            max_tokens=300,
        )
        data = self._parse(raw)
        if data is None:
            return self._heuristic(question, contexts, answer)
        return self._normalize(data)

    def _parse(self, raw: str) -> dict | None:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            # 容错：截取第一个 { 到最后一个 }
            try:
                s = raw[raw.find("{"): raw.rfind("}") + 1]
                return json.loads(s)
            except Exception:
                return None

    def _normalize(self, data: dict) -> dict:
        scores = {}
        for d in _DIMS:
            try:
                v = float(data.get(d, 5))
                scores[d] = max(0.0, min(10.0, v))
            except Exception:
                scores[d] = 5.0
        confidence = sum(scores[d] * w for d, w in zip(_DIMS, _WEIGHTS)) / 10.0
        verdict = str(data.get("overall_verdict", "pass")).lower()
        if verdict not in ("pass", "revise", "reject"):
            verdict = "pass"
        need = bool(data.get("need_reretrieval")) or verdict in ("revise", "reject")
        rq = data.get("reretrieval_queries")
        if isinstance(rq, list):
            queries = [str(x).strip() for x in rq if str(x).strip()][:3]
        elif isinstance(rq, str) and rq.strip():
            queries = [q.strip() for q in rq.split("\n") if q.strip()][:3]
        else:
            queries = []
        return {
            **scores,
            "confidence": round(confidence, 3),
            "hallucination_detected": bool(data.get("hallucination_detected")),
            "missing_key_points": str(data.get("missing_key_points") or ""),
            "need_reretrieval": need,
            "reretrieval_queries": queries,
            "overall_verdict": verdict,
        }

    def _heuristic(self, question: str, contexts: list[dict], answer: str) -> dict:
        """LLM 失效兜底：规则评估，避免掩盖退化。"""
        n_char = len(answer or "")
        has_citation = "《" in answer and "条" in answer
        conf = 0.35
        if contexts and n_char >= 60:
            conf = 0.62 if has_citation else 0.52
        elif n_char >= 60:
            conf = 0.42
        verdict = "pass" if conf >= 0.5 else "revise"
        return {
            "law_accuracy": 6, "completeness": 6, "logic": 6,
            "timeliness": 5, "practicality": 5, "risk_warning": 5,
            "confidence": conf,
            "hallucination_detected": not has_citation,
            "missing_key_points": "",
            "need_reretrieval": conf < 0.5,
            "reretrieval_queries": [] if conf >= 0.5 else [question],
            "overall_verdict": verdict,
        }


self_evaluator = SelfEvaluator()
