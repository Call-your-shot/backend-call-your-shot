from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import Field

from .common import ApiModel


class AddressModel(ApiModel):
    address_line_1: Optional[str] = Field(default=None, alias="addressLine1")
    address_line_2: Optional[str] = Field(default=None, alias="addressLine2")
    suburb: Optional[str] = Field(default=None)
    state: Optional[str] = Field(default=None)
    postcode: Optional[str] = Field(default=None)
    country: Optional[str] = Field(default="Australia")
    full_address: Optional[str] = Field(default=None, alias="fullAddress")
    latitude: Optional[float] = Field(default=None, alias="lat")
    longitude: Optional[float] = Field(default=None, alias="lng")


class TenantInfo(ApiModel):
    name: str = Field(..., description="Tenant full name")
    email: str = Field(..., description="Tenant email address")


class SystemInfo(ApiModel):
    panel_count: int = Field(..., alias="panelCount")
    system_size_kw: float = Field(..., alias="systemSizeKw")
    panel_watts: int = Field(..., alias="panelWatts")
    orientation: str = Field(...)
    pitch_degrees: float = Field(..., alias="pitchDegrees")
    estimated_annual_ac_kwh: float = Field(..., alias="estimatedAnnualAcKwh")
    source: Literal["google", "mock"] = Field(...)


class ConsumptionInfo(ApiModel):
    bill_usage_kwh: float = Field(..., alias="billUsageKwh")
    billing_period_start: str = Field(..., alias="billingPeriodStart")
    billing_period_end: str = Field(..., alias="billingPeriodEnd")
    estimated_annual_kwh: float = Field(..., alias="estimatedAnnualKwh")
    rate_per_kwh_cents: float = Field(..., alias="ratePerKwhCents")
    rate_source: Literal["bill", "wollongong-default"] = Field(..., alias="rateSource")
    recommended_system_size_kw: float = Field(..., alias="recommendedSystemSizeKw")
    system_size_source: Literal["backend", "fallback"] = Field(..., alias="systemSizeSource")


class CreateProposalRequest(ApiModel):
    address: Union[str, AddressModel] = Field(...)
    tenant: TenantInfo = Field(...)
    system: SystemInfo = Field(...)
    consumption: ConsumptionInfo = Field(...)


class ProposalResponse(ApiModel):
    id: str = Field(...)
    property_id: str = Field(..., alias="propertyId")
    proposal_type: str = Field(default="solar", alias="proposalType")
    title: str = Field(...)
    description: str = Field(...)
    status: str = Field(...)
    invite_token: str = Field(..., alias="inviteToken")
    invite_url: str = Field(..., alias="inviteUrl")
    tenant: TenantInfo = Field(...)
    system: SystemInfo = Field(...)
    consumption: ConsumptionInfo = Field(...)
    financial_summary: dict[str, Any] = Field(..., alias="financialSummary")
    property: dict[str, Any] = Field(...)
    created_at: str = Field(..., alias="createdAt")


class AcceptProposalRequest(ApiModel):
    landlord_name: str = Field(..., alias="landlordName")
    landlord_email: str = Field(..., alias="landlordEmail")
