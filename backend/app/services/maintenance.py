"""检修计划业务规则：状态流转、字段校验、权限闸门与计划-措施票绑定。

绑定口径（org.enrich_plan / org.find_ticket 是唯一来源）：
- 计划里的检修设备必须先有已签发（含执行中）的安全措施票，否则不许推到已完工；
- 同设备挂多条计划，队组统一按措施票监护人所在队组算，不按计划填报人各算一份；
- 措施状态每次实时从措施票表取，计划列表与措施票详情读到的永远是同一份结论。

权限口径：
- 计划编号与排期（登记）只有本片区负责人能提交，计划撤回同样限本片区负责人；
- 跨片区任何写操作直接拒绝（403），只读接口不受影响；
- 状态变化与越权拒绝都落审计流水，事后能查到是谁、在什么时候动的。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.org import enrich_plan
from app.store import store

MODULE = "maintenance"
REQUIRED_FIELDS = ["计划编号", "所属片区", "检修设备", "检修类别", "计划开始", "计划结束"]
STATUS_ORDER = ["待审批", "已批复", "执行中", "已完工"]
ACTION_RULES = {"提交审批": "已批复", "开始执行": "执行中", "确认完工": "已完工"}
# 撤回是逆向流转：已批复的计划由本片区负责人撤回到待审批。
REVERSE_RULES = {"撤回计划": ("已批复", "待审批")}
# 只有这两类动作涉及计划编号与排期的提交/撤回，限本片区负责人。
MANAGER_ACTIONS = {"提交审批", "撤回计划"}

PLAN_NOT_FOUND = "检修计划 {id} 不存在或已归档"
TICKET_NOT_ISSUED = "设备「{device}」没有已签发的安全措施票，措施票未签发前不许把计划推到已完工"


class PermissionError_(Exception):
    """业务权限拒绝：路由层翻译成 403，审计流水仍会记录。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _operator_label(operator: dict[str, str] | None) -> str:
    if not operator:
        return "未登记访客"
    return f"{operator['name']}（{operator['area']}·{operator['role']}）"


class MaintenanceService:
    # ---- 查询 ----------------------------------------------------------------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        area: str | None = None,
        page: int = 1,
        size: int = 20,
        operator: dict[str, str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("计划编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if area:
            rows = [row for row in rows if row.get("所属片区") == area]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [self._view(row, operator) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int, operator: dict[str, str] | None = None) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._view(row, operator) if row else None

    def _view(self, row: dict[str, Any], operator: dict[str, str] | None) -> dict[str, Any]:
        view = enrich_plan(row)
        view["可改动"], view["权限说明"] = self._permission(row, operator)
        return view

    @staticmethod
    def _permission(
        row: dict[str, Any], operator: dict[str, str] | None
    ) -> tuple[bool, str]:
        """权限判定也只留这一份：列表按钮与写接口共用。"""
        if not operator:
            return False, "未识别到值班身份，当前为只读访客"
        if row.get("所属片区") != operator["area"]:
            return False, f"跨片区单据：你在{operator['area']}，该计划属于{row.get('所属片区')}，仅可查看"
        if operator["role"] != "片区负责人":
            return False, "计划编号与排期的提交、撤回仅限本片区负责人；你可执行现场类动作"
        return True, "本片区负责人，可提交、撤回与流转"

    # ---- 登记 ----------------------------------------------------------------
    def create_entry(
        self, values: dict[str, Any], operator: dict[str, str] | None
    ) -> tuple[dict[str, Any] | None, list[str], str]:
        """登记计划编号与排期：只有本片区负责人能提交，片区以登录身份为准防伪造。"""
        if not operator:
            self._audit("登记检修计划", None, "拒绝",
                        "未登记访客无权登记计划编号与排期", values, None)
            raise PermissionError_("未登记到值班身份，计划编号与排期仅限本片区负责人提交")
        if operator["role"] != "片区负责人":
            self._audit("登记检修计划", None, "拒绝",
                        f"{operator['name']} 不是片区负责人，禁止提交计划编号与排期",
                        values, operator)
            raise PermissionError_("只有本片区负责人能提交计划编号与排期")
        values = {**values, "所属片区": operator["area"]}
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["责任人"] = values.get("责任人") or operator["name"]
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["legacy"] = False
        rows.append(entry)
        self._audit("登记检修计划", entry, "成功",
                    f"{operator['name']} 提交计划编号与排期，归属{operator['area']}",
                    values, operator)
        return self._view(entry, operator), [], ""

    # ---- 状态流转 ------------------------------------------------------------
    def run_action(
        self, entry_id: int, action: str, operator: dict[str, str] | None
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, PLAN_NOT_FOUND.format(id=entry_id)
        if action not in ACTION_RULES and action not in REVERSE_RULES:
            return None, f"动作「{action}」不属于检修计划可执行范围"

        # 跨片区 / 非负责人：直接拒绝，并把越权尝试落到审计流水。
        writable, reason = self._permission(entry, operator)
        if action in MANAGER_ACTIONS and not writable:
            self._audit(action, entry, "拒绝", reason, None, operator)
            raise PermissionError_(f"越权操作已拒绝：{reason}")
        if not operator or entry.get("所属片区") != operator["area"]:
            self._audit(action, entry, "拒绝", reason, None, operator)
            raise PermissionError_(f"越权操作已拒绝：{reason}")

        before = str(entry.get("status"))
        if action in REVERSE_RULES:
            expect, target = REVERSE_RULES[action]
            if before != expect:
                return None, f"仅{expect}状态的计划可以撤回，当前为{before}"
        else:
            target = ACTION_RULES[action]
            if target not in STATUS_ORDER:
                return None, f"目标状态「{target}」不在允许的状态序列里"
            if action == "确认完工":
                ticket = self._issued_ticket(entry)
                if ticket is None:
                    message = TICKET_NOT_ISSUED.format(device=entry.get("检修设备"))
                    self._audit(action, entry, "拒绝", message, None, operator)
                    return None, message

        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = False
        self._audit(action, entry, "成功", f"计划状态 {before} → {target}", None, operator)
        return self._view(entry, operator), f"检修计划已{action}（{before} → {target}）"

    # ---- 审计 ----------------------------------------------------------------
    @staticmethod
    def _issued_ticket(entry: dict[str, Any]) -> dict[str, Any] | None:
        from app.org import find_ticket

        return find_ticket(entry.get("检修设备"), only_issued=True)

    def _audit(
        self,
        action: str,
        entry: dict[str, Any] | None,
        result: str,
        detail: str,
        submitted: dict[str, Any] | None,
        operator: dict[str, str] | None,
    ) -> None:
        store.add_audit({
            "时间": _now(),
            "模块": "检修计划",
            "动作": action,
            "结果": result,
            "计划编号": entry.get("计划编号") if entry else (submitted or {}).get("计划编号", "—"),
            "检修设备": entry.get("检修设备") if entry else (submitted or {}).get("检修设备", "—"),
            "所属片区": entry.get("所属片区") if entry else (submitted or {}).get("所属片区", "—"),
            "操作人": _operator_label(operator),
            "详情": detail,
        })
