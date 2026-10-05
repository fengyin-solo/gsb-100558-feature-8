"""安全措施业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app import domain
from app.store import store

MODULE = "safety"
REQUIRED_FIELDS = ["措施编号", "措施类型", "涉及设备", "监护人"]
STATUS_ORDER = ["待签发", "已签发", "执行中", "已解除"]
ACTION_RULES = {"签发措施": "已签发", "开始执行": "执行中", "解除措施": "已解除"}
NEGATIVE_ACTIONS = []


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
        rows = [domain.decorate_ticket(dict(row)) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("措施编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if equipment:
            rows = [row for row in rows if equipment in str(row.get("涉及设备", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return domain.decorate_ticket(dict(entry)) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        guardian = str(values.get("监护人") or "").strip()
        if not domain.team_for_guardian(guardian):
            return None, missing + [f"监护人「{guardian}」未登记所在队组"]
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["签发人"] = str(values.get("签发人") or "").strip()
        entry["执行人"] = str(values.get("执行人") or "").strip()
        entry["有效期至"] = str(values.get("有效期至") or "").strip()
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return domain.decorate_ticket(entry), []

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
            return None, "签发人未签字，措施票不能签发"
        entry["status"] = target
        entry["措施状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        if action == "签发措施":
            entry["签发人"] = entry.get("签发人") or "值班负责人"
        return domain.decorate_ticket(entry), f"安全措施票已{action}"
