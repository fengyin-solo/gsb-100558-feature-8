"""值班工作台：检修计划状态变化落库，供值班工作台回放与追溯。

内存仓库里单独维护一张 duty_logs 表；真实项目里这张表就是审计/变更流水表。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "duty_logs"

ACTION_LABELS = {
    "提交审批": "提交审批",
    "开始执行": "开始执行",
    "确认完工": "确认完工",
    "撤回计划": "撤回计划",
    "登记计划": "登记计划",
}


def _next_id() -> int:
    return max((int(row.get("id", 0)) for row in store.rows(MODULE)), default=0) + 1


def record_change(
    *,
    plan_id: int | None,
    plan_no: str,
    equipment: str,
    action: str,
    from_status: str | None,
    to_status: str | None,
    operator: str,
    area: str,
    team: str,
    denied: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    """计划状态变化落库一条；越权被拒也留痕，事后能查出是谁动的。"""
    entry = {
        "id": _next_id(),
        "记录时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "计划编号": plan_no,
        "检修设备": equipment,
        "变更动作": ACTION_LABELS.get(action, action),
        "变更前状态": from_status or "—",
        "变更后状态": to_status or "未变更",
        "操作人": operator,
        "操作人片区": area,
        "归属队组": team,
        "结果": "已拒绝" if denied else "已生效",
        "说明": reason,
        "ref_plan_id": plan_id,
    }
    store.rows(MODULE).append(entry)
    return entry


class DutyService:
    def list_logs(
        self,
        *,
        plan_no: str | None = None,
        area: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = list(reversed(store.rows(MODULE)))
        if plan_no:
            rows = [row for row in rows if plan_no in str(row.get("计划编号", ""))]
        if area:
            rows = [row for row in rows if row.get("操作人片区") == area]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def summary(self) -> dict[str, int]:
        rows = store.rows(MODULE)
        return {
            "变更总数": len(rows),
            "已生效": sum(1 for row in rows if row.get("结果") == "已生效"),
            "已拒绝": sum(1 for row in rows if row.get("结果") == "已拒绝"),
            "今日完工": sum(
                1
                for row in rows
                if row.get("变更后状态") == "已完工" and row.get("结果") == "已生效"
            ),
        }


duty_service = DutyService()
