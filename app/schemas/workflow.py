from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import Field, model_validator

from .common import ApiModel


class PriceAdjustmentInput(ApiModel):
    previous_tariff_id: Optional[UUID] = Field(default=None, alias="previousTariffId")
    proposed_usage_rate: Optional[float] = Field(default=None, ge=0, alias="proposedUsageRate")
    proposed_feed_in_rate: Optional[float] = Field(default=None, ge=0, alias="proposedFeedInRate")
    proposed_daily_charge: Optional[float] = Field(default=None, ge=0, alias="proposedDailyCharge")
    fixed_solar_rate_cents_per_kwh: Optional[float] = Field(default=None, ge=0, alias="fixedSolarRateCentsPerKwh")
    reason: Optional[str] = Field(default=None, max_length=1000)
    effective_from: datetime = Field(alias="effectiveFrom")
    status: Literal["draft", "pending"] = "pending"

    @model_validator(mode="after")
    def require_change(self) -> "PriceAdjustmentInput":
        if all(
            value is None
            for value in (
                self.proposed_usage_rate,
                self.proposed_feed_in_rate,
                self.proposed_daily_charge,
                self.fixed_solar_rate_cents_per_kwh,
            )
        ):
            raise ValueError("at least one price field must be provided")
        return self


class PriceAdjustment(ApiModel):
    id: str
    property_id: str
    previous_tariff_id: Optional[str] = None
    proposed_usage_rate: Optional[float] = None
    proposed_feed_in_rate: Optional[float] = None
    proposed_daily_charge: Optional[float] = None
    fixed_solar_rate_cents_per_kwh: Optional[float] = None
    reason: Optional[str] = None
    effective_from: str
    status: str
    created_at: str


class LeaseRequestInput(ApiModel):
    request_type: str = Field(min_length=1, max_length=120, alias="requestType")
    message: str = Field(min_length=1, max_length=5000)
    tenant_user_id: Optional[str] = Field(default=None, alias="tenantUserId")


class LeaseRequest(ApiModel):
    id: str
    property_id: str
    tenant_user_id: Optional[str] = None
    request_type: str
    message: str
    status: str
    created_at: str


class ContractGenerationInput(ApiModel):
    contract_type: Literal["ppa", "lease_amendment", "energy_agreement"] = Field(alias="contractType")
    title: str = Field(default="Draft Solar PPA", min_length=1, max_length=160)
    tenant_user_id: Optional[str] = Field(default=None, alias="tenantUserId")
    landlord_user_id: Optional[str] = Field(default=None, alias="landlordUserId")
    agent_user_id: Optional[str] = Field(default=None, alias="agentUserId")
    solar_installation_id: Optional[UUID] = Field(default=None, alias="solarInstallationId")
    pricing_contract_id: Optional[UUID] = Field(default=None, alias="pricingContractId")
    terms: dict[str, Any] = Field(default_factory=dict)


class Contract(ApiModel):
    id: str
    property_id: str
    contract_type: str
    title: str
    tenant_user_id: Optional[str] = None
    landlord_user_id: Optional[str] = None
    agent_user_id: Optional[str] = None
    solar_installation_id: Optional[str] = None
    pricing_contract_id: Optional[str] = None
    status: str
    terms: dict[str, Any]
    document_text: str
    created_at: str
