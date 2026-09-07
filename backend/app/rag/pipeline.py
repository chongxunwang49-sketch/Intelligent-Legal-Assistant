# -*- coding: utf-8 -*-
"""
智法通 V2 —— RAG 问答主管线

query():    指代消解 → 改写 → 子查询分解 → 多路混合检索 → Cross-Encoder 精排 →
            生成 → LLM Self-RAG 自评估 → 低置信/revise → 重检索-再生成(≤2轮) → 法条引用校验
query_stream(): 检索/精排(meta) → LLM 流式生成(content) → 引用校验/自评估 → done
"""
from __future__ import annotations

import json
import re
import time
from typing import AsyncGenerator, Optional

import httpx

from app.config import settings
from app.rag.embedding import embedding_service
from app.rag.llm import llm_client
from app.rag.query_rewriter import query_rewriter
from app.rag.reranker import reranker
from app.rag.retriever import HybridRetriever
from app.rag.self_eval import self_evaluator
from app.rag.sub_query import sub_query_decomposer
from app.rag.vector_store import vector_store

_CITE_RE = re.compile(r"《([^》]{1,40}?)》\s*(?:第([零一二三四五六七八九十百千\d]+)条)?")

retriever = HybridRetriever(vector_store, embedding_service)


def _dedupe(items: list[dict]) -> list[dict]:
    seen: dict[str, dict] = {}
    for it in items:
        key = it.get("id")
        if key not in seen:
            seen[key] = it
        else:
            # 保留较高 rrf 分
            if it.get("rrf_score", 0) > seen[key].get("rrf_score", 0):
                seen[key] = it
    return list(seen.values())


class RAGPipeline:
    async def _retrieve_candidates(
        self, question: str, sub_queries: list[str], top_n: int
    ) -> tuple[list[dict], int]:
        merged: list[dict] = []
        where = {"effectiveness": "有效"}
        for q in sub_queries:
            items = await retriever.retrieve(q, top_k=settings.RAG_RECALL_TOP_K, where=where)
            merged.extend(items)
        merged = _dedupe(merged)
        if not merged:
            return [], 0
        ranked = await reranker.rerank(question, merged, top_n)
        return ranked, len(merged)

    def _build_context(self, candidates: list[dict]) -> list[dict]:
        return [
            {
                "law_name": it.get("metadata", {}).get("law_name") or it.get("metadata", {}).get("title") or "",
                "article_no": it.get("metadata", {}).get("article_no") or "",
                "title": it.get("metadata", {}).get("title") or "",
                "text": it.get("text", ""),
                "rerank_score": it.get("rerank_score", 0),
            }
            for it in candidates
        ]

    async def _generate(
        self, question: str, contexts: list[dict], history_text: str = ""
    ) -> str:
        ctx_text = "\n\n".join(
            f"[{c.get('law_name') or c.get('title')}{'第'+str(c.get('article_no'))+'条' if c.get('article_no') else ''}] {c.get('text')}"
            for c in contexts
        )
        sys = (
            "你是严谨的中国法律智能顾问。只能依据给出的法条/法规上下文回答；"
            "引用法律时用《法律名称》第X条格式；若上下文不足以回答，明确说明并建议咨询执业律师；"
            "回答须有条理、给出对用户具体可操作的建议，不编造法条。"
        )
        history_block = f"\n\n对话历史：{history_text}" if history_text else ""
        usr = f"可用法条上下文：\n{ctx_text}\n\n{history_block}\n用户问题：{question}\n\n请回答："
        out = await llm_client.complete(
            [{"role": "system", "content": sys}, {"role": "user", "content": usr}],
            temperature=settings.OLLAMA_TEMPERATURE,
            max_tokens=settings.OLLAMA_MAX_TOKENS,
        )
        return out.strip() if out else "抱歉，暂时无法生成回答，请稍后重试或咨询执业律师。"

    async def _extract_citations(self, answer: str, contexts: list[dict]) -> tuple[list[dict], list[str]]:
        """抽取回答中《X》第X条引用并与检索上下文比对；返回 (命中引用, 未命中警告)。"""
        found_names: dict[str, str] = {}
        for m in _CITE_RE.finditer(answer):
            name = m.group(1).strip()
            art = (m.group(2) or "").strip()
            if name not in found_names and len(name) <= 40:
                found_names[name] = art or ""
        citations: list[dict] = []
        warnings: list[str] = []
        for name, art in found_names.items():
            hit = any(
                name in (c.get("law_name") or c.get("title") or "")
                for c in contexts
            )
            if hit:
                citations.append({"name": name, "article": art})
            else:
                warnings.append(f"回答引用的《{name}》未在本次检索上下文中核验到")
        return citations, warnings

    # ================== 非流式（含 Self-RAG 闭环）==================
    async def query(
        self,
        question: str,
        history: Optional[list[dict]] = None,
        _graph_context: Optional[list[dict]] = None,
    ) -> dict:
        t0 = time.time()
        question = (question or "").strip()
        hist_text = self._history_text(history)
        resolved = await query_rewriter.resolve_coreference(question, hist_text)
        rewritten = resolved  # 指代消解即为改写结果（进一步术语改写按需开放）
        if sub_query_decomposer.is_complex_heuristic(rewritten):
            sub_queries = await sub_query_decomposer.decompose(rewritten)
        else:
            sub_queries = [rewritten]

        candidates, recalled = await self._retrieve_candidates(rewritten, sub_queries, settings.RAG_TOP_K)
        # GraphRAG 图谱第三路候选（M5 注入）
        if _graph_context:
            for g in _graph_context:
                candidates.append(
                    {"id": g.get("id", f"g_{len(candidates)}"), "text": g.get("text", ""),
                     "metadata": g.get("metadata", {}), "rerank_score": g.get("score", 0.0)}
                )
            candidates = _dedupe(candidates)

        contexts = self._build_context(candidates)
        answer = ""
        final_eval: dict = {}
        max_tries = settings.RAG_RERETRIEVAL_MAX_RETRIES + 1
        for attempt in range(max_tries):
            answer = await self._generate(rewritten, contexts, hist_text)
            final_eval = await self._normalized_eval(rewritten, contexts, answer)
            if attempt >= max_tries - 1:
                break
            need = (
                final_eval.get("need_reretrieval")
                or final_eval.get("overall_verdict") in ("revise", "reject")
                or (final_eval.get("confidence") or 0) < settings.RAG_RERETRIEVAL_CONFIDENCE_THRESHOLD
            )
            if not need:
                break
            # 重检索查询改写（允许跨法条检索）
            retry_queries = final_eval.get("reretrieval_queries") or sub_queries
            extra, recalled2 = await self._retrieve_candidates(
                retry_queries[0] if retry_queries else rewritten,
                retry_queries,
                settings.RAG_TOP_K,
            )
            if not extra:
                break
            contexts = self._build_context(extra)
            recalled = max(recalled, recalled2)

        citations, warnings = await self._extract_citations(answer, contexts)
        latency = int((time.time() - t0) * 1000)
        warning = "；".join(warnings) if warnings else ""
        return {
            "answer": answer,
            "citations": citations,
            "confidence": final_eval.get("confidence", 0.5),
            "self_eval": final_eval,
            "rewritten_query": rewritten,
            "sub_queries": sub_queries,
            "retrieved_count": recalled,
            "used_context_count": len(contexts),
            "warning": warning,
            "latency_ms": latency,
            "token_count": max(len(answer) // 2, 0),
        }

    # ================== 流式 ==================
    async def query_stream(
        self,
        question: str,
        history: Optional[list[dict]] = None,
    ) -> AsyncGenerator[dict, None]:
        t0 = time.time()
        question = (question or "").strip()
        hist_text = self._history_text(history)
        resolved = await query_rewriter.resolve_coreference(question, hist_text)
        sub_queries = [resolved]
        candidates, recalled = await self._retrieve_candidates(resolved, sub_queries, settings.RAG_TOP_K)
        contexts = self._build_context(candidates)
        yield {
            "type": "meta",
            "data": {
                "question": question,
                "rewritten": resolved,
                "sub_queries": sub_queries,
                "retrieved_count": recalled,
            },
        }
        ctx_text = "\n\n".join(
            f"[{c.get('law_name') or c.get('title')}{'第'+str(c.get('article_no'))+'条' if c.get('article_no') else ''}] {c.get('text')}"
            for c in contexts
        )
        sys = (
            "你是严谨的中国法律智能顾问。只能依据给出的法条/法规上下文回答；引用法律用《法律名称》第X条格式；"
            "上下文不足时明确说明并建议咨询执业律师；不编造法条。"
        )
        hb = f"\n\n对话历史：{hist_text}" if hist_text else ""
        usr = f"可用法条上下文：\n{ctx_text}\n\n{hb}\n用户问题：{question}\n\n请回答："
        chunks: list[str] = []
        async for tok in llm_client.complete_stream(
            [{"role": "system", "content": sys}, {"role": "user", "content": usr}]
        ):
            chunks.append(tok)
            yield {"type": "content", "data": {"delta": tok}}
        answer = "".join(chunks).strip() or "抱歉，暂时无法生成回答，请稍后重试或咨询执业律师。"
        citations, warnings = await self._extract_citations(answer, contexts)
        final_eval = await self._normalized_eval(resolved, contexts, answer)
        latency = int((time.time() - t0) * 1000)
        yield {
            "type": "done",
            "data": {
                "answer": answer,
                "citations": citations,
                "confidence": final_eval.get("confidence", 0.5),
                "self_eval": final_eval,
                "warning": "；".join(warnings) if warnings else "",
                "latency_ms": latency,
            },
        }

    # ================== 工具 ==================
    def _history_text(self, history: Optional[list[dict]]) -> str:
        if not history:
            return ""
        lines = []
        for m in history[-6:]:
            role = m.get("role")
            content = (m.get("content") or "")[:200]
            lines.append(f"{'用户' if role == 'user' else '助手'}：{content}")
        return "\n".join(lines)

    async def _normalized_eval(self, q, contexts, answer) -> dict:
        ev = await self_evaluator.evaluate(q, contexts, answer)
        return ev if ev else {}


rag_pipeline = RAGPipeline()
