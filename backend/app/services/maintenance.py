"""检修计划业务规则。

收口的规则：
- 计划里的检修设备必须先有「已签发」的安全措施票，登记时即绑定，措施编号串票或设备不符直接拒绝；
- 票没签发（或被退回待签发）不许把计划推到已完工；
- 同一设备挂多条计划时，队组按所绑措施票监护人所在队组算（口径只留 app.domain 一份）；
- 计划编号与排期只有本片区负责人能提交/撤回，同片区值班员可执行/完工，跨片区只读；
- 每次状态变化（含越权被拒）都写值班工作台流水，事后可查是谁动的。
"""
from __future__ import annotations

from typing import Any

from app import domain
from app.security import Identity, PermissionDenied
from app.services import duty
from app.store import store

MODULE = "maintenance"
REQUIRED_FIELDS = ["计划编号", "检修设备", "检修类别", "计划开始", "计划结束"]
STATUS_ORDER = ["待审批", "已批复", "执行中", "已完工"]

# 动作 -> 目标状态
ACTION_RULES = {"提交审批": "已批复", "开始执行": "执行中", "确认完工": "已完工", "撤回计划": "待审批"}
# 只有本片区负责人能做的动作：计划编号提交、排期撤回
LEAD_ONLY_ACTIONS = {"提交审批", "撤回计划"}
# 各动作要求的前置状态，防止跳状态
PREV_STATUS = {"提交审批": "待审批", "开始执行": "已批复", "确认完工": "执行中", "撤回计划": "已批复"}
FINAL_STATUS = "已完工"


class MaintenanceService:
    # ---------- 查询 ----------
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        area: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = [self._decorate(dict(row)) for row in store.rows(MODULE)]
        if keyword:
            rows = [
                row
                for row in rows
                if keyword in str(row.get("计划编号", "")) or keyword in str(row.get("检修设备", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if area:
            rows = [row for row in rows if row.get("所属片区") == area]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._decorate(dict(entry)) if entry is not None else None

    # ---------- 登记（片区负责人 + 已签发措施票） ----------
    def create_entry(
        self, values: dict[str, Any], identity: Identity
    ) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"

        equipment = str(values.get("检修设备") or "").strip()
        ticket_no = str(values.get("安全措施") or "").strip()

        ticket = domain.resolve_ticket(ticket_no, equipment)
        if ticket is None:
            return None, f"设备「{equipment}」没有可绑定的安全措施票，请先登记并签发措施票"
        if str(ticket.get("涉及设备") or "").strip() != equipment:
            return None, (
                f"措施票 {ticket.get('措施编号')} 涉及设备为「{ticket.get('涉及设备')}」"
                f"，与检修设备「{equipment}」不一致，不能绑定"
            )
        if not domain.is_ticket_issued(ticket):
            return None, (
                f"措施票 {ticket.get('措施编号')} 当前为「{ticket.get('status')}」，"
                "尚未签发，不能据此排检修计划"
            )

        team = domain.team_for_guardian(ticket.get("监护人"))
        if not team:
            return None, f"措施票监护人「{ticket.get('监护人')}」未登记所在队组，无法确定计划归属"
        plan_area = domain.area_for_team(team)

        # 计划编号与排期只有本片区负责人能提交：登记即落排期，走负责人闸口
        try:
            identity.ensure_area_lead(plan_area)
        except PermissionDenied as exc:
            self._log_denied(values, "登记计划", identity, exc.message)
            raise

        rows = store.rows(MODULE)
        plan_no = str(values.get("计划编号") or "").strip()
        if any(str(row.get("计划编号") or "") == plan_no for row in rows):
            return None, f"计划编号 {plan_no} 已存在，编号不能重复"

        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field) or "").strip()
        entry["责任人"] = str(values.get("责任人") or identity.operator).strip()
        entry["安全措施"] = str(ticket.get("措施编号") or "")
        entry["status"] = STATUS_ORDER[0]
        entry["计划状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["归属队组"] = team
        entry["所属片区"] = plan_area
        rows.append(entry)

        duty.record_change(
            plan_id=entry["id"],
            plan_no=entry["计划编号"],
            equipment=entry["检修设备"],
            action="登记计划",
            from_status=None,
            to_status=entry["status"],
            operator=identity.operator,
            area=identity.area,
            team=team,
        )
        return self._decorate(dict(entry)), ""

    # ---------- 状态流转 ----------
    def run_action(self, entry_id: int, action: str, identity: Identity) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"检修计划 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于检修计划可执行范围"

        # 归属只留一份口径：按所绑措施票监护人实时重算，
        # 存量回填值与票据监护人不一致时以票据为准（同一设备挂多票均能区分）。
        ticket = domain.resolve_ticket(entry.get("安全措施"), entry.get("检修设备"))
        if ticket is not None:
            team = domain.team_for_guardian(ticket.get("监护人"))
            if team:
                entry["归属队组"] = team
                entry["所属片区"] = domain.area_for_team(team)
        target_area = entry.get("所属片区") or domain.area_for_team(entry.get("归属队组"))
        try:
            if action in LEAD_ONLY_ACTIONS:
                identity.ensure_area_lead(target_area)
            else:
                identity.ensure_same_area(target_area)
        except PermissionDenied as exc:
            # 越权操作直接拒绝，且必须留痕，事后查得出是谁点的
            duty.record_change(
                plan_id=entry_id,
                plan_no=str(entry.get("计划编号") or ""),
                equipment=str(entry.get("检修设备") or ""),
                action=action,
                from_status=str(entry.get("status") or ""),
                to_status=None,
                operator=identity.operator,
                area=identity.area,
                team=str(entry.get("归属队组") or ""),
                denied=True,
                reason=exc.message,
            )
            raise

        previous = str(entry.get("status") or "")
        required_previous = PREV_STATUS[action]
        if previous != required_previous:
            return None, f"计划当前为「{previous}」，不能{action}（需先处于「{required_previous}」）"

        target = ACTION_RULES[action]

        # 完工闸口：票没签发不许完工；票据状态实时取，列表与详情天然同步
        if target == FINAL_STATUS:
            ticket = domain.resolve_ticket(entry.get("安全措施"), entry.get("检修设备"))
            if ticket is None:
                return None, "绑定的安全措施票已缺失，不能确认完工，请先补齐措施票"
            if not domain.is_ticket_issued(ticket):
                return None, (
                    f"安全措施票 {ticket.get('措施编号')} 当前为「{ticket.get('status')}」，"
                    "票未签发，计划不允许推到已完工"
                )

        entry["status"] = target
        entry["计划状态"] = target
        entry["pending"] = target != FINAL_STATUS
        entry["abnormal"] = False
        duty.record_change(
            plan_id=entry_id,
            plan_no=str(entry.get("计划编号") or ""),
            equipment=str(entry.get("检修设备") or ""),
            action=action,
            from_status=previous,
            to_status=target,
            operator=identity.operator,
            area=identity.area,
            team=str(entry.get("归属队组") or ""),
        )
        return self._decorate(dict(entry)), f"检修计划已{action}"

    # ---------- 内部 ----------
    def _log_denied(self, values: dict[str, Any], action: str, identity: Identity, reason: str) -> None:
        duty.record_change(
            plan_id=None,
            plan_no=str(values.get("计划编号") or ""),
            equipment=str(values.get("检修设备") or ""),
            action=action,
            from_status=None,
            to_status=None,
            operator=identity.operator,
            area=identity.area,
            team="",
            denied=True,
            reason=reason,
        )

    def _decorate(self, row: dict[str, Any]) -> dict[str, Any]:
        """补齐绑定措施票的实时状态：计划列表与措施票详情读的是同一份票据数据。"""
        ticket = domain.resolve_ticket(row.get("安全措施"), row.get("检修设备"))
        if ticket is not None:
            team = domain.team_for_guardian(ticket.get("监护人"))
            row["安全措施"] = ticket.get("措施编号")
            row["措施状态"] = ticket.get("status")
            row["措施监护人"] = ticket.get("监护人")
            if team:
                row["归属队组"] = team
                row["所属片区"] = domain.area_for_team(team)
            row["措施已签发"] = domain.is_ticket_issued(ticket)
        else:
            row["措施状态"] = "未绑定"
            row["措施监护人"] = ""
            row["措施已签发"] = False
        row.setdefault("归属队组", "待核实")
        row.setdefault("所属片区", "待核实")
        row["计划状态"] = row.get("status")
        return row
