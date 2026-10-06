"""内存数据仓库：给每个业务模块准备一份可筛选、可流转的示例数据。

真实项目里这里会换成数据库访问层；当前实现只依赖标准库，保证克隆下来就能起。
审计流水（audit_changes）与业务表一样落进仓库，服务重启之间由 seed 初始化，
运行期所有计划状态变化都在这里留痕，供值班工作台与事后追溯读取。
"""
from __future__ import annotations

from typing import Any

from app.seed import SEED_ROWS

AUDIT_MODULE = "audit_changes"


class Store:
    def __init__(self) -> None:
        self._tables: dict[str, list[dict[str, Any]]] = {
            name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()
        }
        self._tables.setdefault(AUDIT_MODULE, [])
        self._migrate_legacy_plans()

    def module_names(self) -> list[str]:
        return sorted(name for name in self._tables if name != AUDIT_MODULE)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def add_audit(self, entry: dict[str, Any]) -> dict[str, Any]:
        """审计流水只追加、不修改，保证事后查得到是谁动的。"""
        rows = self.rows(AUDIT_MODULE)
        entry = dict(entry)
        entry["id"] = max((int(row.get("id", 0)) for row in rows), default=0) + 1
        rows.insert(0, entry)
        return entry

    def audit_rows(self) -> list[dict[str, Any]]:
        return list(self.rows(AUDIT_MODULE))

    def _migrate_legacy_plans(self) -> None:
        """存量数据迁移：过往计划标记为 legacy，队组沿用原值，缺的按检修类别回填。

        只在首次加载（没有迁移标记）时执行一次；新计划不走这条路径，队组一律
        按绑定措施票的监护人动态判定。
        """
        from app.org import team_of_category

        for row in self.rows("maintenance"):
            if row.get("legacy_migrated"):
                continue
            row["legacy"] = True
            team = str(row.get("所属队组") or "").strip()
            if team:
                row["team_source"] = "原有归属"
            else:
                row["所属队组"] = team_of_category(row.get("检修类别"))
                row["team_source"] = "检修类别回填"
            row["legacy_migrated"] = True

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
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
