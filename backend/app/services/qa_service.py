# -*- coding: utf-8 -*-
"""智法通 V2 —— 法律问答服务（对话/消息/反馈/流式，非流式与流式均落库引用与置信度）。"""
from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enums import ConversationStatus
from app.models.qa import Conversation, Message, QAFeedback
from app.rag.pipeline import rag_pipeline
from app.utils.security import sanitize_html_content

LEGAL_DISCLAIMER = (
    "\n\n---\n*本回答由 AI 依据检索到的现行有效法律法规自动生成，仅供学习与参考，不构成正式法律意见；"
    "重大事项请咨询执业律师。依据《生成式人工智能服务管理暂行办法》，本内容由 AI 生成，请注意甄别。*"
)

DEFAULT_SUGGESTIONS = [
    "试用期最长可以约定多久？",
    "公司违法解除劳动合同要赔多少钱？",
    "民间借贷利率最高是多少？",
    "签合同遇到霸王条款怎么办？",
]


class QAService:
    # ---------------- 对话 ----------------
    async def _get_conv(self, db, user_id: int, conversation_id: Optional[int], title: str) -> Conversation:
        if conversation_id:
            r = await db.execute(
                select(Conversation).where(
                    Conversation.id == conversation_id,
                    Conversation.user_id == user_id,
                    Conversation.status == ConversationStatus.ACTIVE.value,
                )
            )
            conv = r.scalar_one_or_none()
            if conv is None:
                raise HTTPException(status_code=404, detail="对话不存在")
            return conv
        cnt = await db.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.user_id == user_id,
                Conversation.status == ConversationStatus.ACTIVE.value,
            )
        ) or 0
        if cnt >= settings.MAX_CONVERSATIONS_PER_USER:
            raise HTTPException(status_code=429, detail="对话数量已达上限，请先删除旧对话")
        conv = Conversation(user_id=user_id, title=title[:80] or "新对话")
        db.add(conv)
        await db.flush()
        return conv

    async def get_conversations(self, db, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        page = max(page, 1)
        page_size = min(max(page_size, 1), 50)
        conds = [Conversation.user_id == user_id, Conversation.status == ConversationStatus.ACTIVE.value]
        total = await db.scalar(select(func.count(Conversation.id)).where(*conds)) or 0
        r = await db.execute(
            select(Conversation)
            .where(*conds)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        convs = r.scalars().all()
        return {
            "items": [
                {
                    "id": c.id,
                    "title": c.title,
                    "message_count": c.message_count,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
                for c in convs
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_messages(self, db, user_id: int, conversation_id: int) -> list[dict]:
        conv = await self._get_conv(db, user_id, conversation_id, "")
        r = await db.execute(
            select(Message).where(Message.conversation_id == conv.id).order_by(Message.id)
        )
        msgs = r.scalars().all()
        out = []
        for m in msgs:
            out.append(
                {
                    "id": m.id,
                    "role": m.role,
                    "content": sanitize_html_content(m.content),
                    "citations": json.loads(m.citations) if m.citations else [],
                    "confidence": m.confidence,
                    "created_at": m.created_at,
                }
            )
        return out

    async def rename_conversation(self, db, user_id: int, conversation_id: int, title: str) -> dict:
        title = (title or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail="标题不能为空")
        conv = await self._get_conv(db, user_id, conversation_id, title)
        conv.title = title[:200]
        from app.database import naive_utcnow

        conv.updated_at = naive_utcnow()
        await db.commit()
        return {"id": conv.id, "title": conv.title}

    async def delete_conversation(self, db, user_id: int, conversation_id: int) -> None:
        conv = await self._get_conv(db, user_id, conversation_id, "")
        conv.status = ConversationStatus.DELETED.value
        await db.commit()

    # ---------------- 提问 ----------------
    async def ask(self, db, user_id: int, question: str, conversation_id: Optional[int] = None) -> dict:
        question = (question or "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="问题不能为空")
        if len(question) > 2000:
            raise HTTPException(status_code=400, detail="问题过长")
        conv = await self._get_conv(db, user_id, conversation_id, question)
        db.add(Message(conversation_id=conv.id, role="user", content=question))
        history = await self._recent_history(db, conv.id)
        graph_ctx = await self._graph_context(question)
        result = await rag_pipeline.query(question, history, _graph_context=graph_ctx)
        answer = sanitize_html_content(result["answer"])
        full_answer = answer + LEGAL_DISCLAIMER
        citations_json = json.dumps(result.get("citations", []), ensure_ascii=False)
        db.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=full_answer,
                citations=citations_json,
                confidence=result.get("confidence"),
                latency_ms=result.get("latency_ms"),
                token_count=result.get("token_count"),
            )
        )
        conv.message_count = (conv.message_count or 0) + 2
        await db.commit()
        return {
            "conversation_id": conv.id,
            "answer": full_answer,
            "citations": result.get("citations", []),
            "confidence": result.get("confidence"),
            "self_eval": result.get("self_eval"),
            "warning": result.get("warning", ""),
            "rewritten_query": result.get("rewritten_query"),
        }

    async def ask_stream(
        self, db, user_id: int, question: str, conversation_id: Optional[int] = None
    ) -> AsyncGenerator[dict, None]:
        question = (question or "").strip()
        if not question or len(question) > 2000:
            yield {"type": "error", "data": {"message": "问题不合法"}}
            return
        conv = await self._get_conv(db, user_id, conversation_id, question)
        db.add(Message(conversation_id=conv.id, role="user", content=question))
        await db.commit()
        history = await self._recent_history(db, conv.id)
        citations: list = []
        confidence = 0.5
        chunks: list[str] = []
        async for ev in rag_pipeline.query_stream(question, history):
            if ev["type"] == "meta":
                yield ev
            elif ev["type"] == "content":
                chunks.append(ev["data"]["delta"])
                yield ev
            elif ev["type"] == "done":
                answer = ev["data"].get("answer", "".join(chunks))
                citations = ev["data"].get("citations", [])
                confidence = ev["data"].get("confidence", 0.5)
                # 免责声明作为收尾 content 事件
                disclaimer_ev = {
                    "type": "content",
                    "data": {"delta": LEGAL_DISCLAIMER},
                }
                yield disclaimer_ev
                yield ev  # done（含引用/置信度）
        full_answer = "".join(chunks).strip() + LEGAL_DISCLAIMER
        db.add(
            Message(
                conversation_id=conv.id,
                role="assistant",
                content=full_answer,
                citations=json.dumps(citations, ensure_ascii=False),
                confidence=confidence,
            )
        )
        conv.message_count = (conv.message_count or 0) + 2
        await db.commit()

    async def _graph_context(self, question: str) -> list[dict]:
        """GraphRAG：图谱关联候选（Neo4j 不可用/失败时返回空，不阻塞主检索）。"""
        try:
            from app.services.graph_service import graph_service

            rows = await graph_service.graph_query_text(question, 5)
            return [
                {
                    "id": x.get("id") or f"g_{i}",
                    "text": x.get("text", "")[:400],
                    "metadata": {
                        "law_name": x.get("law_name") or x.get("title") or "",
                        "article_no": x.get("article_no") or "",
                        "title": x.get("title") or x.get("law_name") or "",
                    },
                }
                for i, x in enumerate(rows)
            ]
        except Exception:
            return []

    async def _recent_history(self, db, conversation_id: int) -> list[dict]:
        r = await db.execute(
            select(Message).where(Message.conversation_id == conversation_id).order_by(Message.id.desc()).limit(10)
        )
        msgs = list(r.scalars().all())
        msgs.reverse()
        return [{"role": m.role, "content": m.content} for m in msgs if m.role in ("user", "assistant")]

    # ---------------- 反馈 / 建议 ----------------
    async def submit_feedback(
        self, db, user_id: int, message_id: int, is_positive: bool, rating: Optional[int] = None, comment: Optional[str] = None
    ) -> dict:
        r = await db.execute(select(Message).where(Message.id == message_id))
        msg = r.scalar_one_or_none()
        if msg is None:
            raise HTTPException(status_code=404, detail="消息不存在")
        conv = await db.get(Conversation, msg.conversation_id)
        if conv is None or conv.user_id != user_id:
            raise HTTPException(status_code=403, detail="无权操作该消息")
        r2 = await db.execute(select(QAFeedback).where(QAFeedback.message_id == message_id))
        fb = r2.scalar_one_or_none()
        if fb is None:
            fb = QAFeedback(message_id=message_id, user_id=user_id)
            db.add(fb)
        fb.is_positive = is_positive
        fb.rating = rating
        fb.comment = comment
        await db.commit()
        return {"message": "反馈已提交"}

    def suggestions(self) -> list[str]:
        return DEFAULT_SUGGESTIONS


qa_service = QAService()
