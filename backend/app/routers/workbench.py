"""值班工作台接口：读取检修计划状态变化流水与越权拦截记录。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import PageResult
from app.services.workbench import WorkbenchService

router = APIRouter(prefix="/api/workbench", tags=["值班工作台"])

service = WorkbenchService()


@router.get("/changes", response_model=PageResult[dict])
def list_changes(
    result: str | None = Query(default=None, description="成功 / 拒绝"),
    area: str | None = Query(default=None, description="按所属片区过滤"),
    keyword: str | None = Query(default=None, description="按计划编号、设备或操作人检索"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """分页返回变更流水，最新一条在最前；只读，不在这一层做任何修改。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_changes(
        result=result, area=area, keyword=keyword, page=page, size=size
    )
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/summary")
def summary() -> dict[str, int]:
    """工作台顶部的计数卡片。"""
    return service.summary()
