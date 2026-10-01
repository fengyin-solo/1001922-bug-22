"""值班台账：看板与台账共用同一份数据源。

口径约定：
- 看板（/api/overview）的关键指标一律从值班台账（duty 表）取数；
- 台账只维护一份权威数据（store 里的 duty 表），不存在第二份缓存；
- 若台账对某模块的待处理/异常量做了订正，与模块实时汇总冲突时以台账为准，
  被覆盖的差异写进 conflicts 返回，便于看板标注。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "duty"
LEDGER_FIELDS = ["模块", "待处理", "异常量", "记录时间", "值班人", "备注"]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


class DutyService:
    def list_ledger(self) -> list[dict[str, Any]]:
        """台账全量：每模块保留最近一条登记，按登记时间倒序。"""
        latest: dict[str, dict[str, Any]] = {}
        for row in store.rows(MODULE):
            latest[str(row.get("模块") or "")] = row
        return sorted(latest.values(), key=lambda r: str(r.get("记录时间") or ""), reverse=True)

    def add_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        module = str(values.get("模块") or "").strip()
        if not module:
            return None, "模块不能为空"
        try:
            pending = int(values.get("待处理") or 0)
            abnormal = int(values.get("异常量") or 0)
        except (TypeError, ValueError):
            return None, "待处理与异常量必须是整数"
        if pending < 0 or abnormal < 0:
            return None, "待处理与异常量不能为负数"
        entry = {
            "id": max((int(row.get("id", 0)) for row in store.rows(MODULE)), default=0) + 1,
            "模块": module,
            "待处理": pending,
            "异常量": abnormal,
            "记录时间": _now(),
            "值班人": str(values.get("值班人") or "").strip() or "值班管理员",
            "备注": str(values.get("备注") or "").strip(),
        }
        store.rows(MODULE).append(entry)
        return entry, "值班台账已登记，看板已同步取台账口径"

    def overview(self) -> dict[str, Any]:
        """看板取数：先算各模块实时汇总，再用台账逐模块覆盖，冲突记录在 conflicts。"""
        base = store.overview()
        ledger = self.list_ledger()
        overrides = {str(row.get("模块") or ""): row for row in ledger}

        conflicts: list[dict[str, Any]] = []
        modules: list[dict[str, Any]] = []
        for item in base["modules"]:
            name = str(item["name"])
            row = overrides.get(name)
            merged = dict(item)
            if row is not None:
                ledger_pending = int(row["待处理"])
                ledger_abnormal = int(row["异常量"])
                if ledger_pending != int(item["pending"]) or ledger_abnormal != int(item["abnormal"]):
                    conflicts.append({
                        "模块": name,
                        "模块汇总": {"待处理": item["pending"], "异常量": item["abnormal"]},
                        "台账登记": {"待处理": ledger_pending, "异常量": ledger_abnormal},
                    })
                merged["pending"] = ledger_pending
                merged["abnormal"] = ledger_abnormal
                merged["source"] = "duty"
            else:
                merged["source"] = "module"
            modules.append(merged)

        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {
            "cards": cards,
            "modules": modules,
            "source": "duty-ledger",
            "conflicts": conflicts,
            "ledger": ledger,
        }


duty_service = DutyService()
