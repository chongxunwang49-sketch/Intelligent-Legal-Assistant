# -*- coding: utf-8 -*-
"""
智法通 V2 —— ChromaDB 向量库封装（HNSW + cosine）

- 维度不一致自动删集合重建（应对模型切换）
- 统一 metadata schema 由调用方保证：document_id/chunk_index/doc_type/title/law_name/
  article_no/effectiveness/effective_date(epoch秒)
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import chromadb

from app.config import settings

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
        dim: int | None = None,
    ) -> None:
        self.persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self.collection_name = collection_name or settings.CHROMA_COLLECTION_NAME
        self.dim = dim or settings.CHROMA_EMBEDDING_DIM
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=self.persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._check_and_rebuild_if_dim_mismatch()

    def _check_and_rebuild_if_dim_mismatch(self) -> None:
        try:
            if self._collection.count() == 0:
                return
            got = self._collection.get(limit=1, include=["embeddings"])
            embs = got.get("embeddings") or []
            if embs and len(embs[0]) != self.dim:
                logger.warning(
                    "向量维度不匹配(现 %d, 期望 %d)，删除集合重建", len(embs[0]), self.dim
                )
                self._client.delete_collection(self.collection_name)
                self._collection = self._client.create_collection(
                    name=self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                )
        except Exception as exc:  # pragma: no cover
            logger.warning("向量维度自检失败: %s", exc)

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
        documents: list[str],
    ) -> None:
        # Chroma 不接受 None 元数据值：过滤空键
        clean = []
        for md in metadatas:
            clean.append({k: v for k, v in md.items() if v is not None})
        self._collection.add(ids=ids, embeddings=embeddings, metadatas=clean, documents=documents)

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int = 10,
        where: Optional[dict] = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "query_embeddings": query_embeddings,
            "n_results": n_results,
            "include": ["metadatas", "documents", "distances"],
        }
        if where:
            kwargs["where"] = where
        return self._collection.query(**kwargs)

    def get(
        self,
        where: Optional[dict] = None,
        limit: int = 10000,
        include: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"limit": limit}
        if include:
            kwargs["include"] = include
        if where:
            kwargs["where"] = where
        return self._collection.get(**kwargs)

    def delete(self, ids: list[str]) -> None:
        if ids:
            self._collection.delete(ids=ids)

    def count(self) -> int:
        return self._collection.count()


vector_store = VectorStore()
