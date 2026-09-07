# -*- coding: utf-8 -*-
"""
智法通 V2 —— Rerank 精排微服务（两阶段检索第二阶段：Cross-Encoder 精排）

技术栈：sentence-transformers + FastAPI，在 pytorch 环境运行（需 torch）。
模型：  BAAI/bge-reranker-v2-m3（约 1.1GB，首次启动自动下载，可经 HF_ENDPOINT 镜像加速）

接口（与后端 reranker 客户端约定一致）：
  POST /rerank
      body: { "query": str, "documents": [str, ...], "top_n": int }
      resp: { "results": [{"index": int, "score": float}, ...] 按分数降序, "total": int, "model": str }
  GET  /health
      resp: { "status": "healthy"|"loading"|"unhealthy", "model": str, "device": str }

启动（pytorch 环境）：
  python rerank_service/server.py            # 默认 127.0.0.1:9999
  uvicorn rerank_service.server:app --host 0.0.0.0 --port 9999
环境变量：RERANK_HOST / RERANK_PORT / RERANK_MODEL / RERANK_DEVICE(auto|cpu|cuda)
"""
from __future__ import annotations

import os
import threading

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field

MODEL_NAME = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")
HOST = os.getenv("RERANK_HOST", "0.0.0.0")
PORT = int(os.getenv("RERANK_PORT", "9999"))
DEVICE = os.getenv("RERANK_DEVICE", "auto")

app = FastAPI(title="ZhiFaTong Rerank Service", version="1.0.0")

# 模型加载状态：跨请求共享，加载成本高（1.1GB）故只加载一次
_model = None
_model_lock = threading.Lock()
_ready = False


class RerankRequest(BaseModel):
    query: str = Field(..., min_length=1)
    documents: list[str] = Field(..., min_length=1)
    top_n: int = Field(5, ge=1, le=50)


class RerankResponse(BaseModel):
    results: list[dict]
    total: int
    model: str


def _resolve_device() -> str:
    if DEVICE != "auto":
        return DEVICE
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def load_model():
    """幂等地加载 CrossEncoder（线程安全）。"""
    global _model, _ready
    if _ready:
        return
    with _model_lock:
        if _ready:
            return
        from sentence_transformers import CrossEncoder

        device = _resolve_device()
        print(f"[rerank] 加载模型 {MODEL_NAME} @ {device} ...", flush=True)
        _model = CrossEncoder(MODEL_NAME, device=device)
        _ready = True
        print(f"[rerank] 模型加载完成，设备: {device}", flush=True)


@app.on_event("startup")
def _startup():
    # 后台线程预热，避免首个请求阻塞过久
    threading.Thread(target=load_model, daemon=True).start()


@app.get("/health")
def health():
    status = "healthy" if _ready else "loading"
    return {"status": status, "model": MODEL_NAME, "device": _resolve_device(), "ready": _ready}


@app.post("/rerank", response_model=RerankResponse)
def rerank(req: RerankRequest):
    load_model()  # 若尚未就绪则同步等待（首个请求）
    if _model is None:
        return {"results": [], "total": 0, "model": MODEL_NAME}
    # CrossEncoder.predict 直接返回相关性分数（越高越相关）
    scores = _model.predict([(req.query, d) for d in req.documents])
    scores = np.asarray(scores, dtype=float)
    # 按分数降序取 top_n
    order = np.argsort(-scores)[: req.top_n]
    results = [{"index": int(i), "score": float(scores[i])} for i in order]
    return {"results": results, "total": int(len(req.documents)), "model": MODEL_NAME}


if __name__ == "__main__":
    import uvicorn

    load_model()
    print(f"[rerank] 服务启动 http://{HOST}:{PORT}", flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")
