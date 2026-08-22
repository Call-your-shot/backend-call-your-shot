from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ..data import CONTRACTS, LEASE_REQUESTS, PRICE_ADJUSTMENTS, TARIFF


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
    record = {
        "id": str(uuid4()),
        "property_id": property_id,
        "tenant_user_id": payload.get("tenant_user_id"),
        "request_type": payload["request_type"],
        "message": payload["message"],
        "status": "submitted",
        "created_at": utc_now(),
    }
    LEASE_REQUESTS.insert(0, record)
    return record


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
