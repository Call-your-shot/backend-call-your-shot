from __future__ import annotations

from fastapi import APIRouter, Query, status

from ..api_link.energy import require_property
from ..data import (
    CONTRACTS,
    LANDLORD_USER_ID,
    LEASE_REQUESTS,
    PRICE_ADJUSTMENTS,
    PROPERTIES,
    PROPERTY,
    TENANT_USER_ID,
)
from ..schemas import ListResponse
from ..schemas.workflow import (
    Contract,
    ContractGenerationInput,
    HouseApplicationInput,
    LeaseRequest,
    LeaseRequestInput,
    LeaseRequestStatusUpdate,
    Notification,
    NotificationReadUpdate,
    PriceAdjustment,
    PriceAdjustmentInput,
    TenantLeaveRequestInput,
)
from ..utils.workflow import (
    create_contract_record,
    create_house_application_record,
    create_leave_request_record,
    create_lease_request_record,
    create_price_adjustment_record,
    list_notifications,
    mark_notification_read,
    update_lease_request_status,
)

router = APIRouter(prefix="/api/properties/{property_id}", tags=["workflow"])


@router.get("/price-adjustments", response_model=ListResponse)
def list_price_adjustments(property_id: str) -> dict:
    require_property(property_id)
    return {"data": [PriceAdjustment(**row) for row in PRICE_ADJUSTMENTS if row["property_id"] == property_id]}


@router.post("/price-adjustments", response_model=PriceAdjustment, status_code=status.HTTP_201_CREATED)
def create_price_adjustment(property_id: str, payload: PriceAdjustmentInput) -> PriceAdjustment:
    require_property(property_id)
    return PriceAdjustment(**create_price_adjustment_record(property_id, payload.model_dump()))


@router.get("/lease-requests", response_model=ListResponse)
def list_lease_requests(property_id: str) -> dict:
    require_property(property_id)
    return {"data": [LeaseRequest(**row) for row in LEASE_REQUESTS if row["property_id"] == property_id]}


@router.post("/lease-requests", response_model=LeaseRequest, status_code=status.HTTP_201_CREATED)
def create_lease_request(property_id: str, payload: LeaseRequestInput) -> LeaseRequest:
    require_property(property_id)
    return LeaseRequest(**create_lease_request_record(property_id, payload.model_dump()))


@router.post("/lease-requests/leave", response_model=LeaseRequest, status_code=status.HTTP_201_CREATED)
def apply_to_leave_property(property_id: str, payload: TenantLeaveRequestInput) -> LeaseRequest:
    require_property(property_id)
    return LeaseRequest(**create_leave_request_record(property_id, payload.model_dump()))


@router.post("/house-applications", response_model=LeaseRequest, status_code=status.HTTP_201_CREATED)
def apply_for_new_house(property_id: str, payload: HouseApplicationInput) -> LeaseRequest:
    require_property(property_id)
    return LeaseRequest(**create_house_application_record(property_id, payload.model_dump()))


@router.patch("/lease-requests/{request_id}/status", response_model=LeaseRequest)
def review_lease_request_status(
    property_id: str,
    request_id: str,
    payload: LeaseRequestStatusUpdate,
) -> LeaseRequest:
    require_property(property_id)
    return LeaseRequest(**update_lease_request_status(property_id, request_id, payload.model_dump()))


@router.get("/contracts", response_model=ListResponse)
def list_contracts(property_id: str) -> dict:
    require_property(property_id)
    return {"data": [Contract(**row) for row in CONTRACTS if row["property_id"] == property_id]}


@router.post("/contracts/generate", response_model=Contract, status_code=status.HTTP_201_CREATED)
def generate_contract(property_id: str, payload: ContractGenerationInput) -> Contract:
    require_property(property_id)
    property_name = next((row["name"] for row in PROPERTIES if row["id"] == property_id), PROPERTY["name"])
    return Contract(**create_contract_record(property_id, property_name, payload.model_dump()))


@router.get("/my-plan", response_model=dict)
def get_tenant_plan(
    property_id: str,
    tenant_user_id: str = Query(TENANT_USER_ID, alias="tenantUserId"),
) -> dict:
    require_property(property_id)
    requests = [
        row
        for row in LEASE_REQUESTS
        if row.get("tenant_user_id") == tenant_user_id and row["property_id"] == property_id
    ]
    return {
        "viewer": {"role": "tenant", "userId": tenant_user_id},
        "current_requests": [LeaseRequest(**row) for row in requests],
        "notifications": [
            Notification(**row)
            for row in list_notifications(recipient_user_id=tenant_user_id)
            if row.get("property_id") == property_id
        ],
    }


@router.get("/my-properties", response_model=dict)
def get_landlord_properties(
    property_id: str,
    landlord_user_id: str = Query(LANDLORD_USER_ID, alias="landlordUserId"),
) -> dict:
    require_property(property_id)
    requests = [
        row
        for row in LEASE_REQUESTS
        if row.get("landlord_user_id") == landlord_user_id and row["property_id"] == property_id
    ]
    property_ids = {row["property_id"] for row in requests} or {property_id}
    return {
        "viewer": {"role": "landlord", "userId": landlord_user_id},
        "properties": [
            {
                "property": prop,
                "lease_requests": [LeaseRequest(**row) for row in requests if row["property_id"] == prop["id"]],
            }
            for prop in PROPERTIES
            if prop["id"] in property_ids
        ],
        "notifications": [
            Notification(**row)
            for row in list_notifications(recipient_user_id=landlord_user_id)
            if row.get("property_id") == property_id
        ],
    }


@router.get("/notifications", response_model=ListResponse)
def get_notifications(
    property_id: str,
    recipient_user_id: str | None = Query(None, alias="recipientUserId"),
    recipient_role: str | None = Query(None, alias="recipientRole"),
) -> dict:
    require_property(property_id)
    rows = [row for row in list_notifications(recipient_user_id, recipient_role) if row.get("property_id") == property_id]
    return {"data": [Notification(**row) for row in rows]}


@router.patch("/notifications/{notification_id}/read", response_model=Notification)
def read_notification(property_id: str, notification_id: str, payload: NotificationReadUpdate) -> Notification:
    require_property(property_id)
    _ = payload
    return Notification(**mark_notification_read(notification_id))
