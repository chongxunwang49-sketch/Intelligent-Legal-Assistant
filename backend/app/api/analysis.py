# -*- coding: utf-8 -*-
"""智法通 V2 —— 数据分析 API（热点/引用统计/聚类/趋势/概览）。"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analysis import CitationStat, QueryLog
from app.models.knowledge import LegalDocument
from app.models.user import User
from app.models.qa import Conversation
from app.models.contract import Contract
from app.utils.deps import get_current_user, require_permission

router = APIRouter(prefix="/analysis", tags=["analysis"])
_manager = require_permission("analysis:view")


def _since(days: int) -> datetime:
    return datetime.now() - timedelta(days=days)


@router.get("/hot-topics")
async def hot_topics(
    days: int = 30,
    top_n: int = 10,
    _=Depends(_manager),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)
    rows = (await db.execute(select(QueryLog).where(QueryLog.created_at >= since))).scalars().all()
    cnt: Counter = Counter()
    samples: dict[str, list[str]] = defaultdict(list)
    for q in rows:
        c = q.category or "其他"
        cnt[c] += 1
        if len(samples[c]) < 3:
            samples[c].append(q.query_text[:60])
    total = sum(cnt.values()) or 1
    return {
        "items": [
            {
                "category": c,
                "count": n,
                "ratio": round(n / total, 3),
                "samples": samples[c],
            }
            for c, n in cnt.most_common(top_n)
        ]
    }


@router.get("/citations")
async def citations(
    days: int = 30,
    top_n: int = 10,
    _=Depends(_manager),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)
    rows = (await db.execute(select(CitationStat).where(CitationStat.stat_date >= since))).scalars().all()
    agg: dict[int, list] = defaultdict(list)  # doc_id -> [counts, pos, neg]
    for r in rows:
        agg[r.document_id].append((r.citation_count or 0, r.positive_feedback_count or 0, r.negative_feedback_count or 0))
    doc_ids = list(agg.keys())
    titles: dict[int, str] = {}
    if doc_ids:
        rows_d = (await db.execute(select(LegalDocument.id, LegalDocument.title).where(LegalDocument.id.in_(doc_ids)))).all()
        titles = {r[0]: r[1] for r in rows_d}
    out = []
    for did, vals in agg.items():
        total = sum(v[0] for v in vals)
        pos = sum(v[1] for v in vals)
        neg = sum(v[2] for v in vals)
        out.append(
            {
                "document_id": did,
                "title": titles.get(did, "未知文档"),
                "citation_count": total,
                "positive_rate": round(pos / max(pos + neg, 1), 2),
            }
        )
    out.sort(key=lambda x: x["citation_count"], reverse=True)
    return {"items": out[:top_n]}


@router.get("/user-clusters")
async def user_clusters(
    days: int = 30,
    _=Depends(_manager),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)
    qrows = (await db.execute(select(QueryLog).where(QueryLog.created_at >= since))).scalars().all()
    by_user: dict[int, list[QueryLog]] = defaultdict(list)
    for q in qrows:
        if q.user_id:
            by_user[q.user_id].append(q)
    users: dict[int, str] = {}
    if by_user:
        rows = (await db.execute(select(User.id, User.username).where(User.id.in_(list(by_user))))).all()
        users = {r[0]: r[1] for r in rows}
    features = []
    for uid, qs in by_user.items():
        cats = {q.category for q in qs}
        lat = [q.latency_ms or 0 for q in qs if q.latency_ms]
        features.append(
            {
                "user_id": uid,
                "username": users.get(uid, str(uid)),
                "query_count": len(qs),
                "domain_diversity": len(cats),
                "avg_latency_ms": int(statistics.mean(lat)) if lat else 0,
            }
        )
    return {"items": features, "n_clusters": 0, "scatter_data": []}


@router.get("/trends")
async def trends(
    days: int = 30,
    granularity: str = "day",
    _=Depends(_manager),
    db: AsyncSession = Depends(get_db),
):
    since = _since(days)
    rows = (await db.execute(select(QueryLog.created_at).where(QueryLog.created_at >= since))).scalars().all()
    buckets: dict[str, int] = defaultdict(int)
    for ts in rows:
        if granularity == "month":
            key = ts.strftime("%Y-%m")
        elif granularity == "week":
            key = ts.strftime("%Y-W%W")
        else:
            key = ts.strftime("%Y-%m-%d")
        buckets[key] += 1
    ordered = sorted(buckets.items())
    return {"items": [{"date": k, "count": v} for k, v in ordered]}


@router.get("/overview")
async def overview(_=Depends(_manager), db: AsyncSession = Depends(get_db)):
    since = _since(30)
    q_total = await db.scalar(select(func.count(QueryLog.id))) or 0
    q_30 = await db.scalar(select(func.count(QueryLog.id)).where(QueryLog.created_at >= since)) or 0
    docs = await db.scalar(select(func.count(LegalDocument.id))) or 0
    users = await db.scalar(select(func.count(User.id))) or 0
    convs = await db.scalar(select(func.count(Conversation.id))) or 0
    contracts = await db.scalar(select(func.count(Contract.id))) or 0
    return {
        "total_queries": q_total,
        "queries_last_30d": q_30,
        "total_documents": docs,
        "total_users": users,
        "total_conversations": convs,
        "total_contracts": contracts,
    }
