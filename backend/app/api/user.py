# -*- coding: utf-8 -*-
"""智法通 V2 —— 用户管理路由（仅超级管理员）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import Role, User, role_permission, user_role
from app.services import auth_service
from app.utils.deps import (
    CurrentUser,
    get_current_superuser,
    invalidate_user_cache,
)
from app.utils.security import hash_password

router = APIRouter(prefix="/users", tags=["user-management"])

_WEAK = {"123456", "password", "admin123", "12345678", "qwerty"}


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)
    phone: Optional[str] = None
    role_codes: list[str] = ["user"]


class UserRolesUpdate(BaseModel):
    role_codes: list[str]


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPassword(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=64)


def _serialize_user(user: User) -> dict:
    data = user.to_dict()
    data["permission_codes"] = sorted(
        {p.code for r in user.roles for p in r.permissions if p.code}
    )
    return data


async def _load_user(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


async def _resolve_roles(db: AsyncSession, role_codes: list[str]) -> list[Role]:
    if not role_codes:
        return []
    result = await db.execute(select(Role).where(Role.code.in_(role_codes)))
    roles = result.scalars().all()
    found = {r.code for r in roles}
    missing = set(role_codes) - found
    if missing:
        raise HTTPException(status_code=400, detail=f"角色不存在: {', '.join(missing)}")
    return list(roles)


@router.get("")
async def list_users(
    page: int = 1,
    page_size: int = 10,
    keyword: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    _: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    conds = []
    if keyword:
        like = f"%{keyword.strip()}%"
        conds.append(
            or_(User.username.like(like), User.email.like(like), User.phone.like(like))
        )
    if status is not None:
        if status == "active":
            conds.append(User.is_active.is_(True))
        elif status == "disabled":
            conds.append(User.is_active.is_(False))
    base = select(User)
    if role:
        base = base.join(user_role).join(Role).where(Role.code == role)
    total = await db.scalar(
        select(func.count()).select_from(base.subquery())
    )
    result = await db.execute(
        base.options(selectinload(User.roles).selectinload(Role.permissions))
        .where(*conds)
        .order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    users = result.scalars().all()
    return {
        "items": [_serialize_user(u) for u in users],
        "total": total or 0,
        "page": page,
        "page_size": page_size,
    }


@router.get("/roles")
async def list_roles(
    _: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Role).order_by(Role.id))
    roles = result.scalars().all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "code": r.code,
            "description": r.description,
            "is_default": r.is_default,
            "permission_codes": [p.code for p in r.permissions],
        }
        for r in roles
    ]


@router.post("", status_code=201)
async def create_user(
    req: UserCreate,
    _: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if req.password.lower() in _WEAK:
        raise HTTPException(status_code=400, detail="密码过于简单")
    clash = await db.execute(
        select(User.id).where((User.username == req.username) | (User.email == str(req.email)))
    )
    if clash.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在")
    roles = await _resolve_roles(db, req.role_codes)
    user = User(
        username=req.username,
        email=str(req.email),
        hashed_password=hash_password(req.password),
        phone=req.phone or None,
        is_active=True,
        is_superuser=False,
    )
    user.roles = roles
    db.add(user)
    await db.commit()
    u = await _load_user(db, user.id)
    invalidate_user_cache(u.id)
    return _serialize_user(u)


@router.put("/{user_id}/roles")
async def set_user_roles(
    user_id: int,
    req: UserRolesUpdate,
    admin: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    user = await _load_user(db, user_id)
    # 保护：不能移除自己的 admin 角色 / 不能解除自身超管
    if user.id == admin.id and "admin" not in req.role_codes:
        raise HTTPException(status_code=400, detail="不能移除自己的管理员角色")
    if user.id == admin.id and "admin" in req.role_codes and not user.is_superuser:
        pass
    roles = await _resolve_roles(db, req.role_codes)
    user.roles = roles
    # 超级管理员标记与 admin 角色保持一致（内置超管保持超管）
    if user.is_superuser and user.id != admin.id and "admin" not in req.role_codes:
        # 允许管理员被降级时同步解除超管，但不允许对自己执行
        user.is_superuser = False
    await db.commit()
    u = await _load_user(db, user.id)
    invalidate_user_cache(u.id)
    return _serialize_user(u)


@router.put("/{user_id}/status")
async def set_user_status(
    user_id: int,
    req: UserStatusUpdate,
    admin: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if user_id == admin.id and not req.is_active:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    user = await _load_user(db, user_id)
    user.is_active = req.is_active
    await db.commit()
    invalidate_user_cache(user_id)
    return _serialize_user(user)


@router.put("/{user_id}")
async def update_user(
    user_id: int,
    req: UserUpdate,
    _: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    user = await _load_user(db, user_id)
    if req.email is not None:
        clash = await db.execute(
            select(User.id).where(User.email == str(req.email), User.id != user_id)
        )
        if clash.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="邮箱已被使用")
        user.email = str(req.email)
    if req.phone is not None:
        user.phone = req.phone.strip() or None
    if req.is_active is not None:
        user.is_active = req.is_active
    await db.commit()
    invalidate_user_cache(user_id)
    return _serialize_user(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    admin: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    user = await _load_user(db, user_id)
    await db.delete(user)
    await db.commit()
    invalidate_user_cache(user_id)
    return {"message": "用户已删除"}


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    req: ResetPassword,
    admin: CurrentUser = Depends(get_current_superuser),
    db: AsyncSession = Depends(get_db),
):
    user = await _load_user(db, user_id)
    if req.new_password.lower() in _WEAK:
        raise HTTPException(status_code=400, detail="密码过于简单")
    user.hashed_password = hash_password(req.new_password)
    await db.commit()
    invalidate_user_cache(user_id)
    return {"message": "密码已重置"}
