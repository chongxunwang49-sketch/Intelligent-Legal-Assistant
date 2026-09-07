# -*- coding: utf-8 -*-
"""用户/角色/权限模型（RBAC 三角色体系）。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, naive_utcnow

# ---------- 多对多关联表 ----------
user_role = Table(
    "user_role",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "user_id",
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("created_at", DateTime, default=naive_utcnow),
)

role_permission = Table(
    "role_permission",
    Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "role_id",
        Integer,
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("created_at", DateTime, default=naive_utcnow),
)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    resource: Mapped[str] = mapped_column(String(50), default="")
    action: Mapped[str] = mapped_column(String(50), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "resource": self.resource,
            "action": self.action,
            "description": self.description,
        }


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50))
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=naive_utcnow, onupdate=naive_utcnow
    )

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_permission,
        backref="roles",
        lazy="selectin",
    )


    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "is_default": self.is_default,
            "permissions": [p.to_dict() for p in self.permissions],
        }


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True)
    avatar: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=naive_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=naive_utcnow, onupdate=naive_utcnow
    )

    roles: Mapped[list[Role]] = relationship(
        secondary=user_role,
        backref="users",
        lazy="selectin",
    )

    @property
    def role_codes(self) -> list[str]:
        return [r.code for r in self.roles]

    def to_dict(self, with_roles: bool = True) -> dict:
        data = {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "phone": self.phone,
            "avatar": self.avatar,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "last_login": self.last_login,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if with_roles:
            data["roles"] = [r.to_dict() for r in self.roles]
        return data
