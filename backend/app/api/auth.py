# -*- coding: utf-8 -*-
"""智法通 V2 —— 认证路由。"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services import auth_service
from app.utils.deps import CurrentUser, get_current_user
from app.utils.file_parser import FileParseError

router = APIRouter(prefix="/auth", tags=["auth"])

_AVATAR_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
_WEAK_LOGIN_PASSWORDS = {"123456", "password", "admin", "12345678", "qwerty"}


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)
    phone: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ProfileUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=64)


def _serialize_me(user: User) -> dict:
    data = user.to_dict()
    perm_codes = sorted(
        {p.code for r in user.roles for p in r.permissions if p.code}
    )
    data["permission_codes"] = perm_codes
    return data


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if req.password.lower() in _WEAK_LOGIN_PASSWORDS:
        raise HTTPException(status_code=400, detail="密码过于简单")
    return await auth_service.register(db, req.username, req.email, req.password, req.phone)


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.login(db, req.username, req.password)


@router.post("/refresh")
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_service.refresh_access_token(db, req.refresh_token)


@router.get("/me")
async def me(user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    u = await auth_service.get_user_with_roles(db, user.id)
    if u is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    return _serialize_me(u)


@router.put("/me")
async def update_me(
    req: ProfileUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = await auth_service.update_profile(db, user.id, email=str(req.email) if req.email else None, phone=req.phone)
    return _serialize_me(u)


@router.post("/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in _AVATAR_EXT:
        raise HTTPException(status_code=400, detail="仅支持 png/jpg/jpeg/gif/webp 头像")
    if (file.content_type or "") not in _AVATAR_EXT.values():
        raise HTTPException(status_code=400, detail="文件类型校验失败")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="头像大小不能超过 5MB")
    avatars_dir = os.path.join(settings.UPLOAD_DIR, "avatars")
    os.makedirs(avatars_dir, exist_ok=True)
    fname = f"avatar_{user.id}_{uuid.uuid4().hex}{ext}"
    with open(os.path.join(avatars_dir, fname), "wb") as f:
        f.write(data)
    # 删除旧头像文件（若存在）
    u = await auth_service.get_user_with_roles(db, user.id)
    if u and u.avatar:
        old = u.avatar.split("/")[-1]
        old_path = os.path.join(avatars_dir, old)
        if old != fname and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
    url = f"{settings.API_PREFIX}/uploads/avatars/{fname}"
    u = await auth_service.set_avatar(db, user.id, url)
    return _serialize_me(u)


@router.delete("/avatar")
async def delete_avatar(
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    u = await auth_service.get_user_with_roles(db, user.id)
    if u and u.avatar:
        old_path = os.path.join(settings.UPLOAD_DIR, "avatars", u.avatar.split("/")[-1])
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
    u = await auth_service.clear_avatar(db, user.id)
    return _serialize_me(u)


@router.put("/password")
async def change_password(
    req: PasswordChange,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await auth_service.change_password(db, user.id, req.old_password, req.new_password)
    return {"message": "密码修改成功"}
