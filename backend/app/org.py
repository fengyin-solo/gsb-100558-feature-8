"""组织与判定口径的唯一来源。

检修计划与安全措施票怎么绑定、监护人属于哪个队组、存量计划归哪个队组，
全部在这一个模块里判定，计划列表、计划详情、措施票详情都只准读这里的结论，
不允许各自存一份、各自算一份。
"""
from __future__ import annotations

from typing import Any

SAFETY_MODULE = "safety"

# 措施票签发之后才算数：「已签发」与签发后进入「执行中」都满足完工前置条件。
ISSUED_STATUSES = ("已签发", "执行中")

# 片区负责人：只有本能在本片区提交计划编号与排期、撤回计划。
# code 是随请求头传输的 ASCII 标识，中文姓名不直接进 HTTP 头。
DIRECTORY: list[dict[str, str]] = [
    {"code": "zhao", "name": "赵建国", "role": "片区负责人", "area": "东片区"},
    {"code": "sun", "name": "孙立业", "role": "片区负责人", "area": "西片区"},
    {"code": "zhou", "name": "周明", "role": "值班员", "area": "东片区"},
    {"code": "wu", "name": "吴琳", "role": "值班员", "area": "西片区"},
]


def find_operator(ident: str | None) -> dict[str, str] | None:
    """按工号或姓名查操作人；查不到说明当前请求是未登记身份，按访客处理。"""
    ident = str(ident or "").strip()
    if not ident:
        return None
    for person in DIRECTORY:
        if person["code"] == ident or person["name"] == ident:
            return dict(person)
    return None


# 监护人所在队组：措施票上不重复存队组，一律按监护人查这张表。
GUARDIAN_TEAM: dict[str, str] = {
    "王强": "电气一次班",
    "李刚": "电气一次班",
    "陈敏": "电气二次班",
    "郑伟": "高压试验班",
}

# 存量计划没有措施票可挂时，按检修类别回填队组的口径。
CATEGORY_TEAM: dict[str, str] = {
    "变压器检修": "电气一次班",
    "汇流箱检修": "电气二次班",
    "逆变器检修": "电气二次班",
    "组件检修": "组件检修班",
    "预防性试验": "高压试验班",
}

# 同一设备多张票时的选票次序：执行中优先于已签发，其次才轮到未走完流程的票；
# 次序相同取最近一张（id 更大）。判定口径只有这一份。
_TICKET_RANK = {"执行中": 0, "已签发": 1, "待签发": 2, "已解除": 3}


def team_of_guardian(guardian: Any) -> str:
    """措施票监护人 → 队组的唯一查法。"""
    return GUARDIAN_TEAM.get(str(guardian or "").strip(), "")


def team_of_category(category: Any) -> str:
    """检修类别 → 默认队组，供存量计划回填。"""
    return CATEGORY_TEAM.get(str(category or "").strip(), "待划分队组")


def find_ticket(equipment: Any, *, only_issued: bool = False) -> dict[str, Any] | None:
    """按检修设备找绑定的措施票。

    only_issued=True 时只认已签发（含执行中）的票，这是完工闸门的判定；
    不传时返回排序最靠前的票，用于列表展示真实的票号与措施状态。
    """
    from app.store import store

    equipment = str(equipment or "").strip()
    candidates = [
        row for row in store.rows(SAFETY_MODULE)
        if str(row.get("涉及设备") or "").strip() == equipment
    ]
    if only_issued:
        candidates = [row for row in candidates if row.get("status") in ISSUED_STATUSES]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            -_TICKET_RANK.get(str(row.get("status")), 9),
            int(row.get("id", 0)),
        ),
    )


def enrich_plan(row: dict[str, Any]) -> dict[str, Any]:
    """给检修计划补上绑定票与队组结论。

    派生字段每次实时从措施票表取，计划列表与措施票详情读到的措施状态因此天然同步；
    存量计划沿用原有队组归属，缺失的按检修类别回填。
    """
    view = dict(row)
    if row.get("legacy"):
        view["所属队组"] = str(row.get("所属队组") or "").strip() or team_of_category(row.get("检修类别"))
        view["队组来源"] = row.get("team_source") or "检修类别回填"
        ticket = find_ticket(row.get("检修设备"))
    else:
        ticket = find_ticket(row.get("检修设备"))
        team = team_of_guardian(ticket.get("监护人")) if ticket else ""
        view["所属队组"] = team or "待划分队组"
        view["队组来源"] = "措施票监护人" if ticket else "未绑定措施票"
    if ticket:
        view["安全措施票"] = ticket.get("措施编号", "—")
        view["措施状态"] = ticket.get("status", "—")
    else:
        view["安全措施票"] = "未配置"
        view["措施状态"] = "未配置"
    view["可完工"] = find_ticket(row.get("检修设备"), only_issued=True) is not None
    return view
