"""检修计划接口：维护检修计划，覆盖提交审批、开始执行、确认完工、撤回等动作。

越权操作（跨片区改动、非片区负责人提交/撤回）统一返回 403 直接拒绝。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.security import Identity, PermissionDenied, current_identity
from app.services.maintenance import MaintenanceService

router = APIRouter(prefix="/api/maintenance", tags=["检修计划"])

service = MaintenanceService()

LIST_FIELDS = ["计划编号", "检修设备", "检修类别", "计划开始", "计划结束", "责任人", "安全措施", "计划状态"]
STATUSES = ["待审批", "已批复", "执行中", "已完工"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按计划编号或检修设备检索"),
    status: str | None = Query(default=None, description="待审批、已批复、执行中、已完工"),
    area: str | None = Query(default=None, description="按所属片区过滤"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按计划编号、状态与片区过滤检修计划列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, area=area, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出检修计划清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "maintenance", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条检修计划明细；不存在时给出可读的错误说明。跨片区也只查看。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检修计划 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload, identity: Identity = Depends(current_identity)) -> ActionResult:
    """登记检修计划：必须绑定已签发的安全措施票，且只有本片区负责人能提交排期。"""
    try:
        entry, message = service.create_entry(payload.values, identity)
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    if message:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message="检修计划已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    identity: Identity = Depends(current_identity),
) -> ActionResult:
    """对单条检修计划执行动作；越权直接 403 拒绝并在值班工作台留痕。"""
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(entry_id, action, identity)
    except PermissionDenied as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
