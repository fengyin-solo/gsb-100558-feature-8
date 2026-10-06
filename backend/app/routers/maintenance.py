"""检修计划接口：维护检修计划，覆盖提交审批、开始执行、确认完工、撤回等动作。

所有写接口都强制带当前值班身份：本片区负责人才可提交编号排期与撤回；
跨片区写操作由服务层抛 PermissionError_，这里统一翻译成 403 直接拒绝。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.deps import current_operator
from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.maintenance import MaintenanceService, PermissionError_

router = APIRouter(prefix="/api/maintenance", tags=["检修计划"])

service = MaintenanceService()

LIST_FIELDS = ["计划编号", "所属片区", "检修设备", "检修类别", "计划开始", "计划结束", "责任人",
               "安全措施票", "措施状态", "所属队组", "队组来源", "计划状态"]
STATUSES = ["待审批", "已批复", "执行中", "已完工"]

@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按计划编号检索"),
    status: str | None = Query(default=None, description="待审批、已批复、执行中、已完工"),
    area: str | None = Query(default=None, description="按所属片区过滤"),
    page: int = 1,
    size: int = 20,
    operator: dict[str, str] | None = Depends(current_operator),
) -> PageResult[dict]:
    """按计划编号、状态与片区过滤检修计划；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(
        keyword=keyword, status=status, area=area, page=page, size=size, operator=operator
    )
    return PageResult(items=items, total=total, page=page, size=size)

@router.get("/export")
def export_entries(operator: dict[str, str] | None = Depends(current_operator)) -> dict[str, Any]:
    """导出检修计划清单：返回当前过滤条件下的全量数据（含绑定票与队组判定）。"""
    items, total = service.list_entries(page=1, size=10000, operator=operator)
    return {"module": "maintenance", "total": total, "items": items}

@router.get("/{entry_id}", response_model=dict)
def get_entry(
    entry_id: int, operator: dict[str, str] | None = Depends(current_operator)
) -> dict:
    """读取单条检修计划明细；不存在时给出可读的错误说明。跨片区同样可查看。"""
    entry = service.get_entry(entry_id, operator)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"检修计划 {entry_id} 不存在或已归档")
    return entry

@router.post("", response_model=ActionResult, status_code=201)
def create_entry(
    payload: EntryPayload, operator: dict[str, str] | None = Depends(current_operator)
) -> ActionResult:
    """登记计划编号与排期：仅限本片区负责人，片区以后台身份为准，不许前端指定。"""
    try:
        entry, missing, _ = service.create_entry(payload.values, operator)
    except PermissionError_ as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="检修计划已登记，编号与排期已提交", entry=entry)

@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(
    entry_id: int,
    payload: EntryPayload,
    operator: dict[str, str] | None = Depends(current_operator),
) -> ActionResult:
    """状态流转与撤回。

    - 提交审批、撤回计划：仅本片区负责人；
    - 开始执行、确认完工：限本片区值班人员；
    - 确认完工前强制校验设备已绑定已签发措施票；
    - 跨片区一律 403，拒绝动作连同操作人一起落审计流水。
    """
    action = str(payload.values.get("action") or "").strip()
    try:
        entry, message = service.run_action(entry_id, action, operator)
    except PermissionError_ as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)

