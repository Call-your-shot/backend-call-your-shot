from __future__ import annotations

from fastapi import APIRouter, Query

from ..utils.plan_views import get_frontend_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def get_dashboard(email: str = Query(..., min_length=3)) -> dict:
    return get_frontend_dashboard(email)
