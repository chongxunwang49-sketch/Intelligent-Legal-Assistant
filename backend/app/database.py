# -*- coding: utf-8 -*-
"""智法通 V2 —— 异步数据库引擎与会话管理（SQLAlchemy 2.0）。"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime


def naive_utcnow() -> datetime:
    """统一的时间戳函数：存储无时区的 UTC（naive），与 MySQL DATETIME 兼容。"""
    return datetime.utcnow()

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """ORM 声明基类。"""


engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=False,
    pool_recycle=3600,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖：每请求一个会话。"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
