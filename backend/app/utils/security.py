# -*- coding: utf-8 -*-
"""
智法通 V2 —— 安全工具
密码哈希(bcrypt)、JWT(HS256, type=access/refresh 区分)、XSS 净化(单一来源)。
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------- 密码 ----------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ---------------- JWT ----------------
def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: int) -> str:
    return _create_token(
        str(user_id),
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: int) -> str:
    return _create_token(
        str(user_id),
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Optional[dict]:
    """解码并校验签名；返回 payload，失败返回 None（不区分原因，避免侧信道）。"""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# ---------------- XSS 净化（单一来源）----------------
# 危险标签：内容类（script/style/iframe/object/embed/link/meta/base/form）
_DANGEROUS_TAGS = re.compile(
    r"<\s*(script|style|iframe|object|embed|link|meta|base|form|applet|svg|math)\b[^>]*>.*?<\s*/\s*\1\s*>"
    r"|<\s*(script|style|iframe|object|embed|link|meta|base|form|applet|svg|math)\b[^>]*/?>",
    flags=re.IGNORECASE | re.DOTALL,
)
_EVENT_HANDLERS = re.compile(r"\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)", flags=re.IGNORECASE)
_JAVASCRIPT_URI = re.compile(r"\s*(href|src|action)\s*=\s*([\"']?)\s*javascript:[^\"'>\s]*", flags=re.IGNORECASE)


def sanitize_html_content(text: str | None) -> str:
    """清洗不可信文本中的 HTML/脚本，返回安全文本。

    - 普通 `<`/`>` 转义为实体（文本当作文本处理）；
    - 若命中危险标签整体剔除其内容；
    - 移除 on* 事件属性与 javascript: 伪协议。
    """
    if not text:
        return text or ""
    text = str(text)
    text = _DANGEROUS_TAGS.sub("", text)
    text = _EVENT_HANDLERS.sub("", text)
    text = _JAVASCRIPT_URI.sub("", text)
    return html.escape(text, quote=False)
