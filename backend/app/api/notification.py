# -*- coding: utf-8 -*-
"""智法通 V2 —— 通知路由。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.notification_service import notification_service
from app.utils.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/")
async def list_notifications(
    page: int = 1,
    page_size: int = 10,
    is_read: Optional[bool] = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await notification_service.get_notifications(
        db, user.id, page=page, page_size=page_size, is_read=is_read
    )


@router.get("/unread-count")
async def unread_count(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"unread_count": await notification_service.get_unread_count(db, user.id)}


@router.put("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await notification_service.mark_as_read(db, notification_id, user.id)
    return {"message": "ok"}


@router.put("/read-all")
async def mark_all_read(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    count = await notification_service.mark_all_as_read(db, user.id)
    return {"message": "ok", "updated": count}
