# -*- coding: utf-8 -*-
"""
智法通 V2 —— HybridRetriever：稠密向量(Chroma ANN) + BM25 稀疏 + RRF 融合

改进：
- BM25 语料快照按集合数量缓存，避免每次全量重扫（旧实现每次 get(1000)+内存分词）
- 默认 where 过滤 effectiveness=有效，且上传/种子统一走同一条 metadata 构造路径
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

from app.config import settings

_WS_RE = re.compile(r"\s+")


class HybridRetriever:
    def __init__(self, vector_store, embedding_service, rrf_k: int | None = None) -> None:
        self.vector_store = vector_store
        self.embedding = embedding_service
        self.rrf_k = rrf_k or settings.RAG_RRF_K
        self._corpus_cache: dict[Any, Any] = {}  # (where_str,count) -> snapshot

    # ---------------- 语料快照 ----------------
    def _corpus(self, where: Optional[dict]) -> tuple[list, list, list]:
        where_key = str(where)
        count = self.vector_store.count()
        cached = self._corpus_cache.get(where_key)
        if cached and cached["count"] == count:
            return cached["ids"], cached["texts"], cached["metas"]
        got = self.vector_store.get(where=where, limit=5000, include=["documents", "metadatas"])
        ids: list = got.get("ids") or []
        texts: list = got.get("documents") or []
        metas: list = got.get("metadatas") or []
        self._corpus_cache[where_key] = {"count": count, "ids": ids, "texts": texts, "metas": metas}
        return ids, texts, metas

    # ---------------- BM25 ----------------
    def _bm25_rank(self, query_tokens: list[str], texts: list[str], top_n: int) -> list[dict]:
        if not texts:
            return []
        # 文档频次 df
        df: dict[str, int] = {}
        doc_token_lists: list[list[str]] = []
        doc_lens: list[int] = []
        for t in texts:
            toks = self._tokenize(t)
            doc_token_lists.append(toks)
            doc_lens.append(len(toks))
            for tok in set(toks):
                df[tok] = df.get(tok, 0) + 1
        n_docs = len(texts)
        avgdl = sum(doc_lens) / n_docs if n_docs else 1
        k1, b = 1.5, 0.75
        idf_map = {
            tok: math.log(1 + (n_docs - df.get(tok, 0) + 0.5) / (df.get(tok, 0) + 0.5))
            for tok in query_tokens
        }
        scored: list[tuple[int, float]] = []
        for i, toks in enumerate(doc_token_lists):
            tf: dict[str, int] = {}
            for tok in toks:
                tf[tok] = tf.get(tok, 0) + 1
            dl = doc_lens[i] or 1
            s = 0.0
            for tok in set(query_tokens):
                if tok not in tf:
                    continue
                s += idf_map.get(tok, 0.0) * (tf[tok] * (k1 + 1)) / (
                    tf[tok] + k1 * (1 - b + b * dl / avgdl)
                )
            scored.append((i, s))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [{"index": i, "score": s} for i, s in scored[:top_n]]

    def _tokenize(self, text: str) -> list[str]:
        try:
            import jieba

            return [t for t in jieba.lcut(text) if t.strip() and not _WS_RE.fullmatch(t)]
        except Exception:
            return [c for c in text if c.strip()]

    # ---------------- 稠密 ----------------
    async def _dense_search_async(self, query: str, top_n: int, where: Optional[dict]) -> list[dict]:
        emb = await self.embedding.embed_text(query)
        res = self.vector_store.query([emb], n_results=top_n, where=where)
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out = []
        for i in range(len(ids)):
            out.append(
                {
                    "id": ids[i],
                    "text": docs[i] if i < len(docs) else "",
                    "metadata": metas[i] if i < len(metas) else {},
                    "dist": dists[i] if i < len(dists) else 1.0,
                }
            )
        return out

    # ---------------- 融合 ----------------
    def _rrf_fuse(self, lists: list[list[dict]], top_n: int) -> list[dict]:
        scores: dict[str, float] = {}
        items: dict[str, dict] = {}
        for lst in lists:
            for rank, item in enumerate(lst):
                key = item["id"]
                if key not in items:
                    items[key] = item
                scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank + 1)
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        result = []
        for key, score in ranked[:top_n]:
            item = items[key]
            item = dict(item)
            item["rrf_score"] = score
            result.append(item)
        return result

    # ---------------- 对外 ----------------
    async def retrieve(
        self,
        query: str,
        top_k: int,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """混合检索主入口：稠密 top_k*2 + 稀疏 top_k*2 → RRF 取 top_k。"""
        where = where or {"effectiveness": "有效"}
        dense = await self._dense_search_async(query, top_k * 2, where)
        q_tokens = self._tokenize(query)
        if not q_tokens:
            sparse: list[dict] = []
        else:
            ids, texts, metas = self._corpus(where)
            if not texts:
                sparse = []
            else:
                ranked = self._bm25_rank(q_tokens, texts, top_k * 2)
                sparse = [
                    {"id": ids[r["index"]], "text": texts[r["index"]],
                     "metadata": metas[r["index"]] if r["index"] < len(metas) else {},
                     "bm25_score": r["score"]}
                    for r in ranked
                ]
        fused = self._rrf_fuse([dense, sparse], top_k)
        return fused
