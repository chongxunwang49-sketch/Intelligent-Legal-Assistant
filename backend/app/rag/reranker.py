# -*- coding: utf-8 -*-
"""
智法通 V2 —— Reranker（第二阶段精排）
优先调用自建 Cross-Encoder 服务(bge-reranker-v2-m3 @ RERANK_SERVICE_URL)；
服务不可用时降级为 LLM(qwen2.5:1.5b) 逐条打分。
健康探测带 TTL(30s)，服务恢复后可自动重新启用。
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_HEALTH_TTL = 30
_MAX_LLM_CHARS = 500


class Reranker:
    def __init__(self) -> None:
        self.url = settings.RERANK_SERVICE_URL.rstrip("/")
        self.timeout = settings.RERANK_TIMEOUT
        self.ollama_base = settings.OLLAMA_BASE_URL.rstrip("/")
        self.ollama_model = settings.OLLAMA_MODEL
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=5.0))
        self._available: bool | None = None
        self._probe_at = 0.0

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass

    async def _check_service(self) -> bool:
        now = time.time()
        if self._available is not None and now < self._probe_at:
            return self._available
        try:
            resp = await self._client.get(f"{self.url}/health", timeout=5)
            self._available = resp.status_code == 200 and resp.json().get("ready") is True
        except Exception:
            self._available = False
        self._probe_at = now + _HEALTH_TTL
        if not self._available:
            logger.warning("Rerank 服务不可用，降级 LLM 逐条打分")
        return self._available

    async def rerank(self, query: str, items: list[dict], top_n: int) -> list[dict]:
        """items: [{id,text,metadata,...}]；返回按相关度降序的 top_n（注入 rerank_score）。"""
        if not items:
            return []
        if await self._check_service():
            try:
                docs = [it.get("text", "")[:2000] for it in items]
                resp = await self._client.post(
                    f"{self.url}/rerank",
                    json={"query": query[:500], "documents": docs, "top_n": min(top_n, len(docs))},
                )
                if resp.status_code == 200:
                    body = resp.json()
                    results = body.get("results") or []
                    ordered: list[dict] = []
                    for r in results:
                        idx = r.get("index")
                        if isinstance(idx, int) and 0 <= idx < len(items):
                            it = dict(items[idx])
                            it["rerank_score"] = float(r.get("score", 0.0))
                            ordered.append(it)
                    return ordered
            except Exception as exc:
                logger.warning("Rerank 调用失败，降级 LLM: %s", exc)
        return await self._rerank_with_llm(query, items, top_n)

    async def _rerank_with_llm(self, query: str, items: list[dict], top_n: int) -> list[dict]:
        """LLM 逐条打分（0-1 相关性），异常返回默认 0.5。"""
        scored: list[dict] = []
        for it in items:
            content = it.get("text", "")[:_MAX_LLM_CHARS]
            prompt = (
                "你是一个法律检索相关性打分器。只输出一个 0~1 之间的数字（越大越相关），不要其它内容。\n"
                f"查询：{query}\n候选文档：{content}\n打分："
            )
            score = 0.5
            try:
                resp = await self._client.post(
                    f"{self.ollama_base}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 10},
                    },
                    timeout=60,
                )
                if resp.status_code == 200:
                    raw = (resp.json().get("response") or "").strip()
                    try:
                        num = float(json.loads(raw) if raw.isdigit() or raw.replace(".", "", 1).isdigit() else raw)
                        score = max(0.0, min(1.0, num))
                    except Exception:
                        pass
            except Exception:
                pass
            it = dict(it)
            it["rerank_score"] = score
            scored.append(it)
        scored.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return scored[:top_n]


reranker = Reranker()
