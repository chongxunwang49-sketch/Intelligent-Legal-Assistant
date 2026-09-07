# -*- coding: utf-8 -*-
"""智法通 V2 —— 日额度服务（Redis 原子计数器）。

规则：普通用户 问答 50 次/日、合同审查 10 次/日；admin / legal_admin 不限额。
Redis 不可用时降级放行（记录日志），保证可用性。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from app.config import settings
from app.redis_client import get_redis
from app.utils.deps import CurrentUser

logger = logging.getLogger(__name__)

# resource_type -> 每日限额
DAILY_LIMITS = {
    "qa": settings.QUOTA_QA_DAILY,
    "contract": settings.QUOTA_CONTRACT_DAILY,
}


def _seconds_until_local_midnight() -> int:
    now = datetime.now()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((nxt - now).total_seconds())


def _is_unlimited(user: CurrentUser) -> bool:
    return user.is_superuser or "admin" in user.role_codes


class QuotaService:
    async def check_and_consume(
        self, user: CurrentUser, resource_type: str
    ) -> dict:
        """原子消费一次额度；返回 (allowed, remaining, limit)。"""
        if resource_type not in DAILY_LIMITS:
            return {"allowed": True, "remaining": -1, "limit": -1}
        if _is_unlimited(user):
            return {"allowed": True, "remaining": -1, "limit": -1}
        limit = DAILY_LIMITS[resource_type]
        redis = await get_redis()
        if redis is None:
            return {"allowed": True, "remaining": -1, "limit": limit}
        key = f"quota:{user.id}:{resource_type}:{datetime.now():%Y-%m-%d}"
        try:
            used = await redis.incr(key)
            if used == 1:
                await redis.expire(key, _seconds_until_local_midnight())
            if used > limit:
                await redis.decr(key)  # 回滚超额
                return {"allowed": False, "remaining": 0, "limit": limit}
            return {"allowed": True, "remaining": max(limit - used, 0), "limit": limit}
        except Exception as exc:  # pragma: no cover
            logger.warning("额度服务 Redis 异常，降级放行: %s", exc)
            return {"allowed": True, "remaining": -1, "limit": limit}

    async def get_quota(self, user: CurrentUser, resource_type: str) -> dict:
        """查询（不扣减）。remaining=-1 表示不限额。"""
        if resource_type not in DAILY_LIMITS:
            return {"used": 0, "remaining": -1, "limit": -1}
        if _is_unlimited(user):
            return {"used": -1, "remaining": -1, "limit": -1}
        limit = DAILY_LIMITS[resource_type]
        redis = await get_redis()
        if redis is None:
            return {"used": 0, "remaining": limit, "limit": limit}
        key = f"quota:{user.id}:{resource_type}:{datetime.now():%Y-%m-%d}"
        try:
            used = int(await redis.get(key) or 0)
        except Exception:
            used = 0
        return {
            "used": used,
            "remaining": max(limit - used, 0),
            "limit": limit,
        }


quota_service = QuotaService()
