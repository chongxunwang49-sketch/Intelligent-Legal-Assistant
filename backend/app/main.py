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


async def _ensure_vector_index() -> None:
    """为已提交但未分块的文档构建向量索引（幂等，统一 metadata 路径）。"""
    from app.services.knowledge_service import knowledge_service

    try:
        async with AsyncSessionLocal() as db:
            n = await knowledge_service.rebuild_index_for_docs(db)
            if n:
                logger.info("向量索引构建完成：共 %d 篇文档", n)
            else:
                count = knowledge_service.vector_store.count()
                logger.info("向量库现有 %d 个分块，无需重建", count)
    except Exception as exc:
        logger.warning("向量索引初始化跳过（可稍后手动重建）: %s", exc)


async def _ensure_graph() -> None:
    """Neo4j 可用且图谱为空时自动构建（幂等）。"""
    from app.services.graph_service import graph_service

    if not settings.NEO4J_ENABLED:
        return
    try:
        if not await graph_service.verify_connectivity():
            logger.warning("Neo4j 不可达，图谱初始化跳过")
            return
        stats = await graph_service.get_stats()
        if stats.get("available") and stats.get("total", 0) == 0:
            async with AsyncSessionLocal() as db:
                result = await graph_service.build_graph(db)
                logger.info("知识图谱构建完成: %s", result.get("stats"))
    except Exception as exc:
        logger.warning("知识图谱初始化跳过: %s", exc)


async def _shutdown_llm_services() -> None:
    try:
        from app.rag.embedding import embedding_service
        from app.rag.reranker import reranker

        await embedding_service.close()
        await reranker.close()
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("启动 %s v%s", settings.APP_NAME, settings.APP_VERSION)
    await _wait_for_db()
    await _init_schema_and_seed()
    _ensure_dirs()
    await _ensure_vector_index()
    await _ensure_graph()
    yield
    await _shutdown_llm_services()
    try:
        from app.services.graph_service import graph_service

        await graph_service.close_driver()
    except Exception:
        pass
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
from app.api import (
    analysis,
    auth,
    contract,
    dashboard,
    graph,
    knowledge,
    notification,
    qa,
    user,
)  # noqa: E402

for r in (
    auth.router,
    notification.router,
    user.router,
    knowledge.router,
    qa.router,
    contract.router,
    analysis.router,
    dashboard.router,
    graph.router,
):
    app.include_router(r, prefix=settings.API_PREFIX)

# 静态文件（上传的头像/合同原文件）
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount(
    f"{settings.API_PREFIX}/uploads",
    StaticFiles(directory=settings.UPLOAD_DIR),
    name="uploads",
)
