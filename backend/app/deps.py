"""请求侧的身份解析。

当前是无登录的演示后台，身份随请求头 X-Operator 带入；换成真实 SSO/网关时
只需要替换 current_operator 的实现，业务层拿到的仍是 org.DIRECTORY 里的人员口径。
"""
from __future__ import annotations

from fastapi import Header

from app.org import find_operator


def current_operator(
    x_operator: str | None = Header(default=None, alias="X-Operator"),
) -> dict[str, str] | None:
    """解析当前操作人；未带或查无此人时返回 None，业务侧按只读访客处理。"""
    return find_operator(x_operator)
