"""测风塔业务规则：状态流转、字段口径、校验历史与停用清单都收在这里。

口径约定：
- 列表与详情共用同一份 CANONICAL_FIELDS，字段顺序/取值只有一个出口，避免错位。
- 「提交校验」只追加校验历史，历史记录永不覆盖。
- 「恢复使用」只回写最近一次恢复结果（last_recovery），连续两次恢复保留最近一次。
- 停用清单按塔架编号去重，同一座塔只保留一条停用记录。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "metmast"
DEACTIVATIONS = "metmast_deactivations"
REQUIRED_FIELDS = ["塔架编号", "所在场站", "塔架高度"]
# 列表与详情共用的字段顺序；「测风状态」统一取自 status，而不是行内的占位字段。
CANONICAL_FIELDS = ["塔架编号", "所在场站", "塔架高度", "测风层数", "风速仪型号", "上次校验日", "数据完整率", "测风状态"]
DEFAULT_COMPLETENESS = "100%"
MISSING_COMPLETENESS = "0%"

STATUS_PENDING = "待校验"
STATUS_NORMAL = "数据正常"
STATUS_MISSING = "数据缺失"
STATUS_DISABLED = "已停用"
STATUS_ORDER = [STATUS_PENDING, STATUS_NORMAL, STATUS_MISSING, STATUS_DISABLED]

ACTION_SUBMIT = "提交校验"
ACTION_MARK_MISSING = "登记数据缺失"
ACTION_DISABLE = "停用测风塔"
ACTION_RECOVER = "恢复使用"


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _normalize_completeness(raw: Any) -> str | None:
    """把完整率归一为 0%-100% 的百分数字符串；非法输入返回 None 交由上层报错。"""
    text = str(raw or "").strip().rstrip("%").strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value < 0 or value > 100:
        return None
    if float(value).is_integer():
        return f"{int(value)}%"
    return f"{value:.1f}%"


class MetmastService:
    # ---- 查询口径 ----------------------------------------------------------
    def _project(self, entry: dict[str, Any]) -> dict[str, Any]:
        """列表与详情的统一出口：测风状态取真实 status，其余字段缺失补 —。"""
        view = {field: entry.get(field) for field in CANONICAL_FIELDS}
        view["测风状态"] = entry.get("status")
        view["id"] = entry.get("id")
        return view

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("塔架编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._project(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        view = self._project(entry)
        # 详情额外带出历史与最近一次恢复结果
        view["校验历史"] = list(entry.get("校验历史", []))
        view["最近恢复"] = entry.get("last_recovery")
        return view

    def stats(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        in_service = [row for row in rows if row.get("status") != STATUS_DISABLED]
        missing = sum(1 for row in rows if row.get("status") == STATUS_MISSING)
        rates: list[float] = []
        for row in in_service:
            text = str(row.get("数据完整率") or "").rstrip("%")
            try:
                rates.append(float(text))
            except ValueError:
                continue
        avg = round(sum(rates) / len(rates), 1) if rates else 0.0
        return {
            "在运测风塔": len(in_service),
            "数据缺失塔数": missing,
            "数据完整率": f"{avg:g}%",
        }

    def list_deactivations(self) -> list[dict[str, Any]]:
        """停用清单：按塔架编号去重，同一座塔只出现一次，停用后再恢复不重复登记。"""
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for record in store.rows(DEACTIVATIONS):
            code = str(record.get("塔架编号") or "")
            if code in seen:
                continue
            seen.add(code)
            result.append(dict(record))
        return result

    # ---- 写入 --------------------------------------------------------------
    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        code = str(values.get("塔架编号")).strip()
        if any(str(row.get("塔架编号") or "") == code for row in rows):
            return None, [f"塔架编号 {code} 已存在"]
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in CANONICAL_FIELDS if field != "测风状态"})
        entry["塔架编号"] = code
        entry["数据完整率"] = DEFAULT_COMPLETENESS
        entry["测风层数"] = str(values.get("测风层数") or "").strip() or "1"
        entry["status"] = STATUS_PENDING
        entry["pending"] = True
        entry["abnormal"] = False
        entry["校验历史"] = []
        entry["last_recovery"] = None
        rows.append(entry)
        return self._project(entry), []

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"测风塔 {entry_id} 不存在或已归档"

        if action == ACTION_SUBMIT:
            return self._submit(entry)
        if action == ACTION_MARK_MISSING:
            return self._mark_missing(entry, values)
        if action == ACTION_DISABLE:
            return self._disable(entry)
        if action == ACTION_RECOVER:
            return self._recover(entry, values)
        return None, f"动作「{action}」不属于测风塔可执行范围"

    def _submit(self, entry: dict[str, Any]) -> tuple[dict[str, Any], str]:
        """提交校验：状态与完整率复位为正常，并追加一条不可覆盖的校验历史。"""
        entry["status"] = STATUS_NORMAL
        entry["数据完整率"] = DEFAULT_COMPLETENESS
        entry["上次校验日"] = _today()
        entry["pending"] = False
        entry["abnormal"] = False
        history = entry.setdefault("校验历史", [])
        history.append({"校验日": _today(), "结论": "数据正常", "完整率": DEFAULT_COMPLETENESS})
        return self._project(entry), "校验通过，状态与数据完整率已复位"

    def _mark_missing(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any], str]:
        rate = _normalize_completeness(values.get("数据完整率"))
        if rate is None:
            rate = MISSING_COMPLETENESS
        entry["status"] = STATUS_MISSING
        entry["数据完整率"] = rate
        entry["pending"] = True
        entry["abnormal"] = True
        history = entry.setdefault("校验历史", [])
        history.append({"校验日": _today(), "结论": "数据缺失", "完整率": rate})
        return self._project(entry), "已登记数据缺失"

    def _disable(self, entry: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """停用：同一座塔只登记一条停用记录，重复停用直接拦下。"""
        code = str(entry.get("塔架编号") or "")
        existing = {str(r.get("塔架编号") or "") for r in store.rows(DEACTIVATIONS)}
        if entry.get("status") == STATUS_DISABLED or code in existing:
            return None, f"{code} 已在停用清单中，不能重复停用"
        entry["status"] = STATUS_DISABLED
        entry["pending"] = False
        entry["abnormal"] = True
        store.rows(DEACTIVATIONS).append({
            "塔架编号": code,
            "所在场站": entry.get("所在场站"),
            "停用日期": _today(),
        })
        return self._project(entry), "测风塔已停用，停用清单已登记"

    def _recover(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        """恢复使用：状态与完整率同时复位。

        - 仅「数据缺失」的塔允许恢复；
        - 完整率非法时整体失败、不写任何数据，前端保留已填内容可重试；
        - 恢复结果只存最近一次（last_recovery 覆盖），校验历史不受影响。
        """
        if entry.get("status") != STATUS_MISSING:
            return None, f"当前状态为「{entry.get('status')}」，只有数据缺失的测风塔可以恢复使用"

        rate = _normalize_completeness(values.get("数据完整率"))
        if values.get("数据完整率") not in (None, "") and rate is None:
            return None, "数据完整率需为 0-100 之间的数值，恢复未生效，请修改后重试"

        new_code = str(values.get("塔架编号") or "").strip()
        if new_code:
            duplicate = next(
                (
                    row for row in store.rows(MODULE)
                    if row is not entry and str(row.get("塔架编号") or "") == new_code
                ),
                None,
            )
            if duplicate is not None:
                return None, f"塔架编号 {new_code} 已被其他测风塔占用，恢复未生效"
            entry["塔架编号"] = new_code

        entry["数据完整率"] = rate or DEFAULT_COMPLETENESS
        entry["status"] = STATUS_NORMAL
        entry["pending"] = False
        entry["abnormal"] = False
        # 最近一次恢复结果：连续恢复时覆盖旧结果；校验历史不动
        entry["last_recovery"] = {
            "恢复日期": _today(),
            "完整率": entry["数据完整率"],
            "登记人": str(values.get("登记人") or "").strip() or "值班管理员",
        }
        return self._project(entry), "已恢复使用，状态与数据完整率同时复位"
