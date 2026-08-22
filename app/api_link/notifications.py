from __future__ import annotations

from fastapi import APIRouter, Query

from ..utils.plan_views import list_frontend_notifications

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def get_notifications(email: str = Query(..., min_length=3)) -> dict:
    return list_frontend_notifications(email)
