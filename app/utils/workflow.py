from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from ..data import (
    CONTRACTS,
    LANDLORD_USER_ID,
    LEASE_REQUESTS,
    NOTIFICATIONS,
    PRICE_ADJUSTMENTS,
    TARIFF,
    TENANT_USER_ID,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_price_adjustment_record(property_id: str, payload: dict) -> dict:
    record = {
        "id": str(uuid4()),
        "property_id": property_id,
        "previous_tariff_id": str(payload["previous_tariff_id"]) if payload.get("previous_tariff_id") else TARIFF["id"],
        "proposed_usage_rate": payload.get("proposed_usage_rate"),
        "proposed_feed_in_rate": payload.get("proposed_feed_in_rate"),
        "proposed_daily_charge": payload.get("proposed_daily_charge"),
        "fixed_solar_rate_cents_per_kwh": payload.get("fixed_solar_rate_cents_per_kwh"),
        "reason": payload.get("reason"),
        "effective_from": payload["effective_from"].isoformat(),
        "status": payload["status"],
        "created_at": utc_now(),
    }
    PRICE_ADJUSTMENTS.insert(0, record)
    return record


def create_lease_request_record(property_id: str, payload: dict) -> dict:
    now = utc_now()
    tenant_user_id = payload.get("tenant_user_id") or TENANT_USER_ID
    landlord_user_id = payload.get("landlord_user_id") or LANDLORD_USER_ID
    record = {
        "id": str(uuid4()),
        "property_id": property_id,
        "tenant_user_id": tenant_user_id,
        "landlord_user_id": landlord_user_id,
        "request_type": payload["request_type"],
        "message": payload["message"],
        "status": "submitted",
        "requested_move_out_date": payload["requested_move_out_date"].isoformat() if payload.get("requested_move_out_date") else None,
        "proposed_move_in_date": payload["proposed_move_in_date"].isoformat() if payload.get("proposed_move_in_date") else None,
        "target_property_id": payload.get("target_property_id"),
        "reviewed_by_user_id": None,
        "review_notes": None,
        "created_at": now,
        "updated_at": now,
        "status_history": [{"status": "submitted", "changed_at": now, "changed_by_user_id": tenant_user_id}],
    }
    LEASE_REQUESTS.insert(0, record)
    create_notification_record(
        recipient_user_id=landlord_user_id,
        recipient_role="landlord",
        property_id=property_id,
        entity_type="lease_request",
        entity_id=record["id"],
        title="New tenant request",
        message=f"Tenant submitted a {record['request_type'].replace('_', ' ')} request for review.",
    )
    return record


def create_leave_request_record(property_id: str, payload: dict) -> dict:
    return create_lease_request_record(property_id, {"request_type": "leave_house", **payload})


def create_house_application_record(property_id: str, payload: dict) -> dict:
    return create_lease_request_record(property_id, {"request_type": "new_house_application", "target_property_id": property_id, **payload})


def find_lease_request(property_id: str, request_id: str) -> dict:
    for record in LEASE_REQUESTS:
        if record["property_id"] == property_id and record["id"] == request_id:
            return record
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lease request not found")


def update_lease_request_status(property_id: str, request_id: str, payload: dict) -> dict:
    record = find_lease_request(property_id, request_id)
    new_status = "declined" if payload["status"] == "rejected" else payload["status"]
    if record["status"] in {"approved", "declined", "cancelled"} and record["status"] != new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Final lease request status cannot be changed",
        )

    now = utc_now()
    reviewer_user_id = payload.get("reviewed_by_user_id") or record.get("landlord_user_id") or LANDLORD_USER_ID
    record["status"] = new_status
    record["reviewed_by_user_id"] = reviewer_user_id
    record["review_notes"] = payload.get("review_notes")
    record["updated_at"] = now
    record.setdefault("status_history", []).append(
        {
            "status": new_status,
            "changed_at": now,
            "changed_by_user_id": reviewer_user_id,
            "notes": payload.get("review_notes"),
        }
    )

    tenant_message = f"Your {record['request_type'].replace('_', ' ')} request is now {new_status}."
    if payload.get("review_notes"):
        tenant_message = f"{tenant_message} Notes: {payload['review_notes']}"
    create_notification_record(
        recipient_user_id=record.get("tenant_user_id"),
        recipient_role="tenant",
        property_id=property_id,
        entity_type="lease_request",
        entity_id=record["id"],
        title="Lease request status updated",
        message=tenant_message,
    )
    return record


def create_notification_record(
    *,
    recipient_user_id: str | None,
    recipient_role: str,
    property_id: str | None,
    entity_type: str,
    entity_id: str,
    title: str,
    message: str,
) -> dict:
    notification = {
        "id": str(uuid4()),
        "recipient_user_id": recipient_user_id,
        "recipient_role": recipient_role,
        "property_id": property_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "title": title,
        "message": message,
        "status": "unread",
        "created_at": utc_now(),
        "read_at": None,
    }
    NOTIFICATIONS.insert(0, notification)
    return notification


def list_notifications(recipient_user_id: str | None = None, recipient_role: str | None = None) -> list[dict]:
    rows = NOTIFICATIONS
    if recipient_user_id:
        rows = [row for row in rows if row.get("recipient_user_id") == recipient_user_id]
    if recipient_role:
        rows = [row for row in rows if row.get("recipient_role") == recipient_role]
    return rows


def mark_notification_read(notification_id: str) -> dict:
    for notification in NOTIFICATIONS:
        if notification["id"] == notification_id:
            notification["status"] = "read"
            notification["read_at"] = utc_now()
            return notification
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")


def build_contract_document(property_name: str, payload: dict) -> str:
    terms = payload.get("terms") or {}
    solar_rate = terms.get("tenantSolarRateCentsPerKwh", terms.get("fixedSolarRateCentsPerKwh", "TBD"))
    export_rate = terms.get("exportRateCentsPerKwh", "TBD")
    return (
        f"{payload['title']}\n\n"
        "DRAFT - Requires human/legal review before execution.\n\n"
        f"Property: {property_name}\n"
        f"Contract type: {payload['contract_type']}\n"
        f"Tenant solar rate: {solar_rate} cents/kWh\n"
        f"Export reference rate: {export_rate} cents/kWh\n\n"
        "Commercial intent: share rooftop solar savings with the tenant while "
        "preserving auditable landlord revenue, export revenue, and ROI cash flow.\n"
    )


def create_contract_record(property_id: str, property_name: str, payload: dict) -> dict:
    document_text = build_contract_document(property_name, payload)
    record = {
        "id": str(uuid4()),
        "property_id": property_id,
        "contract_type": payload["contract_type"],
        "title": payload["title"],
        "tenant_user_id": payload.get("tenant_user_id"),
        "landlord_user_id": payload.get("landlord_user_id"),
        "agent_user_id": payload.get("agent_user_id"),
        "solar_installation_id": str(payload["solar_installation_id"]) if payload.get("solar_installation_id") else None,
        "pricing_contract_id": str(payload["pricing_contract_id"]) if payload.get("pricing_contract_id") else None,
        "status": "draft",
        "terms": {"draftNotice": "Requires human/legal review before execution", **(payload.get("terms") or {})},
        "document_text": document_text,
        "created_at": utc_now(),
    }
    CONTRACTS.insert(0, record)
    return record
