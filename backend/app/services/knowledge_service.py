# -*- coding: utf-8 -*-
"""
智法通 V2 —— 知识库服务
统一 metadata schema 构造 + 增量维护（修复旧版“上传文档因缺 effectiveness 检索不到”的缺陷）。
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import naive_utcnow
from app.models.enums import DocumentEffectiveness, DocumentStatus
from app.models.knowledge import DocumentChunk, LegalDocument
from app.models.user import User
from app.rag.embedding import EmbeddingService
from app.rag.text_utils import split_document_text
from app.rag.vector_store import VectorStore
from app.utils.file_parser import FileParseError, parse_document

logger = logging.getLogger(__name__)

_ALLOWED_EXT = {e.lstrip(".").lower() for e in settings.ALLOWED_FILE_TYPES.split(",") if e}


def _epoch(dt: Optional[datetime]) -> Optional[int]:
    if dt is None:
        return None
    return int(dt.timestamp())


class KnowledgeService:
    def __init__(self) -> None:
        from app.rag.vector_store import vector_store

        self.vector_store: VectorStore = vector_store
        self.embedding = EmbeddingService()

    # ---------------- 索引 ----------------
    async def index_document(self, db: AsyncSession, doc: LegalDocument) -> LegalDocument:
        """对已入库文档执行分块+向量化+写分块行。重复调用先清理旧向量。"""
        if doc.id is None or doc.id <= 0:
            await db.flush()
        # 清理旧分块/向量（幂等重建）
        old_chunks = (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc.id))).scalars().all()
        old_ids = [c.vector_id for c in old_chunks if c.vector_id]
        if old_ids:
            self.vector_store.delete(old_ids)
        for c in old_chunks:
            await db.delete(c)
        await db.flush()

        chunks = split_document_text(
            doc.title or "",
            doc.doc_type or "法律",
            doc.content or "",
            effectiveness=doc.effectiveness or DocumentEffectiveness.EFFECTIVE.value,
            effective_epoch=_epoch(doc.effective_date),
            version=doc.version or "",
        )
        texts = [c["text"] for c in chunks]
        embeddings = await self.embedding.embed_texts(texts) if texts else []
        ids = [f"doc_{doc.id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "document_id": doc.id,
                "chunk_index": i,
                "doc_type": doc.doc_type,
                "title": doc.title,
                "law_name": c["law_name"],
                "article_no": c["article_no"],
                "effectiveness": c["effectiveness"],
                "effective_date": c["effective_epoch"],
                "version": c.get("version"),
            }
            for i, c in enumerate(chunks)
        ]
        if ids:
            self.vector_store.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
        # 写分块行
        start_char = 0
        for i, c in enumerate(chunks):
            db.add(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=c["text"],
                    vector_id=ids[i],
                    token_count=len(c["text"]),
                    start_char=start_char,
                    end_char=start_char + len(c["text"]),
                    law_name=c["law_name"],
                    article_no=c["article_no"],
                    chunk_metadata=json.dumps(metadatas[i], ensure_ascii=False),
                )
            )
            start_char += len(c["text"]) + 1
        doc.chunk_count = len(chunks)
        doc.status = DocumentStatus.COMPLETED.value
        doc.indexing_progress = 100
        await db.flush()
        return doc

    async def rebuild_index_for_docs(self, db: AsyncSession, doc_ids: Optional[list[int]] = None) -> int:
        """为 chunk_count==0 的已提交文档建索引；doc_ids 指定时仅重建这些。"""
        conds = [LegalDocument.status == DocumentStatus.COMPLETED.value]
        if doc_ids is not None:
            conds.append(LegalDocument.id.in_(doc_ids))
        else:
            conds.append(LegalDocument.chunk_count == 0)
        result = await db.execute(select(LegalDocument).where(*conds))
        docs = result.scalars().all()
        n = 0
        for doc in docs:
            try:
                await self.index_document(db, doc)
                await db.commit()
                n += 1
            except Exception as exc:
                logger.exception("文档 %s 建索引失败: %s", doc.id, exc)
                doc.status = DocumentStatus.FAILED.value
                await db.commit()
        return n

    # ---------------- 上传 ----------------
    async def upload_document(
        self,
        db: AsyncSession,
        user: User,
        file,
        doc_type: str = "法律",
        tags: Optional[list[str]] = None,
    ) -> LegalDocument:
        filename = os.path.basename((file.filename or "").replace("\\", "/"))
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if not filename or filename.startswith(".") or ".." in filename:
            raise HTTPException(status_code=400, detail="文件名不合法")
        if ext not in _ALLOWED_EXT:
            raise HTTPException(status_code=400, detail=f"不支持的文件类型，仅允许: {', '.join(sorted(_ALLOWED_EXT))}")
        data = await file.read()
        if len(data) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"文件大小不能超过 {settings.MAX_UPLOAD_SIZE_MB}MB")
        if not data:
            raise HTTPException(status_code=400, detail="文件内容为空")
        up_dir = Path(settings.UPLOAD_DIR)
        up_dir.mkdir(parents=True, exist_ok=True)
        fname = f"doc_{user.id}_{uuid.uuid4().hex}.{ext}"
        fpath = up_dir / fname
        fpath.write_bytes(data)
        try:
            text = parse_document(str(fpath), ext)
        except FileParseError as exc:
            fpath.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail=str(exc))
        if not text.strip():
            fpath.unlink(missing_ok=True)
            raise HTTPException(status_code=400, detail="未能从文件中解析出文本")
        title = os.path.splitext(filename)[0][:300]
        doc = LegalDocument(
            title=title,
            doc_type=doc_type,
            source="upload",
            file_path=str(fpath),
            file_name=filename,
            file_size=len(data),
            content=text,
            summary=text[:200],
            tags=json.dumps(tags or [], ensure_ascii=False),
            status=DocumentStatus.PENDING.value,
            is_effective=True,
            effectiveness=DocumentEffectiveness.EFFECTIVE.value,
            uploaded_by=user.id,
        )
        db.add(doc)
        await db.flush()
        try:
            doc = await self.index_document(db, doc)
            await db.commit()
        except Exception as exc:
            logger.exception("上传文档建索引失败")
            doc.status = DocumentStatus.FAILED.value
            await db.commit()
            raise HTTPException(status_code=500, detail=f"文档索引失败: {exc}")
        await db.refresh(doc)
        return doc

    # ---------------- 检索 ----------------
    async def search(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = 5,
        doc_type: Optional[str] = None,
        effectiveness: Optional[str] = None,
    ) -> dict:
        emb = await self.embedding.embed_text(query)
        where: dict = {}
        if doc_type:
            where["doc_type"] = doc_type
        if effectiveness:
            where["effectiveness"] = effectiveness
        else:
            where["effectiveness"] = DocumentEffectiveness.EFFECTIVE.value
        res = self.vector_store.query([emb], n_results=top_k, where=where)
        ids = (res.get("ids") or [[]])[0]
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        # 批量回填标题
        doc_ids = list({int(m.get("document_id", 0)) for m in metas if m.get("document_id")})
        titles: dict[int, str] = {}
        if doc_ids:
            rows = (await db.execute(select(LegalDocument.id, LegalDocument.title).where(LegalDocument.id.in_(doc_ids)))).all()
            titles = {r[0]: r[1] for r in rows}
        items = []
        for i in range(len(ids)):
            m = metas[i] if i < len(metas) else {}
            did = int(m.get("document_id", 0))
            items.append(
                {
                    "id": ids[i],
                    "document_id": did,
                    "title": titles.get(did) or m.get("title") or "",
                    "doc_type": m.get("doc_type"),
                    "law_name": m.get("law_name"),
                    "article_no": m.get("article_no"),
                    "effectiveness": m.get("effectiveness"),
                    "content": docs[i] if i < len(docs) else "",
                    "score": 1.0 - (dists[i] if i < len(dists) else 1.0),
                }
            )
        return {"query": query, "items": items, "total": len(items)}

    # ---------------- 统计 / 详情 ----------------
    async def get_stats(self, db: AsyncSession) -> dict:
        total = await db.scalar(select(func.count(LegalDocument.id))) or 0
        chunk_total = await db.scalar(select(func.count(DocumentChunk.id))) or 0
        by_type = (
            (await db.execute(select(LegalDocument.doc_type, func.count(LegalDocument.id)).group_by(LegalDocument.doc_type))).all()
        )
        return {
            "total_documents": total,
            "total_chunks": chunk_total,
            "doc_type_distribution": [{"doc_type": r[0], "count": r[1]} for r in by_type],
        }

    async def get_documents(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 10,
        keyword: Optional[str] = None,
        doc_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 100)
        conds = []
        if keyword:
            like = f"%{keyword.strip()}%"
            conds.append(or_(LegalDocument.title.like(like), LegalDocument.content.like(like)))
        if doc_type:
            conds.append(LegalDocument.doc_type == doc_type)
        if status:
            conds.append(LegalDocument.status == status)
        total = await db.scalar(select(func.count(LegalDocument.id)).where(*conds)) or 0
        result = await db.execute(
            select(LegalDocument)
            .where(*conds)
            .order_by(LegalDocument.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        docs = result.scalars().all()
        return {
            "items": [self._doc_summary(d) for d in docs],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def _doc_summary(self, d: LegalDocument) -> dict:
        return {
            "id": d.id,
            "title": d.title,
            "doc_type": d.doc_type,
            "source": d.source,
            "file_name": d.file_name,
            "file_size": d.file_size,
            "status": d.status,
            "chunk_count": d.chunk_count,
            "tags": json.loads(d.tags) if d.tags else [],
            "effective_date": d.effective_date,
            "abolished_date": d.abolished_date,
            "effectiveness": d.effectiveness,
            "version": d.version,
            "summary": (d.summary or "")[:120],
            "created_at": d.created_at,
        }

    async def get_detail(self, db: AsyncSession, doc_id: int) -> dict:
        doc = await db.get(LegalDocument, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="文档不存在")
        data = self._doc_summary(doc)
        result = await db.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id).order_by(DocumentChunk.chunk_index).limit(50)
        )
        data["chunks_preview"] = [
            {"index": c.chunk_index, "article_no": c.article_no, "content": c.content[:200], "vector_id": c.vector_id}
            for c in result.scalars().all()
        ]
        return data

    async def get_content(self, db: AsyncSession, doc_id: int) -> dict:
        doc = await db.get(LegalDocument, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="文档不存在")
        return {"id": doc.id, "title": doc.title, "content": doc.content or ""}

    async def delete_document(self, db: AsyncSession, doc_id: int) -> None:
        doc = await db.get(LegalDocument, doc_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="文档不存在")
        chunks = (await db.execute(select(DocumentChunk).where(DocumentChunk.document_id == doc_id))).scalars().all()
        ids = [c.vector_id for c in chunks if c.vector_id]
        if ids:
            self.vector_store.delete(ids)
        if doc.file_path and os.path.exists(doc.file_path):
            try:
                os.remove(doc.file_path)
            except OSError:
                pass
        await db.delete(doc)
        await db.commit()

    # 兼容引用
    @property
    def vector_store_ref(self) -> VectorStore:
        return self.vector_store


knowledge_service = KnowledgeService()
