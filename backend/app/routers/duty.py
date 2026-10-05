"""值班工作台接口：回看检修计划状态变更流水，所有变化都已落库。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import PageResult
from app.services.duty import duty_service

router = APIRouter(prefix="/api/duty", tags=["值班工作台"])

COLUMNS = ["记录时间", "计划编号", "检修设备", "变更动作", "变更前状态", "变更后状态", "操作人", "操作人片区", "归属队组", "结果", "说明"]


@router.get("/logs", response_model=PageResult[dict])
def list_logs(
    plan_no: str | None = Query(default=None, description="按计划编号检索"),
    area: str | None = Query(default=None, description="按操作人片区过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """变更流水按时间倒序返回，越权被拒的记录同样可查。"""
    items, total = duty_service.list_logs(plan_no=plan_no, area=area, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary")
def summary() -> dict[str, int]:
    """值班工作台顶部统计。"""
    return duty_service.summary()
