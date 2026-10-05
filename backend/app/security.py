"""值班操作人身份与片区权限。

身份由请求头带入（X-Operator / X-Area / X-Role），HTTP 头只允许 ASCII，
因此头里传工号与片区/角色编码，服务端按花名册翻译成中文姓名落库；
未带头时给一个默认值班身份，方便裸调接口。
所有越权判定统一抛 PermissionDenied，由路由层转 403，便于审计。
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Header

ROLE_AREA_LEAD = "片区负责人"
ROLE_OPERATOR = "值班员"
ROLE_CODES = {"lead": ROLE_AREA_LEAD, "operator": ROLE_OPERATOR}
AREA_CODES = {"A1": "一片区", "A2": "二片区"}

# 演示用花名册：工号 -> (姓名, 片区, 角色)。真实项目里换成人员主数据。
DIRECTORY: dict[str, tuple[str, str, str]] = {
    "zhangwei": ("张伟", "一片区", ROLE_AREA_LEAD),
    "sunjie": ("孙杰", "一片区", ROLE_OPERATOR),
    "liuyang": ("刘洋", "二片区", ROLE_AREA_LEAD),
    "chenchen": ("陈晨", "二片区", ROLE_OPERATOR),
}

DEFAULT_OPERATOR_CODE = "zhangwei"


class PermissionDenied(Exception):
    """越权操作：直接拒绝（403），不做任何数据改动。"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class Identity:
    operator: str
    area: str
    role: str

    @property
    def is_area_lead(self) -> bool:
        return self.role == ROLE_AREA_LEAD

    def ensure_same_area(self, target_area: str | None) -> None:
        """跨片区点开只能查看、不能改动；目标片区缺失时按越权拒绝，不默认放行。"""
        if not target_area or target_area == "待核实":
            raise PermissionDenied("该计划片区归属未核实，暂不允许操作")
        if self.area != target_area:
            raise PermissionDenied(
                f"跨片区只读：{self.operator}（{self.area}）不能改动{target_area}的检修计划"
            )

    def ensure_area_lead(self, target_area: str | None) -> None:
        """计划编号与排期只有本片区负责人能提交、能撤回。"""
        self.ensure_same_area(target_area)
        if not self.is_area_lead:
            raise PermissionDenied(f"只有{target_area}片区负责人能提交或撤回计划与排期")


def current_identity(
    x_operator: str | None = Header(default=None, alias="X-Operator"),
    x_area: str | None = Header(default=None, alias="X-Area"),
    x_role: str | None = Header(default=None, alias="X-Role"),
) -> Identity:
    """从请求头解析当前值班人；工号在册时以花名册为准，避免前端伪造片区。"""
    code = (x_operator or DEFAULT_OPERATOR_CODE).strip()
    if code in DIRECTORY:
        operator, area, role = DIRECTORY[code]
        return Identity(operator=operator, area=area, role=role)
    # 未登记工号：片区、角色按编码头识别，姓名只用于日志展示
    area = AREA_CODES.get((x_area or "").strip(), "未分配片区")
    role = ROLE_CODES.get((x_role or "").strip(), ROLE_OPERATOR)
    return Identity(operator=code, area=area, role=role)
