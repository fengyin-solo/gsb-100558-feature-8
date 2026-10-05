"""检修计划与安全措施票联动的唯一判定口径。

队组归属、片区归属、措施票是否算「已签发」全部在这里判定，
检修计划列表、安全措施票详情、值班工作台都只能调用这里的函数，避免多处各算各的。
"""
from __future__ import annotations

from typing import Any

# 措施票一旦完成签发，后续执行中、已解除都视为「已签发且持续有效」，可支撑完工
TICKET_ISSUED_STATUSES = ("已签发", "执行中", "已解除")

# 监护人 -> 所在队组：同一设备挂多条计划时，计划归属按所绑措施票的监护人算，只认这一份表
GUARDIAN_TEAMS: dict[str, str] = {
    "王强": "电气一次班",
    "李娟": "电气二次班",
    "赵敏": "应急抢修班",
    "周磊": "生产技术组",
}

# 队组 -> 所属片区：跨片区只读判定用
TEAM_AREAS: dict[str, str] = {
    "电气一次班": "一片区",
    "电气二次班": "一片区",
    "应急抢修班": "二片区",
    "生产技术组": "二片区",
}

# 检修类别 -> 队组：只给存量计划回填用；新计划一律以措施票监护人所在队组为准
CATEGORY_TEAMS: dict[str, str] = {
    "计划检修": "电气一次班",
    "日常维护": "电气二次班",
    "故障抢修": "应急抢修班",
    "试验校验": "生产技术组",
}


def team_for_guardian(guardian: str | None) -> str:
    """按措施票监护人取所在队组；监护人不在册时返回空串由调用方提示。"""
    return GUARDIAN_TEAMS.get(str(guardian or "").strip(), "")


def area_for_team(team: str | None) -> str:
    """按队组取所属片区。"""
    return TEAM_AREAS.get(str(team or "").strip(), "")


def legacy_team_for_category(category: str | None) -> str:
    """存量计划按检修类别回填队组；类别无法识别时归到待核实，不静默乱派。"""
    return CATEGORY_TEAMS.get(str(category or "").strip(), "待核实")


def is_ticket_issued(ticket: dict[str, Any] | None) -> bool:
    """措施票是否处于已签发口径（已签发/执行中/已解除）。"""
    return bool(ticket) and str(ticket.get("status") or "") in TICKET_ISSUED_STATUSES


def resolve_ticket(ticket_no: str | None, equipment: str | None = None) -> dict[str, Any] | None:
    """按措施编号定位安全措施票；编号缺省时退回按涉及设备匹配。

    延迟导入 store，避免 domain <- store <- seed 链路上的循环依赖。
    同一设备有多条票时，编号精确匹配优先，杜绝串票。
    """
    from app.store import store

    ticket_no = str(ticket_no or "").strip()
    equipment = str(equipment or "").strip()
    tickets = store.rows("safety")
    if ticket_no:
        for ticket in tickets:
            if str(ticket.get("措施编号") or "").strip() == ticket_no:
                return ticket
        return None
    if equipment:
        for ticket in tickets:
            if str(ticket.get("涉及设备") or "").strip() == equipment:
                return ticket
    return None


def decorate_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    """给措施票补上唯一口径算出的队组/片区/签发态，列表与详情都走这里。"""
    team = team_for_guardian(ticket.get("监护人"))
    ticket["措施状态"] = ticket.get("status")
    ticket["归属队组"] = team or "待核实"
    ticket["所属片区"] = area_for_team(team)
    ticket["已签发"] = is_ticket_issued(ticket)
    return ticket
