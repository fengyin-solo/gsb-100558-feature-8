"""安全措施业务规则：状态流转、字段校验与筛选口径都收在这里。

措施状态对外只有一份：所有展示字段「措施状态」都直接取自流转 status，
检修计划列表通过 org.find_ticket 读的也是同一个字段，两处天然同步，
不会出现票上显示已签发、计划里还读到待签发的情况。
"""
from __future__ import annotations

from typing import Any

from app.org import team_of_guardian
from app.store import store

MODULE = "safety"
REQUIRED_FIELDS = ["措施编号", "措施类型", "涉及设备", "监护人"]
STATUS_ORDER = ["待签发", "已签发", "执行中", "已解除"]
ACTION_RULES = {"签发措施": "已签发", "开始执行": "执行中", "解除措施": "已解除"}
NEGATIVE_ACTIONS = []


def _view(row: dict[str, Any]) -> dict[str, Any]:
    """票详情/列表的统一出口：措施状态只认 status，队组只按监护人查。"""
    view = dict(row)
    view["措施状态"] = row.get("status", STATUS_ORDER[0])
    view["监护队组"] = team_of_guardian(row.get("监护人")) or "未登记队组"
    return view


class SafetyService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        equipment: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("措施编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if equipment:
            rows = [row for row in rows if equipment in str(row.get("涉及设备", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_view(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return _view(row) if row else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["签发人"] = values.get("签发人") or ""
        entry["执行人"] = values.get("执行人") or ""
        entry["有效期至"] = values.get("有效期至") or ""
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _view(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"安全措施票 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于安全措施可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        if action == "签发措施" and not str(entry.get("签发人") or "").strip():
            return None, "安全措施票缺少签发人，不能签发"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return _view(entry), f"安全措施票已{action}"
