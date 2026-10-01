"""测风塔接口：维护测风塔，覆盖提交校验、登记数据缺失、停用测风塔、恢复使用等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.metmast import (
    ACTION_DISABLE,
    ACTION_MARK_MISSING,
    ACTION_RECOVER,
    ACTION_SUBMIT,
    CANONICAL_FIELDS,
    STATUS_DISABLED,
    STATUS_MISSING,
    STATUS_NORMAL,
    STATUS_PENDING,
    MetmastService,
)

router = APIRouter(prefix="/api/metmast", tags=["测风塔"])

service = MetmastService()

LIST_FIELDS = list(CANONICAL_FIELDS)
STATUSES = [STATUS_PENDING, STATUS_NORMAL, STATUS_MISSING, STATUS_DISABLED]
ACTIONS = [ACTION_SUBMIT, ACTION_MARK_MISSING, ACTION_DISABLE, ACTION_RECOVER]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按塔架编号检索"),
    status: str | None = Query(default=None, description="待校验、数据正常、数据缺失、已停用"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按塔架编号与状态过滤测风塔列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/stats")
def stats() -> dict[str, Any]:
    """列表上方卡片：在运塔数、缺失塔数、在运塔平均数据完整率。"""
    return service.stats()


@router.get("/deactivations")
def list_deactivations() -> dict[str, Any]:
    """停用清单：按塔架编号去重，同一座停用过的塔只出现一次。"""
    items = service.list_deactivations()
    return {"module": "metmast", "total": len(items), "items": items}


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出测风塔清单：返回当前全量数据（与列表同一口径）。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "metmast", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条测风塔明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"测风塔 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条测风塔，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"{'、'.join(missing)}")
    return ActionResult(ok=True, message="测风塔已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条测风塔执行提交校验、登记数据缺失、停用、恢复；不允许的动作会被拦下并说明原因。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
