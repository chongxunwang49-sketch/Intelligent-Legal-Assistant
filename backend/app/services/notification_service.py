# -*- coding: utf-8 -*-
"""智法通 V2 —— 通知服务。"""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationType
from app.models.notification import Notification


class NotificationService:
    async def create_notification(
        self,
        db: AsyncSession,
        user_id: int,
        title: str,
        content: str = "",
        type: NotificationType = NotificationType.SYSTEM,
        resource_type: Optional[str] = None,
        resource_id: Optional[int] = None,
    ) -> Notification:
        n = Notification(
            user_id=user_id,
            title=title,
            content=content,
            type=type,
            resource_type=resource_type,
            resource_id=resource_id,
            is_read=False,
        )
        db.add(n)
        await db.flush()
        return n

    async def get_notifications(
        self,
        db: AsyncSession,
        user_id: int,
        page: int = 1,
        page_size: int = 10,
        is_read: Optional[bool] = None,
    ) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)
        conds = [Notification.user_id == user_id]
        if is_read is not None:
            conds.append(Notification.is_read == is_read)
        total = await db.scalar(
            select(func.count(Notification.id)).where(*conds)
        )
        result = await db.execute(
            select(Notification)
            .where(*conds)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = result.scalars().all()
        unread = await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.is_read.is_(False)
            )
        )
        return {
            "items": [self._to_dict(n) for n in items],
            "total": total or 0,
            "unread_count": unread or 0,
            "page": page,
            "page_size": page_size,
        }

    async def get_unread_count(self, db: AsyncSession, user_id: int) -> int:
        return await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id, Notification.is_read.is_(False)
            )
        ) or 0

    async def mark_as_read(self, db: AsyncSession, notification_id: int, user_id: int) -> Notification:
        result = await db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        n = result.scalar_one_or_none()
        if n is None:
            raise HTTPException(status_code=404, detail="通知不存在")
        n.is_read = True
        await db.flush()
        return n

    async def mark_all_as_read(self, db: AsyncSession, user_id: int) -> int:
        result = await db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.is_read.is_(False))
            .values(is_read=True)
        )
        return result.rowcount or 0

    def _to_dict(self, n: Notification) -> dict:
        return {
            "id": n.id,
            "type": n.type.value if hasattr(n.type, "value") else n.type,
            "title": n.title,
            "content": n.content,
            "is_read": n.is_read,
            "resource_type": n.resource_type,
            "resource_id": n.resource_id,
            "created_at": n.created_at,
        }


notification_service = NotificationService()
