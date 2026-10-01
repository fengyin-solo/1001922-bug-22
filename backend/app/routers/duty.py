"""值班台账接口：台账登记与看板取数共用 DutyService 这一份数据。"""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas import ActionResult, EntryPayload
from app.services.duty import duty_service

router = APIRouter(prefix="/api/duty", tags=["值班台账"])


@router.get("/ledger")
def list_ledger() -> dict[str, object]:
    """值班台账清单：看板与本接口读的是同一份数据。"""
    items = duty_service.list_ledger()
    return {"module": "duty", "total": len(items), "items": items}


@router.post("/ledger", response_model=ActionResult)
def add_ledger(payload: EntryPayload) -> ActionResult:
    """登记一条值班台账；登记后看板立即按台账口径取数。"""
    entry, message = duty_service.add_entry(payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
