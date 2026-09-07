# -*- coding: utf-8 -*-
"""智法通 V2 —— 合同服务（上传/解析/多 Agent 审查/报告/优化下载）。"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.workflow import contract_review_workflow
from app.config import settings
from app.database import naive_utcnow
from app.models.contract import Contract, ReviewReport, RiskClause
from app.models.enums import ContractStatus
from app.utils.file_parser import FileParseError, parse_document

_ALLOWED = {e.lower() for e in settings.ALLOWED_FILE_TYPES.split(",") if e}
_MIME_MAP = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "text/plain": "txt",
}
# 演示/工具辅助文案


def _to_list(text: Optional[str]) -> list:
    if not text:
        return []
    try:
        v = json.loads(text)
        return v if isinstance(v, list) else []
    except Exception:
        return []


class ContractService:
    def __init__(self) -> None:
        self.workflow = contract_review_workflow

    # ---------------- 上传 ----------------
    async def upload_contract(self, db: AsyncSession, user_id: int, file) -> Contract:
        filename = os.path.basename((file.filename or "").replace("\\", "/"))
        if not filename or ".." in filename or filename.startswith("."):
            raise HTTPException(status_code=400, detail="文件名不合法")
        ext = os.path.splitext(filename)[1].lower().lstrip(".")
        if ext not in _ALLOWED:
            raise HTTPException(status_code=400, detail=f"仅支持 {', '.join(sorted(_ALLOWED))} 格式")
        if (file.content_type or "") in _MIME_MAP and _MIME_MAP[file.content_type] != ext:
            raise HTTPException(status_code=400, detail="文件类型与扩展名不一致")
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="文件内容为空")
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="合同文件不能超过 10MB")
        cdir = Path(settings.UPLOAD_DIR) / "contracts"
        cdir.mkdir(parents=True, exist_ok=True)
        fname = f"contract_{user_id}_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"
        fpath = cdir / fname
        fpath.write_bytes(data)
        c = Contract(
            user_id=user_id,
            title=os.path.splitext(filename)[0][:200],
            file_name=filename,
            file_path=str(fpath),
            file_size=len(data),
            file_type=ext,
            status=ContractStatus.PARSING.value,
        )
        db.add(c)
        await db.flush()
        try:
            text = parse_document(str(fpath), ext)
        except FileParseError as exc:
            fpath.unlink(missing_ok=True)
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(exc))
        if not (text or "").strip():
            fpath.unlink(missing_ok=True)
            await db.rollback()
            raise HTTPException(status_code=400, detail="未能从文件中解析出合同文本")
        c.content = text
        c.status = ContractStatus.PARSED.value
        await db.commit()
        await db.refresh(c)
        return c

    # ---------------- 审查 ----------------
    async def review_contract(
        self, db: AsyncSession, user_id: int, contract_id: int, contract_type: Optional[str] = None
    ) -> dict:
        c = await self._own_contract(db, user_id, contract_id)
        if c.status == ContractStatus.REVIEWING.value:
            raise HTTPException(status_code=409, detail="合同正在审查中，请勿重复提交")
        if not (c.content or "").strip():
            # 文件仍在时现场重解析兜底
            if c.file_path and os.path.exists(c.file_path):
                try:
                    c.content = parse_document(c.file_path, c.file_type)
                except Exception:
                    pass
            if not (c.content or "").strip():
                raise HTTPException(status_code=400, detail="合同内容为空，无法审查")
        # 防抖：先置 REVIEWING 并提交释放行锁，避免长事务持锁（1205）
        c.status = ContractStatus.REVIEWING.value
        if contract_type:
            c.contract_type = contract_type
        await db.commit()
        t0 = time.time()
        try:
            report = await self.workflow.run(c.content or "", contract_type or c.contract_type or "")
        except Exception as exc:
            # 失败独立事务回滚状态
            c.status = ContractStatus.FAILED.value
            await db.commit()
            raise HTTPException(status_code=500, detail=f"合同审查失败: {exc}")
        # 写报告（单事务）
        new_report = ReviewReport(
            contract_id=c.id,
            overall_score=float(report.get("overall_score", 0)),
            risk_level=report.get("risk_level", "medium"),
            risk_clause_count=int(report.get("risk_clause_count", 0)),
            summary=report.get("summary", ""),
            suggestions=json.dumps(report.get("suggestions", []), ensure_ascii=False),
            completeness=float(report.get("completeness", 0)),
            compliance=float(report.get("compliance", 0)),
            consistency=float(report.get("consistency", 0)),
            review_duration_ms=int((time.time() - t0) * 1000),
            primary_risks=json.dumps(report.get("primary_risks", []), ensure_ascii=False),
            review_check=json.dumps(report.get("review_check", []), ensure_ascii=False),
            adverse_opinions=json.dumps(report.get("adverse_opinions", []), ensure_ascii=False),
            debate_log=json.dumps(report.get("debate_log", []), ensure_ascii=False),
            unresolved_issues=json.dumps(report.get("unresolved_issues", []), ensure_ascii=False),
            adverse_opinion_count=int(report.get("adverse_opinion_count", 0)),
            unresolved_count=int(report.get("unresolved_count", 0)),
        )
        db.add(new_report)
        await db.flush()
        detail = report.get("risk_clauses_detail", [])
        for rc in detail:
            db.add(
                RiskClause(
                    report_id=new_report.id,
                    clause_index=int(rc.get("clause_index", 0)),
                    original_text=(rc.get("original_text") or "")[:2000],
                    risk_type=rc.get("risk_type", ""),
                    risk_level=rc.get("risk_level", "low"),
                    risk_score=float(rc.get("risk_score", 0)),
                    risk_description=rc.get("risk_description", ""),
                    suggestion=rc.get("suggestion", ""),
                    legal_basis=rc.get("legal_basis", ""),
                )
            )
        if detail:
            new_report.risk_clause_count = len(detail)
        c.status = ContractStatus.REVIEWED.value
        await db.commit()
        return self._serialize_report(new_report, c, risk_clauses=detail)

    # ---------------- 报告 ----------------
    def _serialize_report(
        self, rep: ReviewReport, c: Optional[Contract] = None, risk_clauses: Optional[list] = None
    ) -> dict:
        return {
            "id": rep.id,
            "contract_id": rep.contract_id,
            "risk_clauses": risk_clauses or [],
            "overall_score": rep.overall_score,
            "risk_level": rep.risk_level,
            "risk_clause_count": rep.risk_clause_count,
            "summary": rep.summary or "",
            "suggestions": _to_list(rep.suggestions),
            "completeness": rep.completeness,
            "compliance": rep.compliance,
            "consistency": rep.consistency,
            "review_duration_ms": rep.review_duration_ms,
            "primary_risks": _to_list(rep.primary_risks),
            "review_check": _to_list(rep.review_check),
            "adverse_opinions": _to_list(rep.adverse_opinions),
            "adverse_opinion_count": rep.adverse_opinion_count,
            "debate_log": _to_list(rep.debate_log),
            "unresolved_issues": _to_list(rep.unresolved_issues),
            "unresolved_count": rep.unresolved_count,
            "created_at": rep.created_at,
            "contract_title": c.title if c else None,
        }

    async def _risk_rows(self, db: AsyncSession, report_id: int) -> list[dict]:
        r = await db.execute(
            select(RiskClause).where(RiskClause.report_id == report_id).order_by(RiskClause.clause_index)
        )
        return [
            {
                "id": rc.id,
                "clause_index": rc.clause_index,
                "original_text": rc.original_text,
                "risk_type": rc.risk_type,
                "risk_level": rc.risk_level,
                "risk_score": rc.risk_score,
                "risk_description": rc.risk_description,
                "suggestion": rc.suggestion,
                "legal_basis": rc.legal_basis,
            }
            for rc in r.scalars().all()
        ]

    async def get_review_report(self, db: AsyncSession, user_id: int, contract_id: int) -> dict:
        c = await self._own_contract(db, user_id, contract_id)
        rep = await self._latest_report(db, contract_id)
        if rep is None:
            return self._serialize_report(ReviewReport(contract_id=contract_id), c)
        risk_rows = await self._risk_rows(db, rep.id)
        return self._serialize_report(rep, c, risk_clauses=risk_rows)

    async def _latest_report(self, db: AsyncSession, contract_id: int) -> Optional[ReviewReport]:
        r = await db.execute(
            select(ReviewReport)
            .where(ReviewReport.contract_id == contract_id)
            .order_by(ReviewReport.id.desc())
            .limit(1)
        )
        return r.scalar_one_or_none()

    async def get_contract_history(self, db: AsyncSession, user_id: int, status: Optional[str] = None) -> list[dict]:
        conds = [Contract.user_id == user_id]
        if status:
            conds.append(Contract.status == status)
        result = await db.execute(select(Contract).where(*conds).order_by(Contract.updated_at.desc(), Contract.id.desc()))
        contracts = result.scalars().all()
        cids = [c.id for c in contracts]
        latest: dict[int, ReviewReport] = {}
        if cids:
            reps = (
                await db.execute(
                    select(ReviewReport)
                    .where(ReviewReport.contract_id.in_(cids))
                    .order_by(ReviewReport.id)
                )
            ).scalars().all()
            for rep in reps:  # 同 contract 保留最新
                latest[rep.contract_id] = rep
        items = []
        for c in contracts:
            rep = latest.get(c.id)
            items.append(
                {
                    "id": c.id,
                    "title": c.title,
                    "contract_type": c.contract_type,
                    "status": c.status,
                    "file_type": c.file_type,
                    "file_size": c.file_size,
                    "overall_score": rep.overall_score if rep else None,
                    "risk_level": rep.risk_level if rep else None,
                    "risk_clause_count": rep.risk_clause_count if rep else 0,
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                }
            )
        return items

    async def get_contract_detail(self, db: AsyncSession, user_id: int, contract_id: int) -> dict:
        c = await self._own_contract(db, user_id, contract_id)
        rep = await self._latest_report(db, contract_id)
        risk_rows = await self._risk_rows(db, rep.id) if rep else []
        return {
            "id": c.id,
            "title": c.title,
            "contract_type": c.contract_type,
            "status": c.status,
            "content": c.content or "",
            "parties": [],
            "amount": None,
            "report": self._serialize_report(rep, c, risk_clauses=risk_rows) if rep else None,
            "created_at": c.created_at,
        }

    async def delete_contract(self, db: AsyncSession, user_id: int, contract_id: int) -> None:
        c = await self._own_contract(db, user_id, contract_id)
        if c.file_path and os.path.exists(c.file_path):
            try:
                os.remove(c.file_path)
            except OSError:
                pass
        await db.delete(c)
        await db.commit()

    async def update_type(self, db: AsyncSession, user_id: int, contract_id: int, contract_type: str) -> dict:
        c = await self._own_contract(db, user_id, contract_id)
        c.contract_type = contract_type
        await db.commit()
        return {"id": c.id, "contract_type": contract_type}

    # ---------------- 优化并下载 ----------------
    async def optimize_contract(self, db: AsyncSession, user_id: int, contract_id: int) -> dict:
        c = await self._own_contract(db, user_id, contract_id)
        if c.status != ContractStatus.REVIEWED.value:
            raise HTTPException(status_code=400, detail="请先完成合同审查再生成优化稿")
        rep = await self._latest_report(db, contract_id)
        suggestions = _to_list(rep.suggestions) if rep else []
        lines = [
            f"# {c.title}（AI 优化建议稿）",
            "",
            "> 本文件由智法通生成：保留原合同全文，并给出逐条修订建议，请法务确认后另行修订正式版本。",
            "",
            "## 一、修订建议清单",
            "",
        ]
        for i, s in enumerate(suggestions, 1):
            lines.append(f"{i}. {s}")
        lines += ["", "## 二、原合同全文", "", "```text", c.content or "", "```", ""]
        md = "\n".join(lines)
        fname = f"{c.title}_优化后.md"
        return {"filename": fname, "markdown": md}

    # ---------------- 工具 ----------------
    async def _own_contract(self, db: AsyncSession, user_id: int, contract_id: int) -> Contract:
        r = await db.execute(select(Contract).where(Contract.id == contract_id, Contract.user_id == user_id))
        c = r.scalar_one_or_none()
        if c is None:
            raise HTTPException(status_code=404, detail="合同不存在")
        return c


contract_service = ContractService()
