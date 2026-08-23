from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import HTTPException, status

from ..data import DEMO_NOW, DEMO_TODAY, FRONTEND_NOTIFICATIONS, LANDLORD_PROPERTY_VIEWS, LEASE_REQUESTS, TENANCY_PLANS
from .address import parse_frontend_address


def _email_matches(row: dict, email: str) -> bool:
    email_clean = email.strip().lower()
    candidate_emails = [row.get("email", ""), *(row.get("emails") or [])]
    return email_clean in {candidate.strip().lower() for candidate in candidate_emails}


def _owner_matches(row: dict, email: str) -> bool:
    email_clean = email.strip().lower()
    owner_emails = [row.get("email", ""), *(row.get("owner_emails") or [])]
    return email_clean in {owner_email.strip().lower() for owner_email in owner_emails}


def _address_label(address: dict) -> str:
    return f"{address['street']}, {address['suburb']}"


def _create_frontend_notification(
    *,
    email: str,
    notification_type: str,
    message: str,
    action_required: bool,
    related_id: str,
) -> dict:
    notification = {
        "id": f"notif_{len(FRONTEND_NOTIFICATIONS) + 1:04d}",
        "email": email.strip().lower(),
        "type": notification_type,
        "message": message,
        "createdAt": DEMO_NOW,
        "read": False,
        "actionRequired": action_required,
        "relatedId": related_id,
    }
    FRONTEND_NOTIFICATIONS.insert(0, notification)
    return notification


def list_frontend_notifications(email: str) -> dict:
    email_clean = email.strip().lower()
    return {
        "notifications": [
            {key: value for key, value in row.items() if key != "email"}
            for row in FRONTEND_NOTIFICATIONS
            if row.get("email") == email_clean
        ]
    }


def _find_plan(plan_id: str, email: Optional[str] = None) -> dict:
    for row in TENANCY_PLANS:
        if row["id"] == plan_id and (email is None or _email_matches(row, email)):
            return row
    for row in TENANCY_PLANS:
        if row["id"] == plan_id:
            return row

    # Fallback plan template for unseeded plan IDs
    tenant_name = email.split("@")[0].replace(".", " ").title() if email and "@" in email else "Demo Tenant"
    return {
        "id": plan_id,
        "email": email or "tenant@example.com",
        "tenant_name": tenant_name,
        "property_id": "prop-priya-figtree",
        "status": "active",
        "address": {
            "street": "12/88 Corrimal Street",
            "suburb": "Wollongong",
            "state": "NSW",
            "postcode": "2500",
        },
        "image_variant": 1,
        "start_date": "2025-03-01",
        "rate_per_kwh_cents": 15,
        "grid_rate_cents": 29,
        "max_term_years": 9,
        "monthly_reserve_contribution": 14,
        "balance_repaid": 1120,
        "balance_total": 4100,
        "estimated_completion_date": "2032-01-01",
        "landlord_name": "Coastal Realty Group",
        "property_manager": "Coastal Realty Group",
        "landlord_agreed_date": "2025-02-14",
        "system_size_kw": 5.3,
        "leave_request": None,
        "monthly": [
            {"month": "Jul 2025", "solarUsedKwh": 190, "gridUsedKwh": 210, "chargeDollars": 28.5, "withoutSolarDollars": 116.0, "savingsDollars": 24.7},
            {"month": "Aug 2025", "solarUsedKwh": 210, "gridUsedKwh": 195, "chargeDollars": 31.5, "withoutSolarDollars": 117.5, "savingsDollars": 26.3},
            {"month": "Sep 2025", "solarUsedKwh": 220, "gridUsedKwh": 180, "chargeDollars": 33.0, "withoutSolarDollars": 116.0, "savingsDollars": 30.8},
            {"month": "Oct 2025", "solarUsedKwh": 240, "gridUsedKwh": 160, "chargeDollars": 36.0, "withoutSolarDollars": 116.0, "savingsDollars": 33.6},
            {"month": "Nov 2025", "solarUsedKwh": 250, "gridUsedKwh": 150, "chargeDollars": 37.5, "withoutSolarDollars": 116.0, "savingsDollars": 35.0},
            {"month": "Dec 2025", "solarUsedKwh": 260, "gridUsedKwh": 140, "chargeDollars": 39.0, "withoutSolarDollars": 116.0, "savingsDollars": 36.4},
            {"month": "Jan 2026", "solarUsedKwh": 270, "gridUsedKwh": 130, "chargeDollars": 40.5, "withoutSolarDollars": 116.0, "savingsDollars": 37.8},
            {"month": "Feb 2026", "solarUsedKwh": 250, "gridUsedKwh": 150, "chargeDollars": 37.5, "withoutSolarDollars": 116.0, "savingsDollars": 35.0},
            {"month": "Mar 2026", "solarUsedKwh": 230, "gridUsedKwh": 170, "chargeDollars": 34.5, "withoutSolarDollars": 116.0, "savingsDollars": 32.2},
            {"month": "Apr 2026", "solarUsedKwh": 210, "gridUsedKwh": 190, "chargeDollars": 31.5, "withoutSolarDollars": 116.0, "savingsDollars": 29.4},
            {"month": "May 2026", "solarUsedKwh": 180, "gridUsedKwh": 220, "chargeDollars": 27.0, "withoutSolarDollars": 116.0, "savingsDollars": 25.2},
            {"month": "Jun 2026", "solarUsedKwh": 170, "gridUsedKwh": 230, "chargeDollars": 25.5, "withoutSolarDollars": 116.0, "savingsDollars": 23.8},
            {"month": "Jul 2026", "solarUsedKwh": 190, "gridUsedKwh": 210, "chargeDollars": 28.5, "withoutSolarDollars": 116.0, "savingsDollars": 26.6},
            {"month": "Aug 2026", "solarUsedKwh": 210, "gridUsedKwh": 195, "chargeDollars": 31.5, "withoutSolarDollars": 117.5, "savingsDollars": 26.3},
        ],
    }




def _find_property(property_id: str) -> dict:
    for row in LANDLORD_PROPERTY_VIEWS:
        if row["id"] == property_id or property_id in (row.get("aliases") or []):
            return row
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")



def _latest_leave_request(property_id: Optional[str] = None, tenant_user_id: Optional[str] = None) -> Optional[dict]:
    rows = LEASE_REQUESTS
    if property_id:
        rows = [row for row in rows if row.get("property_id") == property_id or row.get("target_property_id") == property_id]
    if tenant_user_id:
        rows = [row for row in rows if row.get("tenant_user_id") == tenant_user_id]
    rows = [row for row in rows if row.get("request_type") in {"leave_house", "new_house_application"}]
    if not rows:
        return None

    row = rows[0]
    return {
        "id": row["id"],
        "type": row["request_type"],
        "status": row["status"],
        "message": row["message"],
        "requestedMoveOutDate": row.get("requested_move_out_date"),
        "proposedMoveInDate": row.get("proposed_move_in_date"),
        "reviewNotes": row.get("review_notes"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _plan_summary(row: dict) -> dict:
    last_month = row["monthly"][-1] if row.get("monthly") else None
    return {
        "id": row["id"],
        "status": row["status"],
        "address": row["address"],
        "imageVariant": row["image_variant"],
        "landlordName": row["landlord_name"],
        "balanceRepaid": row["balance_repaid"],
        "balanceTotal": row["balance_total"],
        "lastMonth": {
            "month": last_month["month"],
            "savingsDollars": last_month["savingsDollars"],
        } if last_month else None,
    }


def _plan_detail(row: dict) -> dict:
    return {
        "id": row["id"],
        "propertyId": row["property_id"],
        "address": row["address"],
        "imageVariant": row["image_variant"],
        "status": row["status"],
        "startDate": row["start_date"],
        "ratePerKwhCents": row["rate_per_kwh_cents"],
        "gridRateCents": row["grid_rate_cents"],
        "maxTermYears": row["max_term_years"],
        "monthlyReserveContribution": row["monthly_reserve_contribution"],
        "balanceRepaid": row["balance_repaid"],
        "balanceTotal": row["balance_total"],
        "estimatedCompletionDate": row["estimated_completion_date"],
        "landlordName": row["landlord_name"],
        "propertyManager": row["property_manager"],
        "landlordAgreedDate": row["landlord_agreed_date"],
        "systemSizeKw": row["system_size_kw"],
        "monthly": row["monthly"],
        "leaveRequest": row.get("leave_request") or _latest_leave_request(property_id=row["property_id"]),
    }


def list_tenancy_plans(email: str) -> dict:
    return {"plans": [_plan_summary(row) for row in TENANCY_PLANS if _email_matches(row, email)]}


def list_tenancy_details(email: str) -> list[dict]:
    return [_plan_detail(row) for row in TENANCY_PLANS if _email_matches(row, email)]


def get_tenancy_plan(plan_id: str, email: Optional[str] = None) -> dict:
    return _plan_detail(_find_plan(plan_id, email))



def create_plan_leave_request(plan_id: str, payload: dict) -> dict:
    plan = _find_plan(plan_id, payload["email"])
    property_row = _find_property(plan["property_id"])
    if plan.get("leave_request") and plan["leave_request"]["status"] == "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Leave request already pending")

    move_out_date = payload["move_out_date"].isoformat()
    leave_request = {
        "requestedDate": DEMO_TODAY,
        "moveOutDate": move_out_date,
        "reason": payload["reason"],
        "note": payload.get("note"),
        "status": "pending",
        "timeline": {"noticeGiven": DEMO_TODAY},
    }
    plan["status"] = "leaving"
    plan["leave_request"] = leave_request
    property_row["leave_request"] = {
        **leave_request,
        "tenantName": property_row.get("current_tenant", {}).get("name") or plan.get("tenant_name"),
        "planId": plan["id"],
        "tenantEmail": plan["email"],
    }

    owner_email = (property_row.get("owner_emails") or [property_row["email"]])[0]
    _create_frontend_notification(
        email=owner_email,
        notification_type="leave_request_submitted",
        message=f"{property_row['leave_request']['tenantName']} requested to move out of {_address_label(plan['address'])}.",
        action_required=True,
        related_id=property_row["id"],
    )
    return _plan_detail(plan)


def withdraw_plan_leave_request(plan_id: str, email: str) -> dict:
    plan = _find_plan(plan_id, email)
    leave_request = plan.get("leave_request")
    if not leave_request or leave_request.get("status") != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending leave request")
    plan["status"] = "active"
    plan["leave_request"] = None
    property_row = _find_property(plan["property_id"])
    property_row["leave_request"] = None
    return _plan_detail(plan)


def _property_summary(row: dict) -> dict:
    tenant = row.get("current_tenant") or {}
    system = row.get("system") or {}
    return {
        "id": row["id"],
        "address": row["address"],
        "imageVariant": row["image_variant"],
        "occupancyStatus": row["occupancy_status"],
        "systemSizeKw": system.get("sizeKw"),
        "currentTenantName": tenant.get("name"),
        "monthlyIncome": row["monthly_income"],
        "balanceOutstanding": row["balance_outstanding"],
    }


def _property_detail(row: dict) -> dict:
    return {
        "id": row["id"],
        "address": row["address"],
        "imageVariant": row["image_variant"],
        "occupancyStatus": row["occupancy_status"],
        "system": row["system"],
        "currentTenant": row["current_tenant"],
        "tenantHistory": row["tenant_history"],
        "monthlyIncome": row["monthly_income"],
        "balanceOutstanding": row["balance_outstanding"],
        "balanceTotal": row["balance_total"],
        "totalEarned": row["total_earned"],
        "totalInvested": row["total_invested"],
        "monthly": row["monthly"],
        "maintenanceReserve": row["maintenance_reserve"],
        "pendingInvitationEmail": row["pending_invitation_email"],
        "performanceAlert": row["performance_alert"],
        "leaveRequest": _property_leave_request(row),
    }


def list_landlord_properties(email: str) -> dict:
    return {"properties": [_property_summary(row) for row in LANDLORD_PROPERTY_VIEWS if _owner_matches(row, email)]}


def list_landlord_property_details(email: str) -> list[dict]:
    return [_property_detail(row) for row in LANDLORD_PROPERTY_VIEWS if _owner_matches(row, email)]


def get_landlord_property(property_id: str, email: str) -> dict:
    row = _find_property(property_id)
    if not _owner_matches(row, email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not this property's owner")
    return _property_detail(row)


def get_frontend_dashboard(email: str) -> dict:
    return {
        "tenancies": list_tenancy_details(email),
        "ownedProperties": list_landlord_property_details(email),
    }


def _property_leave_request(row: dict) -> Optional[dict]:
    leave_request = row.get("leave_request")
    if not leave_request:
        return _latest_leave_request(property_id=row["id"])
    return {
        "tenantName": leave_request.get("tenantName"),
        "requestedDate": leave_request["requestedDate"],
        "moveOutDate": leave_request["moveOutDate"],
        "reason": leave_request["reason"],
        "status": leave_request["status"],
    }


def approve_property_leave_request(property_id: str, payload: dict) -> dict:
    property_row = _find_property(property_id)
    if not _owner_matches(property_row, payload["email"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not this property's owner")

    leave_request = property_row.get("leave_request")
    if not leave_request or leave_request.get("status") != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending leave request")

    leave_request["status"] = "approved"
    leave_request.setdefault("timeline", {})["approved"] = DEMO_TODAY
    plan = _find_plan(leave_request["planId"])
    plan["status"] = "ended"
    if plan.get("leave_request"):
        plan["leave_request"]["status"] = "approved"
        plan["leave_request"].setdefault("timeline", {})["approved"] = DEMO_TODAY

    _create_frontend_notification(
        email=leave_request["tenantEmail"],
        notification_type="leave_request_approved",
        message=f"Your landlord approved your move-out for {_address_label(plan['address'])}.",
        action_required=False,
        related_id=plan["id"],
    )
    return _property_detail(property_row)


def acknowledge_property_leave_request(property_id: str, payload: dict) -> dict:
    property_row = _find_property(property_id)
    if not _owner_matches(property_row, payload["email"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not this property's owner")
    leave_request = property_row.get("leave_request")
    if not leave_request or leave_request.get("status") != "pending":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No pending leave request")
    leave_request["status"] = "acknowledged"
    leave_request.setdefault("timeline", {})["landlordAcknowledged"] = DEMO_TODAY
    plan = _find_plan(leave_request["planId"])
    if plan.get("leave_request"):
        plan["leave_request"]["status"] = "acknowledged"
        plan["leave_request"].setdefault("timeline", {})["landlordAcknowledged"] = DEMO_TODAY
    return _property_detail(property_row)


def create_landlord_property(payload: dict) -> dict:
    address_text = payload["address"].strip()
    system_input = payload.get("solar_system") or {}
    property_id = f"prop-{uuid4()}"
    system = None
    if system_input:
        system = {
            "sizeKw": float(system_input.get("systemSizeKw") or system_input.get("sizeKw") or 0),
            "panelCount": int(system_input.get("panelCount") or 0),
            "installDate": DEMO_TODAY,
            "inverterModel": "To be confirmed at installation",
            "warrantyExpiry": "",
            "status": "normal",
            "todayGenerationKwh": 0,
            "currentOutputKw": 0,
            "performancePercent": 100,
            "lastReadingAt": DEMO_NOW,
            "dailyOutputKwh30d": [],
            "serviceHistory": [],
        }
    row = {
        "id": property_id,
        "aliases": [],
        "email": payload["email"].strip().lower(),
        "owner_emails": [payload["email"].strip().lower()],
        "address": parse_frontend_address(address_text),
        "image_variant": 0,
        "occupancy_status": "pending_invitation" if payload.get("invite_email") else "vacant",
        "system": system,
        "current_tenant": None,
        "tenant_history": [],
        "monthly_income": 0,
        "balance_outstanding": 0,
        "balance_total": 0,
        "total_earned": 0,
        "total_invested": 0,
        "monthly": [],
        "maintenance_reserve": {
            "accrued": 0,
            "nextCostDescription": "First inspection",
            "nextCostDate": "",
            "nextCostEstimate": 150,
        },
        "pending_invitation_email": payload.get("invite_email"),
        "performance_alert": None,
        "leave_request": None,
    }
    LANDLORD_PROPERTY_VIEWS.append(row)
    return _property_detail(row)


def invite_property_tenant(property_id: str, payload: dict) -> dict:
    property_row = _find_property(property_id)
    if not _owner_matches(property_row, payload["email"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not this property's owner")

    invite_email = payload["invite_email"].strip().lower()
    property_row["occupancy_status"] = "pending_invitation"
    property_row["pending_invitation_email"] = invite_email
    _create_frontend_notification(
        email=invite_email,
        notification_type="tenant_invitation",
        message=f"{property_row.get('property_manager') or 'Your property manager'} invited you to a solar plan at {_address_label(property_row['address'])}.",
        action_required=True,
        related_id=property_row["id"],
    )
    return _property_detail(property_row)


def accept_property_invitation(property_id: str, payload: dict) -> dict:
    property_row = _find_property(property_id)
    email = payload["email"].strip().lower()
    if property_row.get("pending_invitation_email") != email:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email is not invited to this property")

    property_row["occupancy_status"] = "occupied"
    property_row["pending_invitation_email"] = None
    property_row["current_tenant"] = {
        "name": email.split("@")[0].replace(".", " ").title(),
        "tenancyStart": DEMO_TODAY,
        "tenancyEnd": None,
        "ratePerKwhCents": property_row.get("current_tenant", {}).get("ratePerKwhCents", 15),
        "contributionToBalance": 0,
        "current": True,
    }
    property_row["tenant_history"].insert(0, property_row["current_tenant"])
    return _property_detail(property_row)
