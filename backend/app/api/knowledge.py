# -*- coding: utf-8 -*-
"""智法通 V2 —— 知识库路由（上传/检索/统计 需 knowledge:manage）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.knowledge_service import knowledge_service
from app.utils.deps import (
    CurrentUser,
    get_current_user,
    require_permission,
)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/documents")
async def list_documents(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    doc_type: Optional[str] = None,
    status: Optional[str] = None,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_service.get_documents(
        db, page=page, page_size=page_size, keyword=keyword, doc_type=doc_type, status=status
    )


@router.post("/upload", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("法律"),
    tags: Optional[str] = Form(None),
    user: CurrentUser = Depends(require_permission("knowledge:manage")),
    db: AsyncSession = Depends(get_db),
):
    import json as _json

    tag_list = _json.loads(tags) if tags else []
    doc = await knowledge_service.upload_document(db, user, file, doc_type=doc_type, tags=tag_list)
    return {"message": "上传并索引成功", "document": knowledge_service._doc_summary(doc)}


@router.post("/search")
async def search_knowledge(
    payload: dict,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (payload.get("query") or "").strip()
    if not query:
        return {"query": "", "items": [], "total": 0}
    return await knowledge_service.search(
        db,
        query,
        top_k=int(payload.get("top_k", 5)),
        doc_type=payload.get("doc_type"),
        effectiveness=payload.get("effectiveness"),
    )


@router.get("/stats")
async def knowledge_stats(
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_service.get_stats(db)


@router.get("/documents/{doc_id}")
async def document_detail(
    doc_id: int,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_service.get_detail(db, doc_id)


@router.get("/documents/{doc_id}/content")
async def document_content(
    doc_id: int,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await knowledge_service.get_content(db, doc_id)


@router.delete("/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    _: CurrentUser = Depends(require_permission("knowledge:manage")),
    db: AsyncSession = Depends(get_db),
):
    await knowledge_service.delete_document(db, doc_id)
    return {"message": "文档已删除"}
