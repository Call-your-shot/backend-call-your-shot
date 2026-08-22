from typing import Optional

from fastapi import APIRouter, Query

from ..schemas.frontend import PlanLeaveRequestInput
from ..utils.plan_views import create_plan_leave_request, get_tenancy_plan, list_tenancy_plans

router = APIRouter(prefix="/api/plans", tags=["plans"])


@router.get("")
def list_plans(email: str = Query(..., min_length=3)) -> dict:
    return list_tenancy_plans(email)


@router.get("/{plan_id}")
def get_plan(plan_id: str, email: Optional[str] = Query(None)) -> dict:
    return get_tenancy_plan(plan_id, email)



@router.post("/{plan_id}/leave")
def create_leave_request(plan_id: str, payload: PlanLeaveRequestInput) -> dict:
    return create_plan_leave_request(plan_id, payload.model_dump())
