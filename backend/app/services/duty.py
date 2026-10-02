"""值班台账业务规则。

台账是唯一事实来源：看板与台账页都从同一个 snapshot() 取数，
不允许看板再维护一份独立统计；两边对不上时以台账这一份为准。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "duty"
REQUIRED_FIELDS = ["值班日期", "值班班组", "值班人员"]
FIELDS = ["值班日期", "值班班组", "值班人员", "接班时间", "交班时间", "在岗人数", "当班事项", "值班状态"]


class DutyService:
    def list_entries(
        self,
        *,
        shift_date: str | None = None,
        team: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if shift_date:
            rows = [row for row in rows if str(row.get("值班日期", "")) == shift_date]
        if team:
            rows = [row for row in rows if team in str(row.get("值班班组", ""))]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._snapshot(row) for row in rows[start:start + size]], total

    def _snapshot(self, entry: dict[str, Any]) -> dict[str, Any]:
        row: dict[str, Any] = {"id": entry["id"]}
        for field in FIELDS:
            row[field] = entry.get(field)
        row["值班状态"] = entry.get("status")
        return row

    def _stats(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """看板卡片直接从台账行计算，任何地方都不另存一份统计。"""
        on_duty = [row for row in rows if row.get("status") == "在岗"]
        headcount = sum(int(row.get("在岗人数") or 0) for row in on_duty)
        today = date.today().isoformat()
        return {
            "今日值班记录": sum(1 for row in rows if str(row.get("值班日期")) == today),
            "在岗班组": len({row.get("值班班组") for row in on_duty}),
            "在岗人数": headcount,
        }

    def ledger(
        self,
        *,
        shift_date: str | None = None,
        team: str | None = None,
    ) -> dict[str, Any]:
        """台账与看板共用的唯一出口：明细行 + 同源统计。"""
        items, total = self.list_entries(shift_date=shift_date, team=team, page=1, size=10000)
        return {
            "items": items,
            "total": total,
            # 统计始终基于全部台账行，保证看板口径与台账一致
            "stats": self._stats(store.rows(MODULE)),
            "source": "duty_ledger",
        }

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in FIELDS:
            if field == "值班状态":
                entry[field] = "在岗"
            else:
                entry[field] = values.get(field)
        try:
            entry["在岗人数"] = int(values.get("在岗人数") or 0)
        except (TypeError, ValueError):
            return None, ["在岗人数"]
        entry["status"] = str(values.get("值班状态") or "在岗").strip()
        entry["pending"] = entry["status"] != "休息"
        entry["abnormal"] = False
        rows.append(entry)
        return self._snapshot(entry), []
