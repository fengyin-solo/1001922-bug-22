"""测风塔业务规则：状态流转、字段校验、停用清单与恢复登记口径都收在这里。

约定：
- 列表与详情的字段一律以 FIELDS 的顺序为准，避免测风层数等字段在列与列之间错位；
- 历史校验记录只追加、不覆盖；恢复登记按塔架保留最近一次结果；
- 停用清单按塔架去重，重复停用不会产生第二条记录；
- 恢复登记成功时，状态与数据完整率在同一步里复位，不允许只改一半。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "metmast"
DEACTIVATIONS = "$metmast_deactivations"
VALIDATIONS = "$metmast_validations"
RECOVERIES = "$metmast_recoveries"

REQUIRED_FIELDS = ["塔架编号", "所在场站", "塔架高度"]
# 列表与详情共用同一份字段顺序，任何地方都不要另写一份列
FIELDS = ["塔架编号", "所在场站", "塔架高度", "测风层数", "风速仪型号", "上次校验日", "数据完整率", "测风状态"]

STATUS_PENDING = "待校验"
STATUS_NORMAL = "数据正常"
STATUS_MISSING = "数据缺失"
STATUS_STOPPED = "已停用"
STATUS_ORDER = [STATUS_PENDING, STATUS_NORMAL, STATUS_MISSING, STATUS_STOPPED]

# 恢复成功后完整率的复位值：恢复即视为重新采集、数据补齐
RECOVERED_COMPLETENESS = 100.0
DEFAULT_OPERATOR = "值班管理员"


def _today() -> str:
    return date.today().isoformat()


def _next_id(rows: list[dict[str, Any]]) -> int:
    return max((int(row.get("id", 0)) for row in rows), default=0) + 1


def _to_number(raw: Any) -> float | None:
    """把表单里的完整率解析成数值；空串、非数字返回 None 由调用方判错。"""
    if raw is None:
        return None
    if isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().rstrip("%")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _snapshot(entry: dict[str, Any]) -> dict[str, Any]:
    """对外返回的明细：按 FIELDS 顺序补齐字段，测风状态与 status 始终同值。"""
    row: dict[str, Any] = {"id": entry["id"]}
    for field in FIELDS:
        row[field] = entry.get(field)
    row["status"] = entry["status"]
    row["pending"] = entry["pending"]
    row["abnormal"] = entry["abnormal"]
    row["测风状态"] = entry["status"]
    return row


class MetmastService:
    # ---------- 查询 ----------

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
        return [_snapshot(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return _snapshot(entry) if entry else None

    def get_history(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        mast_id = int(entry["id"])
        validations = [dict(row) for row in store.rows(VALIDATIONS) if int(row.get("mast_id", 0)) == mast_id]
        recovery = next(
            (dict(row) for row in store.rows(RECOVERIES) if int(row.get("mast_id", 0)) == mast_id),
            None,
        )
        return {
            "塔架编号": entry.get("塔架编号"),
            "校验记录": validations,  # 历史校验，只追加不覆盖
            "最近恢复": recovery,     # 恢复登记，每塔仅保留最近一次
        }

    def list_deactivations(self) -> list[dict[str, Any]]:
        # 停用清单：以 mast_id 去重，同塔多次停用只保留第一次登记
        seen: set[int] = set()
        result: list[dict[str, Any]] = []
        for row in store.rows(DEACTIVATIONS):
            mast_id = int(row.get("mast_id", 0))
            if mast_id in seen:
                continue
            seen.add(mast_id)
            result.append(dict(row))
        return result

    def summary(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        in_service = [row for row in rows if row.get("status") != STATUS_STOPPED]
        missing = sum(1 for row in rows if row.get("status") == STATUS_MISSING)
        completeness = (
            round(sum(float(row.get("数据完整率") or 0) for row in in_service) / len(in_service), 2)
            if in_service
            else 0
        )
        return {
            "在运测风塔": len(in_service),
            "数据缺失塔数": missing,
            "数据完整率": completeness,
        }

    # ---------- 写入 ----------

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": _next_id(rows)}
        for field in FIELDS:
            if field in REQUIRED_FIELDS:
                entry[field] = str(values.get(field)).strip()
            elif field == "数据完整率":
                entry[field] = 100.0
            elif field == "测风状态":
                entry[field] = STATUS_PENDING
            else:
                entry[field] = values.get(field)
        entry["status"] = STATUS_PENDING
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return _snapshot(entry), []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"测风塔 {entry_id} 不存在或已归档"
        values = values or {}
        if action == "提交校验":
            return self._submit_validation(entry, values)
        if action == "登记数据缺失":
            return self._register_missing(entry, values)
        if action == "停用测风塔":
            return self._deactivate(entry, values)
        if action == "恢复使用":
            return self._recover(entry, values)
        return None, f"动作「{action}」不属于测风塔可执行范围"

    # ---------- 动作实现 ----------

    def _submit_validation(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] == STATUS_STOPPED:
            return None, "测风塔已停用，需先恢复使用后再提交校验"
        completeness = _to_number(values.get("数据完整率"))
        if completeness is None:
            completeness = float(entry.get("数据完整率") or 0)
        if not 0 <= completeness <= 100:
            return None, "数据完整率需在 0～100 之间，请核对后重试"
        operator = str(values.get("操作人") or DEFAULT_OPERATOR).strip() or DEFAULT_OPERATOR
        checked_on = str(values.get("上次校验日") or _today()).strip()
        # 历史校验只追加：每次提交都新增一条，旧记录不改动
        store.rows(VALIDATIONS).append({
            "id": _next_id(store.rows(VALIDATIONS)),
            "mast_id": int(entry["id"]),
            "塔架编号": entry.get("塔架编号"),
            "操作人": operator,
            "校验日期": checked_on,
            "校验结果": STATUS_NORMAL,
            "数据完整率": round(completeness, 2),
        })
        entry["status"] = STATUS_NORMAL
        entry["pending"] = False
        entry["abnormal"] = False
        entry["数据完整率"] = round(completeness, 2)
        entry["上次校验日"] = checked_on
        return _snapshot(entry), "校验已提交，历史记录已追加"

    def _register_missing(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        if entry["status"] == STATUS_STOPPED:
            return None, "测风塔已停用，不能再登记数据缺失"
        operator = str(values.get("操作人") or DEFAULT_OPERATOR).strip() or DEFAULT_OPERATOR
        # 登记缺失同样进校验历史，保持「历史只追加」
        store.rows(VALIDATIONS).append({
            "id": _next_id(store.rows(VALIDATIONS)),
            "mast_id": int(entry["id"]),
            "塔架编号": entry.get("塔架编号"),
            "操作人": operator,
            "校验日期": _today(),
            "校验结果": STATUS_MISSING,
            "数据完整率": entry.get("数据完整率"),
        })
        entry["status"] = STATUS_MISSING
        entry["测风状态"] = STATUS_MISSING
        entry["pending"] = True
        entry["abnormal"] = True
        return _snapshot(entry), "已登记数据缺失，可在恢复使用中补录"

    def _deactivate(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        mast_id = int(entry["id"])
        rows = store.rows(DEACTIVATIONS)
        # 幂等停用：清单里已有该塔就不再登记，避免停用记录重复显示
        existing = next((row for row in rows if int(row.get("mast_id", 0)) == mast_id), None)
        if existing is not None:
            return _snapshot(entry), "该测风塔已在停用清单中，未重复登记"
        reason = str(values.get("停用原因") or "").strip()
        rows.append({
            "mast_id": mast_id,
            "塔架编号": entry.get("塔架编号"),
            "操作人": str(values.get("操作人") or DEFAULT_OPERATOR).strip() or DEFAULT_OPERATOR,
            "停用日期": str(values.get("停用日期") or _today()).strip() or _today(),
            "停用原因": reason,
        })
        entry["status"] = STATUS_STOPPED
        entry["测风状态"] = STATUS_STOPPED
        entry["pending"] = False
        entry["abnormal"] = True
        return _snapshot(entry), "测风塔已停用并登记到停用清单"

    def _recover(self, entry: dict[str, Any], values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        mast_id = int(entry["id"])
        if entry["status"] != STATUS_MISSING:
            return None, "只有登记为数据缺失的测风塔才能恢复使用"
        tower_no = str(values.get("塔架编号") or entry.get("塔架编号") or "").strip()
        if not tower_no:
            # 恢复失败：不改动任何数据，前端保留已填内容供重试
            return None, "塔架编号不能为空，请补充后重试"
        completeness = _to_number(values.get("数据完整率"))
        if completeness is None:
            return None, "数据完整率需为 0～100 的数字，请核对后重试"
        if not 0 <= completeness <= 100:
            return None, "数据完整率需在 0～100 之间，请核对后重试"
        operator = str(values.get("操作人") or DEFAULT_OPERATOR).strip() or DEFAULT_OPERATOR
        note = str(values.get("恢复说明") or "").strip()
        # 恢复登记按塔 upsert：连续恢复两次只保留最近一次
        rows = store.rows(RECOVERIES)
        record = next((row for row in rows if int(row.get("mast_id", 0)) == mast_id), None)
        payload = {
            "mast_id": mast_id,
            "塔架编号": tower_no,
            "操作人": operator,
            "恢复日期": _today(),
            "数据完整率": round(completeness, 2),
            "恢复说明": note,
        }
        if record is None:
            payload["id"] = _next_id(rows)
            rows.append(payload)
        else:
            record.update(payload)
        # 状态、塔架编号、完整率在同一提交里复位；完整率不接受低于复位口径的旧值
        entry["塔架编号"] = tower_no
        entry["status"] = STATUS_NORMAL
        entry["测风状态"] = STATUS_NORMAL
        entry["pending"] = False
        entry["abnormal"] = False
        entry["数据完整率"] = RECOVERED_COMPLETENESS
        entry["上次校验日"] = _today()
        return _snapshot(entry), "测风塔已恢复使用，状态与数据完整率已同时复位"
