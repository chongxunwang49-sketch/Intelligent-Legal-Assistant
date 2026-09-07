# -*- coding: utf-8 -*-
"""
智法通 V2 —— FastAPI 应用入口

生命周期：等待 MySQL → 建表 → 幂等种子 → 索引/图谱(按需) → 注册路由/中间件。
启动自检可通过 /health 查看。
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.database import Base, AsyncSessionLocal, engine
from app.init_data import init_seed_data
from app.redis_client import close_redis

logger = logging.getLogger("uvicorn.error")
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------- 生命周期 ----------------
async def _wait_for_db() -> None:
    for attempt in range(10):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception as exc:
            delay = min(3 * (attempt + 1), 10)
            logger.warning("等待 MySQL 就绪 (%d/10): %s", attempt + 1, exc)
            await asyncio.sleep(delay)
    raise RuntimeError("MySQL 在 60s 内未就绪，启动中止")


async def _init_schema_and_seed() -> None:
    import app.models  # noqa: F401  注册全部表

    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async with AsyncSessionLocal() as db:
                await init_seed_data(db)
            return
        except Exception as exc:
            msg = str(exc)
            retriable = any(
                k in msg
                for k in ("doesn't exist", "Can't connect", "Connection refused", "Unknown database")
            )
            if not retriable:
                raise
            logger.warning("建表/种子重试 (%d/5): %s", attempt + 1, exc)
            await asyncio.sleep(3 * (attempt + 1))
    raise RuntimeError("建表/种子多次重试后仍失败")


def _ensure_dirs() -> None:
    for d in (settings.UPLOAD_DIR, settings.CHROMA_PERSIST_DIR):
        Path(d).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("启动 %s v%s", settings.APP_NAME, settings.APP_VERSION)
    await _wait_for_db()
    await _init_schema_and_seed()
    _ensure_dirs()
    # 索引/图谱构建在对应里程碑接入（M2/M5）
    yield
    await close_redis()
    await engine.dispose()


app.router.lifespan_context = lifespan


# ---------------- 中间件 ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def process_time_middleware(request: Request, call_next):
    import time

    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start:.4f}"
    return response


# ---------------- 全局异常 ----------------
@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "message": "参数校验失败"})


@app.exception_handler(HTTPException)
async def http_exc_handler(_: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


# ---------------- 基础端点 ----------------
@app.get("/")
async def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "status": "running"}


@app.get("/health")
async def health():
    db_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "version": settings.APP_VERSION,
    }


# ---------------- 路由注册（按里程碑渐进接入）----------------
from app.api import auth, notification, user  # noqa: E402

for r in (auth.router, notification.router, user.router):
    app.include_router(r, prefix=settings.API_PREFIX)

# M2+: qa / knowledge / analysis / dashboard / graph / contract 后续在此注册

# 静态文件（上传的头像/合同原文件）
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount(
    f"{settings.API_PREFIX}/uploads",
    StaticFiles(directory=settings.UPLOAD_DIR),
    name="uploads",
)
