# -*- coding: utf-8 -*-
"""智法通 V2 —— 认证服务（注册/登录/刷新/资料/改密/防爆破）。"""
from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import naive_utcnow
from app.models.user import Role, User
from app.redis_client import get_redis
from app.utils.deps import invalidate_user_cache
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

# ---------------- 密码强度 ----------------
_WEAK_PASSWORDS = {
    "123456", "12345678", "123456789", "password", "password1", "admin",
    "admin123", "1234567890", "qwerty", "abc123", "111111", "666666",
    "88888888", "a123456", "admin888", "root", "123123",
}
_PASSWORD_MIN_LEN = 8


def _validate_password_strength(password: str) -> None:
    if len(password) < _PASSWORD_MIN_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码长度至少 {_PASSWORD_MIN_LEN} 位",
        )
    if password.lower() in _WEAK_PASSWORDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="密码过于简单，请更换"
        )
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码须同时包含字母和数字",
        )


# ---------------- 内部工具 ----------------
def _issue_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "refresh_token": create_refresh_token(user.id),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def get_user_with_roles(db: AsyncSession, user_id: int) -> Optional[User]:
    return await _load_user_with_roles(db, user_id)


async def _load_user_with_roles(db: AsyncSession, user_id: int) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    return result.scalar_one_or_none()


async def _get_default_role(db: AsyncSession) -> Optional[Role]:
    result = await db.execute(select(Role).where(Role.is_default.is_(True)))
    return result.scalar_one_or_none()


# ---------------- 业务函数 ----------------
async def register(
    db: AsyncSession,
    username: str,
    email: str,
    password: str,
    phone: Optional[str] = None,
) -> dict:
    username = (username or "").strip()
    email = (email or "").strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9_]{3,32}", username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名须为 3-32 位字母/数字/下划线",
        )
    _validate_password_strength(password)

    existing = await db.execute(
        select(User.id).where((User.username == username) | (User.email == email))
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名或邮箱已被注册",
        )

    user = User(
        username=username,
        email=email,
        hashed_password=hash_password(password),
        phone=phone or None,
        is_active=True,
        is_superuser=False,
    )
    user.roles = []  # 显式初始化，避免 async 懒加载
    db.add(user)
    await db.flush()
    default_role = await _get_default_role(db)
    if default_role is not None:
        user.roles.append(default_role)
    await db.commit()
    user = await _load_user_with_roles(db, user.id)
    tokens = _issue_tokens(user)
    tokens["user"] = user.to_dict()
    return tokens


async def login(db: AsyncSession, username: str, password: str) -> dict:
    """登录（用户名或邮箱）。带 Redis 防爆破：连续失败 5 次锁定 30 分钟。"""
    identifier = (username or "").strip().lower()
    redis = await get_redis()

    fail_key = f"login_fail:{identifier}"
    if redis is not None:
        try:
            attempts = int(await redis.get(fail_key) or 0)
            if attempts >= settings.LOGIN_FAIL_MAX_ATTEMPTS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="尝试次数过多，账号已锁定 30 分钟，请稍后再试",
                )
        except HTTPException:
            raise
        except Exception:
            redis = None  # 降级放行

    result = await db.execute(
        select(User).where(
            (User.username == identifier) | (User.email == identifier)
        )
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.hashed_password):
        if redis is not None:
            try:
                n = await redis.incr(fail_key)
                if n == 1:
                    await redis.expire(fail_key, settings.LOGIN_FAIL_TTL_SECONDS)
            except Exception:
                pass
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员"
        )
    # 登录成功：清除失败计数、更新 last_login
    if redis is not None:
        try:
            await redis.delete(fail_key)
        except Exception:
            pass
    user.last_login = naive_utcnow()
    await db.commit()
    user = await _load_user_with_roles(db, user.id)
    tokens = _issue_tokens(user)
    tokens["user"] = user.to_dict()
    return tokens


async def refresh_access_token(db: AsyncSession, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新令牌无效",
        )
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效"
        )
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用"
        )
    # 令牌轮换：同时签发新的 access 与 refresh
    tokens = _issue_tokens(user)
    return tokens


async def update_profile(db, user_id: int, email=None, phone=None) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if email is not None and email.strip().lower() != user.email:
        clash = await db.execute(
            select(User.id).where(User.email == email.strip().lower(), User.id != user_id)
        )
        if clash.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="该邮箱已被其他账号使用")
        user.email = email.strip().lower()
    if phone is not None:
        user.phone = phone.strip() or None
    await db.commit()
    await db.refresh(user)
    invalidate_user_cache(user_id)
    return user


async def change_password(db, user_id: int, old_password: str, new_password: str) -> None:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not verify_password(old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if old_password == new_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    _validate_password_strength(new_password)
    user.hashed_password = hash_password(new_password)
    await db.commit()
    invalidate_user_cache(user_id)


async def set_avatar(db, user_id: int, avatar_url: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.avatar = avatar_url
    await db.commit()
    await db.refresh(user)
    invalidate_user_cache(user_id)
    return user


async def clear_avatar(db, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.avatar = None
    await db.commit()
    await db.refresh(user)
    invalidate_user_cache(user_id)
    return user
