"""值班台账接口：台账页与运营看板都从 /api/duty/ledger 这一份数据取数。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.duty import DutyService

router = APIRouter(prefix="/api/duty", tags=["值班台账"])

service = DutyService()


@router.get("/ledger", response_model=dict)
def ledger(
    shift_date: str | None = Query(default=None, description="按值班日期过滤，如 2026-10-02"),
    team: str | None = Query(default=None, description="按值班班组模糊检索"),
) -> dict:
    """值班台账与看板共用的数据源：返回明细与同源统计，冲突时以台账为准。"""
    return service.ledger(shift_date=shift_date, team=team)


@router.get("", response_model=PageResult[dict])
def list_entries(
    shift_date: str | None = Query(default=None),
    team: str | None = Query(default=None),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """分页查看值班台账。"""
    items, total = service.list_entries(shift_date=shift_date, team=team, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条值班台账，缺字段时说明原因。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="值班台账已登记", entry=entry)
