"""值班工作台：计划状态变化统一落到这里，供值班人员盯变化、做事后追溯。"""
from __future__ import annotations

from typing import Any

from app.store import store

AUDIT_MODULE = "audit_changes"


class WorkbenchService:
    def list_changes(
        self,
        *,
        result: str | None = None,
        area: str | None = None,
        keyword: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.audit_rows()
        if result:
            rows = [row for row in rows if row.get("结果") == result]
        if area:
            rows = [row for row in rows if row.get("所属片区") == area]
        if keyword:
            rows = [
                row for row in rows
                if keyword in str(row.get("计划编号", ""))
                or keyword in str(row.get("检修设备", ""))
                or keyword in str(row.get("操作人", ""))
            ]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def summary(self) -> dict[str, int]:
        rows = store.audit_rows()
        return {
            "变更总数": len(rows),
            "成功": sum(1 for row in rows if row.get("结果") == "成功"),
            "越权拒绝": sum(1 for row in rows if row.get("结果") == "拒绝"),
        }
