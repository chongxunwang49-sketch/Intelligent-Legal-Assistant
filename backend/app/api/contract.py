# -*- coding: utf-8 -*-
"""智法通 V2 —— 合同审查路由（上传/审查/报告/历史/优化下载）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.contract_service import contract_service
from app.services.quota_service import quota_service
from app.utils.deps import CurrentUser, get_current_user

router = APIRouter(prefix="/contract", tags=["contract"])


class ReviewRequest(BaseModel):
    contract_id: int
    contract_type: Optional[str] = None


class OptimizeRequest(BaseModel):
    contract_id: int


class TypeUpdate(BaseModel):
    contract_type: str = Field(..., min_length=1, max_length=50)


def _contract_slim(c) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "contract_type": c.contract_type,
        "status": c.status,
        "file_name": c.file_name,
        "file_size": c.file_size,
        "file_type": c.file_type,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


@router.post("/upload", status_code=201)
async def upload_contract(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    c = await contract_service.upload_contract(db, user.id, file)
    return {"message": "上传并解析成功", "contract": _contract_slim(c)}


@router.post("/review")
async def review_contract(
    req: ReviewRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quota = await quota_service.check_and_consume(user, "contract")
    if not quota["allowed"]:
        raise HTTPException(status_code=429, detail="今日合同审查额度已用完")
    report = await contract_service.review_contract(db, user.id, req.contract_id, req.contract_type)
    report["remaining"] = quota.get("remaining", -1)
    return report


@router.post("/optimize")
async def optimize_contract(
    req: OptimizeRequest,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    data = await contract_service.optimize_contract(db, user.id, req.contract_id)
    return data


@router.get("/report/{contract_id}")
async def get_report(
    contract_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await contract_service.get_review_report(db, user.id, contract_id)


@router.get("/history")
async def history(
    status: Optional[str] = None,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return {"items": await contract_service.get_contract_history(db, user.id, status)}


@router.get("/{contract_id}")
async def contract_detail(
    contract_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await contract_service.get_contract_detail(db, user.id, contract_id)


@router.delete("/{contract_id}")
async def delete_contract(
    contract_id: int,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await contract_service.delete_contract(db, user.id, contract_id)
    return {"message": "合同已删除"}


@router.patch("/{contract_id}/type")
async def update_type(
    contract_id: int,
    req: TypeUpdate,
    user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await contract_service.update_type(db, user.id, contract_id, req.contract_type)
