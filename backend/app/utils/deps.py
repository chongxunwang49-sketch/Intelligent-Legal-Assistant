# -*- coding: utf-8 -*-
"""
智法通 V2 —— 认证与授权依赖

RBAC 三级判定优先级：is_superuser > legal_admin 角色 > 显式权限码。
- get_current_user: 解析 Bearer access token
- require_permission(code): 业务权限码工厂（如 analysis:view / knowledge:manage）
- get_current_superuser: 仅超级管理员（用户管理模块）
进程内用户缓存 TTL 60s；角色/状态/资料变更后调用 invalidate_user_cache 即时失效。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import Permission, Role, User
from app.utils.security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)

_LEGAL_ADMIN_ROLE = "legal_admin"


@dataclass
class CurrentUser:
    id: int
    username: str
    is_superuser: bool
    is_active: bool
    role_codes: list[str] = field(default_factory=list)
    permission_codes: list[str] = field(default_factory=list)

    @property
    def is_legal_admin(self) -> bool:
        return _LEGAL_ADMIN_ROLE in self.role_codes or self.is_superuser

    def has_permission(self, code: str) -> bool:
        if self.is_superuser or self.is_legal_admin:
            return True
        return code in self.permission_codes

    def can_view_analysis(self) -> bool:
        """仪表盘/数据分析：admin / legal_admin。"""
        return self.has_permission("analysis:view")

    def can_manage_knowledge(self) -> bool:
        """知识库上传/删除：admin / legal_admin。"""
        return self.has_permission("knowledge:manage")


# ---------------- 进程内缓存 ----------------
_CACHE_TTL = 60
_user_cache: dict[int, tuple[float, Optional[CurrentUser]]] = {}


def invalidate_user_cache(user_id: int) -> None:
    _user_cache.pop(user_id, None)


def invalidate_all_user_cache() -> None:
    _user_cache.clear()


async def _load_current_user(user_id: int, db: AsyncSession) -> Optional[CurrentUser]:
    """按需加载并缓存用户（含角色/权限码）。"""
    cached = _user_cache.get(user_id)
    if cached and cached[0] > time.time():
        return cached[1]
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    cu: Optional[CurrentUser] = None
    if user is not None:
        role_codes = [r.code for r in user.roles]
        perm_codes = {
            p.code for r in user.roles for p in r.permissions if p.code
        }
        cu = CurrentUser(
            id=user.id,
            username=user.username,
            is_superuser=user.is_superuser,
            is_active=user.is_active,
            role_codes=role_codes,
            permission_codes=sorted(perm_codes),
        )
    _user_cache[user_id] = (time.time() + _CACHE_TTL, cu)
    return cu


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录凭证无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    payload = decode_token(credentials.credentials)
    if not payload:
        raise unauthorized
    if payload.get("type") != "access":
        raise unauthorized
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise unauthorized
    cu = await _load_current_user(user_id, db)
    if cu is None:
        raise unauthorized
    if not cu.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员"
        )
    return cu


def require_permission(code: str):
    """返回依赖：当前用户须具备指定权限码（superuser/legal_admin 自动放行）。"""

    async def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.has_permission(code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"无权限执行该操作（需要权限：{code}）",
            )
        return user

    return checker


async def get_current_superuser(
    user: CurrentUser = Depends(get_current_user),
) -> CurrentUser:
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅超级管理员可访问",
        )
    return user
