from __future__ import annotations

from fastapi import APIRouter, status

from ..api_link.energy import require_property
from ..data import CONTRACTS, LEASE_REQUESTS, PRICE_ADJUSTMENTS, PROPERTY
from ..schemas import ListResponse
from ..schemas.workflow import (
    Contract,
    ContractGenerationInput,
    LeaseRequest,
    LeaseRequestInput,
    PriceAdjustment,
    PriceAdjustmentInput,
)
from ..utils.workflow import create_contract_record, create_lease_request_record, create_price_adjustment_record

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


@router.get("/contracts", response_model=ListResponse)
def list_contracts(property_id: str) -> dict:
    require_property(property_id)
    return {"data": [Contract(**row) for row in CONTRACTS if row["property_id"] == property_id]}


@router.post("/contracts/generate", response_model=Contract, status_code=status.HTTP_201_CREATED)
def generate_contract(property_id: str, payload: ContractGenerationInput) -> Contract:
    require_property(property_id)
    return Contract(**create_contract_record(property_id, PROPERTY["name"], payload.model_dump()))
