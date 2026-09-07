# -*- coding: utf-8 -*-
"""智法通 V2 —— 知识图谱 API（ECharts 力导向图 / 重建 / 统计 / 时间旅行查询）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.knowledge import LegalDocument
from app.services.graph_service import graph_service
from app.utils.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/graph", tags=["graph"])


def _check_legal_admin(user: CurrentUser) -> None:
    if not (user.is_superuser or user.is_legal_admin):
        raise HTTPException(status_code=403, detail="仅管理员可执行该操作")


@router.get("/knowledge")
async def graph_knowledge(
    max_nodes: Optional[int] = None,
    _: CurrentUser = Depends(get_current_user),
):
    return await graph_service.query_graph(max_nodes)


@router.post("/rebuild")
async def graph_rebuild(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _check_legal_admin(user)
    result = await graph_service.build_graph(db)
    if not result.get("ok"):
        raise HTTPException(status_code=503, detail="Neo4j 不可用或构建失败")
    return {"message": "图谱重建完成", **result}


@router.get("/stats")
async def graph_stats(_: CurrentUser = Depends(get_current_user)):
    return await graph_service.get_stats()


@router.get("/law-versions")
async def law_versions(
    at_date: str,
    keyword: Optional[str] = None,
    _: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """时间旅行查询：返回 at_date 时点生效（未废止）的法律版本。"""
    try:
        at = datetime.strptime(at_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式须为 YYYY-MM-DD")
    conds = [
        LegalDocument.doc_type.in_(["法律", "行政法规", "司法解释"]),
        and_(
            or_(LegalDocument.effective_date.is_(None), LegalDocument.effective_date <= at),
            or_(LegalDocument.abolished_date.is_(None), LegalDocument.abolished_date > at),
        ),
    ]
    if keyword:
        like = f"%{keyword.strip()}%"
        conds.append(or_(LegalDocument.title.like(like), LegalDocument.content.like(like)))
    result = await db.execute(
        select(LegalDocument).where(*conds).order_by(LegalDocument.effective_date)
    )
    docs = result.scalars().all()
    return {
        "at_date": at_date,
        "items": [
            {
                "id": d.id,
                "title": d.title,
                "version": d.version,
                "effective_date": d.effective_date,
                "abolished_date": d.abolished_date,
                "effectiveness": d.effectiveness,
                "summary": (d.summary or "")[:120],
            }
            for d in docs
        ],
        "total": len(docs),
    }
