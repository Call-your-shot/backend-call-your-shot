from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status


from ..clients.supabase_client import get_supabase_client
from ..data import PROPERTIES, PROPERTY_MEMBERSHIPS, PROPOSALS, USERS
from ..schemas import ListResponse
from ..schemas.proposal import (
    AcceptProposalRequest,
    AddressModel,
    CreateProposalRequest,
    ProposalResponse,
)
from ..utils.assessment_service import INITIAL_ASSESSMENTS

router = APIRouter(tags=["proposals"])


def _extract_property(address_raw: str | AddressModel | dict) -> dict:
    if isinstance(address_raw, str):
        full_addr = address_raw
        parts = [p.strip() for p in address_raw.split(",") if p.strip()]
        line1 = parts[0] if parts else "1 Main St"
        suburb = parts[1] if len(parts) > 1 else "Wollongong"
        state = "NSW"
        postcode = "2500"
    elif isinstance(address_raw, AddressModel):
        line1 = address_raw.address_line_1 or address_raw.full_address or "1 Main St"
        suburb = address_raw.suburb or "Wollongong"
        state = address_raw.state or "NSW"
        postcode = address_raw.postcode or "2500"
        full_addr = address_raw.full_address or f"{line1}, {suburb} {state} {postcode}"
    elif isinstance(address_raw, dict):
        line1 = address_raw.get("addressLine1") or address_raw.get("address_line_1") or address_raw.get("fullAddress") or "1 Main St"
        suburb = address_raw.get("suburb") or "Wollongong"
        state = address_raw.get("state") or "NSW"
        postcode = address_raw.get("postcode") or "2500"
        full_addr = address_raw.get("fullAddress") or f"{line1}, {suburb} {state} {postcode}"
    else:
        line1 = "1 Main St"
        suburb = "Wollongong"
        state = "NSW"
        postcode = "2500"
        full_addr = "1 Main St, Wollongong NSW 2500"

    # Check existing properties in memory
    for prop in PROPERTIES:
        if prop.get("address_line_1") == line1 or prop.get("name") == full_addr:
            return prop

    new_prop = {
        "id": str(uuid4()),
        "name": full_addr,
        "address_line_1": line1,
        "address_line_2": None,
        "suburb": suburb,
        "state": state,
        "postcode": postcode,
        "country": "AU",
        "roof_area_m2": 120.0,
        "usable_roof_area_m2": 85.0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    PROPERTIES.append(new_prop)

    # If Supabase is available, insert into Supabase
    sb = get_supabase_client()
    if sb:
        try:
            sb.from_("properties").insert([
                {
                    "id": new_prop["id"],
                    "name": new_prop["name"],
                    "address_line_1": new_prop["address_line_1"],
                    "suburb": new_prop["suburb"],
                    "state": new_prop["state"],
                    "postcode": new_prop["postcode"],
                    "country": new_prop["country"],
                }
            ]).execute()
        except Exception as err:
            print(f"[Supabase] Warning inserting property: {err}")

    return new_prop


@router.post("/create-proposal", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
@router.post("/api/v1/proposals/create", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_proposal(payload: CreateProposalRequest) -> ProposalResponse:

    property_rec = _extract_property(payload.address)

    proposal_id = str(uuid4())
    invite_token = str(uuid4())
    frontend_url = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000").rstrip("/")
    invite_url = f"{frontend_url}/invite/{invite_token}"

    grid_rate_cents = payload.consumption.rate_per_kwh_cents
    est_annual_ac = payload.system.estimated_annual_ac_kwh
    co2_offset = round(est_annual_ac * 0.0007, 2)
    assessment = None
    if payload.assessment_id:
        assessment = INITIAL_ASSESSMENTS.get(payload.assessment_id)
        if assessment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Referenced assessment was not found",
            )

    if assessment:
        financial_summary = {
            "assessmentId": assessment.id,
            "forecastSource": assessment.forecast_source,
            "estimatedAnnualTenantSavings": assessment.tenant_economics.annual_savings_dollars.median,
            "estimatedAnnualLandlordCashflow": assessment.landlord_economics.first_year_net_cashflow_dollars.median,
            "medianPaybackYears": assessment.landlord_economics.median_payback_years,
            "paybackRangeYears": assessment.landlord_economics.payback_range_years,
            "probabilityTenantSavesMoney": assessment.tenant_economics.probability_saves_money,
            "netInstallationCostDollars": assessment.landlord_economics.net_installation_cost_dollars,
            "co2OffsetTonnes": co2_offset,
            "currency": "AUD",
            "ratePerKwhCents": grid_rate_cents,
            "systemSizeKw": payload.system.system_size_kw,
            "modelVersion": "initial-assessment-v1",
        }
    else:
        # Legacy proposals remain supported, but explicitly use the tenant's
        # recommended-system demand rather than valuing every generated kWh
        # as tenant-consumed electricity.
        solar_used = min(est_annual_ac, payload.consumption.estimated_annual_kwh)
        est_annual_savings = round(solar_used * (grid_rate_cents / 100.0), 2)
        financial_summary = {
            "estimatedAnnualSavings": est_annual_savings,
            "co2OffsetTonnes": co2_offset,
            "currency": "AUD",
            "ratePerKwhCents": grid_rate_cents,
            "systemSizeKw": payload.system.system_size_kw,
            "warning": "Legacy proposal without a saved ROI assessment",
        }

    now_iso = datetime.now(timezone.utc).isoformat()

    proposal_rec = {
        "id": proposal_id,
        "property_id": property_rec["id"],
        "proposal_type": "solar",
        "assessment_id": payload.assessment_id,
        "title": f"Rooftop Solar Proposal - {property_rec['address_line_1']}",
        "description": f"Tenant {payload.tenant.name} initialized a {payload.system.system_size_kw}kW solar proposal.",
        "status": "sent",
        "invite_token": invite_token,
        "invite_url": invite_url,
        "tenant": payload.tenant.model_dump(),
        "landlord": payload.landlord.model_dump() if payload.landlord else None,
        "system": payload.system.model_dump(by_alias=True),
        "consumption": payload.consumption.model_dump(by_alias=True),
        "financial_summary": financial_summary,
        "property": property_rec,
        "created_at": now_iso,
    }

    PROPOSALS.append(proposal_rec)

    # Track tenant user
    tenant_email = payload.tenant.email.lower()
    if not any(u["email"].lower() == tenant_email for u in USERS):
        USERS.append({
            "id": str(uuid4()),
            "email": payload.tenant.email,
            "full_name": payload.tenant.name,
            "created_at": now_iso,
            "status": "active",
        })

    PROPERTY_MEMBERSHIPS.append({
        "id": str(uuid4()),
        "property_id": property_rec["id"],
        "email": tenant_email,
        "role": "tenant",
        "status": "active",
        "created_at": now_iso,
    })

    # Supabase persistence
    sb = get_supabase_client()
    if sb:
        try:
            sb.from_("proposals").insert([
                {
                    "id": proposal_id,
                    "property_id": property_rec["id"],
                    "proposal_type": "solar",
                    "title": proposal_rec["title"],
                    "description": proposal_rec["description"],
                    "status": "sent",
                    "invite_token": invite_token,
                    "invite_url": invite_url,
                    "financial_summary": financial_summary,
                    "terms": {
                        "assessmentId": payload.assessment_id,
                        "tenant": payload.tenant.model_dump(),
                        "landlord": payload.landlord.model_dump() if payload.landlord else None,
                        "system": payload.system.model_dump(by_alias=True),
                        "consumption": payload.consumption.model_dump(by_alias=True),
                    },
                }
            ]).execute()
        except Exception as err:
            print(f"[Supabase] Warning inserting proposal: {err}")

    return ProposalResponse(**proposal_rec)


@router.get("/proposals/{proposal_id_or_token}", response_model=ProposalResponse)
@router.get("/api/v1/proposals/{proposal_id_or_token}", response_model=ProposalResponse, include_in_schema=False)
def get_proposal(proposal_id_or_token: str) -> ProposalResponse:
    # Memory lookup
    for p in PROPOSALS:
        if p["id"] == proposal_id_or_token or p.get("invite_token") == proposal_id_or_token:
            return ProposalResponse(**p)

    # Supabase lookup
    sb = get_supabase_client()
    if sb:
        try:
            res = sb.from_("proposals").select("*").or_(f"id.eq.{proposal_id_or_token},invite_token.eq.{proposal_id_or_token}").execute()
            if res.data:
                row = res.data[0]
                terms = row.get("terms", {})
                prop_res = sb.from_("properties").select("*").eq("id", row["property_id"]).execute()
                prop_data = prop_res.data[0] if prop_res.data else {"id": row["property_id"], "name": row["title"]}
                return ProposalResponse(
                    id=row["id"],
                    property_id=row["property_id"],
                    proposal_type=row.get("proposal_type", "solar"),
                    title=row.get("title", ""),
                    description=row.get("description", ""),
                    status=row.get("status", "sent"),
                    invite_token=row.get("invite_token") or proposal_id_or_token,
                    invite_url=row.get("invite_url") or f"http://localhost:3000/invite/{proposal_id_or_token}",
                    tenant=terms.get("tenant", {"name": "Tenant", "email": "tenant@example.com"}),
                    landlord=terms.get("landlord"),
                    system=terms.get("system", {}),
                    consumption=terms.get("consumption", {}),
                    financial_summary=row.get("financial_summary", {}),
                    property=prop_data,
                    created_at=row.get("created_at", datetime.now(timezone.utc).isoformat()),
                )
        except Exception as err:
            print(f"[Supabase] Warning fetching proposal: {err}")

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")


@router.post("/proposals/{proposal_id_or_token}/accept", response_model=ProposalResponse)
@router.post("/api/v1/proposals/{proposal_id_or_token}/accept", response_model=ProposalResponse, include_in_schema=False)
def accept_proposal(proposal_id_or_token: str, payload: AcceptProposalRequest) -> ProposalResponse:

    found_prop = None
    for p in PROPOSALS:
        if p["id"] == proposal_id_or_token or p.get("invite_token") == proposal_id_or_token:
            p["status"] = "accepted"
            p["landlord"] = {"name": payload.landlord_name, "email": payload.landlord_email}
            found_prop = p
            break

    if not found_prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")

    landlord_email = payload.landlord_email.lower()
    now_iso = datetime.now(timezone.utc).isoformat()

    if not any(u["email"].lower() == landlord_email for u in USERS):
        USERS.append({
            "id": str(uuid4()),
            "email": payload.landlord_email,
            "full_name": payload.landlord_name,
            "created_at": now_iso,
            "status": "active",
        })

    PROPERTY_MEMBERSHIPS.append({
        "id": str(uuid4()),
        "property_id": found_prop["property_id"],
        "email": landlord_email,
        "role": "landlord",
        "status": "active",
        "created_at": now_iso,
    })

    sb = get_supabase_client()
    if sb:
        try:
            sb.from_("proposals").update({"status": "accepted"}).or_(f"id.eq.{proposal_id_or_token},invite_token.eq.{proposal_id_or_token}").execute()
        except Exception as err:
            print(f"[Supabase] Warning updating proposal acceptance: {err}")

    return ProposalResponse(**found_prop)


@router.get("/user-properties", response_model=ListResponse)

@router.get("/api/v1/properties/user", response_model=ListResponse)
def list_user_properties(
    email: str = Query(..., description="User email address"),
    role: Optional[str] = Query("landlord", description="Member role (e.g. landlord, tenant)"),
) -> dict:
    email_clean = email.strip().lower()
    prop_ids = {
        m["property_id"]
        for m in PROPERTY_MEMBERSHIPS
        if m["email"].lower() == email_clean and (not role or m["role"] == role)
    }

    user_props = [p for p in PROPERTIES if p["id"] in prop_ids]
    linked_proposals = [
        p for p in PROPOSALS
        if p["property_id"] in prop_ids or (p.get("landlord") and p["landlord"].get("email", "").lower() == email_clean)
    ]

    result = []
    for prop in user_props:
        prop_proposals = [pr for pr in linked_proposals if pr["property_id"] == prop["id"]]
        result.append({
            "property": prop,
            "proposals": prop_proposals,
        })

    return {"data": result}
