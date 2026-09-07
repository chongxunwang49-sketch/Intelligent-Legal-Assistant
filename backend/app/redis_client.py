# -*- coding: utf-8 -*-
"""智法通 V2 —— Redis 连接（防爆破锁 / 日额度 / 分布式锁）。"""
from __future__ import annotations

import asyncio
from typing import Optional

import redis.asyncio as aioredis

from app.config import settings

_pool: Optional[aioredis.Redis] = None
_pool_lock = asyncio.Lock()


async def get_redis() -> Optional[aioredis.Redis]:
    """惰性单例；Redis 不可用时返回 None（调用方按降级处理）。"""
    global _pool
    if _pool is not None:
        return _pool
    async with _pool_lock:
        if _pool is not None:
            return _pool
        try:
            _pool = aioredis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=5,
                max_connections=settings.REDIS_POOL_SIZE,
            )
            await _pool.ping()
        except Exception:
            _pool = None
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        try:
            await _pool.aclose()
        except Exception:
            pass
        _pool = None
