# -*- coding: utf-8 -*-
"""智法通 V2 —— 仪表盘 API。"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis import QueryLog
from app.models.contract import Contract
from app.models.knowledge import LegalDocument
from app.models.user import User
from app.models.qa import Conversation
from app.utils.deps import require_permission

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
_manager = require_permission("analysis:view")


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)):
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    q_today = await db.scalar(select(func.count(QueryLog.id)).where(QueryLog.created_at >= today_start)) or 0
    c_today = await db.scalar(select(func.count(Contract.id)).where(Contract.created_at >= today_start)) or 0
    return {
        "today_queries": q_today,
        "today_contract_reviews": c_today,
        "knowledge_documents": await db.scalar(select(func.count(LegalDocument.id))) or 0,
        "total_users": await db.scalar(select(func.count(User.id))) or 0,
        "total_conversations": await db.scalar(select(func.count(Conversation.id))) or 0,
        "total_contracts": await db.scalar(select(func.count(Contract.id))) or 0,
    }


@router.get("/recent-activities")
async def recent_activities(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    qrows = (await db.execute(select(QueryLog).order_by(QueryLog.created_at.desc()).limit(limit))).scalars().all()
    crows = (await db.execute(select(Contract).order_by(Contract.created_at.desc()).limit(limit))).scalars().all()
    activities = []
    for q in qrows:
        activities.append(
            {"type": "qa", "title": "法律问答", "detail": q.query_text[:60], "time": q.created_at}
        )
    for c in crows:
        activities.append(
            {"type": "contract", "title": f"合同·{c.title[:20]}", "detail": f"状态 {c.status}", "time": c.created_at}
        )
    activities.sort(key=lambda x: x["time"], reverse=True)
    return {"items": activities[:limit]}


@router.get("/domain-distribution")
async def domain_distribution(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now() - timedelta(days=days)
    rows = (await db.execute(select(QueryLog.category).where(QueryLog.created_at >= since))).scalars().all()
    cnt = Counter(c or "其他" for c in rows)
    return {"items": [{"name": k, "value": v} for k, v in cnt.most_common()]}


@router.get("/trends")
async def trends(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now() - timedelta(days=days)
    rows = (await db.execute(select(QueryLog.created_at).where(QueryLog.created_at >= since))).scalars().all()
    buckets: dict[str, int] = defaultdict(int)
    for ts in rows:
        buckets[ts.strftime("%Y-%m-%d")] += 1
    return {"items": [{"date": k, "count": v} for k, v in sorted(buckets.items())]}
