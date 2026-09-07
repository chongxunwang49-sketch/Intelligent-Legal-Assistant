# -*- coding: utf-8 -*-
"""智法通 V2 —— 法律问答路由（含 SSE 流式与日额度）。"""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.qa_service import qa_service
from app.services.quota_service import quota_service
from app.utils.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/qa", tags=["qa"])


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    conversation_id: Optional[int] = None


class FeedbackRequest(BaseModel):
    message_id: int
    is_positive: bool
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


class RenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


async def _consume_qa_quota(user: CurrentUser) -> dict:
    res = await quota_service.check_and_consume(user, "qa")
    if not res["allowed"]:
        raise HTTPException(status_code=429, detail="今日问答额度已用完，请明日再试或升级账号")
    return res


@router.post("/ask")
async def ask(
    req: AskRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quota = await _consume_qa_quota(user)
    data = await qa_service.ask(db, user.id, req.question, req.conversation_id)
    data["remaining"] = quota.get("remaining", -1)
    return data


@router.post("/ask/stream")
async def ask_stream(
    req: AskRequest,
    request: Request,
    user: CurrentUser = Depends(get_current_user),
):
    quota = await _consume_qa_quota(user)

    async def event_generator():
        # 自建会话：避免依赖会话在流式期间被清理
        from app.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db2:
            try:
                async for ev in qa_service.ask_stream(db2, user.id, req.question, req.conversation_id):
                    if await request.is_disconnected():
                        break
                    data = json.dumps(ev, ensure_ascii=False)
                    yield f"data: {data}\n\n"
            except Exception as exc:  # 兜底：不因异常中断连接
                err = json.dumps({"type": "error", "data": {"message": str(exc)}}, ensure_ascii=False)
                yield f"data: {err}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-RateLimit-Remaining": str(quota.get("remaining", -1)),
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations")
async def conversations(
    page: int = 1,
    page_size: int = 20,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await qa_service.get_conversations(db, user.id, page, page_size)


@router.get("/conversations/{conversation_id}/messages")
async def conversation_messages(
    conversation_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"items": await qa_service.get_messages(db, user.id, conversation_id)}


@router.post("/feedback")
async def feedback(
    req: FeedbackRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await qa_service.submit_feedback(db, user.id, req.message_id, req.is_positive, req.rating, req.comment)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await qa_service.delete_conversation(db, user.id, conversation_id)
    return {"message": "对话已删除"}


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: int,
    req: RenameRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await qa_service.rename_conversation(db, user.id, conversation_id, req.title)


@router.get("/suggestions")
async def suggestions(user: CurrentUser = Depends(get_current_user)):
    return {"items": qa_service.suggestions()}


@router.get("/quota")
async def qa_quota(
    user: CurrentUser = Depends(get_current_user),
):
    return await quota_service.get_quota(user, "qa")
