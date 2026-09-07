# -*- coding: utf-8 -*-
"""
智法通 V2 —— Embedding 服务（粗排/ANN 向量化）
首选 Ollama quentinz/bge-large-zh-v1.5(1024 维)；服务不可用时降级本地 jieba+特征哈希向量。
可用性探测带 TTL 缓存（60s），服务恢复后能自动重新探测。
"""
from __future__ import annotations

import hashlib
import logging
import time

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_LOCAL_DIM = settings.CHROMA_EMBEDDING_DIM
_PROBE_TTL = 60


class EmbeddingService:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_EMBEDDING_MODEL
        self.dim = settings.CHROMA_EMBEDDING_DIM
        self.timeout = settings.OLLAMA_TIMEOUT
        self._ollama_available: bool | None = None
        self._probe_at = 0.0
        self._client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass

    async def _check_ollama(self) -> bool:
        now = time.time()
        if self._ollama_available is not None and now < self._probe_at:
            return self._ollama_available
        try:
            resp = await self._client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": ["测试"]},
            )
            ok = resp.status_code == 200 and bool(resp.json().get("embeddings"))
        except Exception:
            ok = False
        self._ollama_available = ok
        self._probe_at = now + _PROBE_TTL
        if not ok:
            logger.warning("Ollama Embedding 不可用，将使用本地哈希向量兜底")
        return ok

    # ---------------- 本地兜底 ----------------
    def _local_embed(self, text: str) -> list[float]:
        """jieba 分词 → 每词特征哈希累加到固定维度 → L2 归一化。"""
        import jieba

        vec = [0.0] * _LOCAL_DIM
        for tok in jieba.lcut(text[:2000]):
            h = hashlib.md5(tok.encode("utf-8")).digest()
            idx = int.from_bytes(h[:4], "little") % _LOCAL_DIM
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if await self._check_ollama():
            try:
                resp = await self._client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": list(texts)},
                )
                if resp.status_code == 200:
                    embeddings = resp.json().get("embeddings") or []
                    if len(embeddings) == len(texts) and len(embeddings[0]) == self.dim:
                        return embeddings
            except Exception as exc:
                logger.warning("Ollama Embedding 调用失败，降级本地: %s", exc)
                self._ollama_available = False
        return [self._local_embed(t) for t in texts]

    async def embed_text(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]


embedding_service = EmbeddingService()
