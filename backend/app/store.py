"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
启动时顺带完成两件迁移：
1. 存量检修计划沿用原有归属，按检修类别回填队组与片区；
2. 安全措施票按唯一口径（监护人所在队组）补齐队组/片区/签发态。
"""
from __future__ import annotations

from typing import Any

from app import domain
from app.seed import SEED_ROWS


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }
        # 值班工作台变更流水：启动即建表，所有计划状态变化都落这里
        self._tables.setdefault("duty_logs", [])
        self._backfill_maintenance()
        self._decorate_safety()

    def _backfill_maintenance(self) -> None:
        """过往计划沿用原有队组归属：按检修类别回填，只在缺归属时补，不覆盖新数据。"""
        for row in self.rows("maintenance"):
            if row.get("归属队组"):
                continue
            team = domain.legacy_team_for_category(row.get("检修类别"))
            row["归属队组"] = team
            row["所属片区"] = domain.area_for_team(team)

    def _decorate_safety(self) -> None:
        for ticket in self.rows("safety"):
            domain.decorate_ticket(ticket)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            if name == "duty_logs":
                continue
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
