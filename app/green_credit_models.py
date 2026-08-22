"""Pydantic v2 contracts for green-credit and project endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class WalletResponse(BaseModel):
    account_id: UUID | None
    status: Literal["active", "suspended", "closed"] | None
    available_credits: str
    lifetime_earned_credits: str
    lifetime_allocated_credits: str


class LedgerEntryResponse(BaseModel):
    id: UUID
    entry_type: Literal["earn", "allocate", "refund", "adjustment"]
    amount_credits: str
    property_id: UUID | None = None
    project_id: UUID | None = None
    source_energy_reading_id: UUID | None = None
    source_solar_kwh: float | None = None
    beneficiary_role: Literal["tenant", "landlord", "agent"] | None = None
    description: str
    occurred_at: datetime
    created_at: datetime


class LedgerPageResponse(BaseModel):
    data: list[LedgerEntryResponse]
    next_cursor: datetime | None = None


class GreenProjectResponse(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str
    category: str
    location: str | None = None
    image_path: str | None = None
    target_credits: str
    funded_credits: str
    remaining_credits: str
    minimum_allocation_credits: str
    funding_percentage: float
    status: Literal["draft", "open", "funded", "active", "completed", "cancelled"]
    impact_unit: str
    expected_impact: float | None = None
    verification_method: str
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    metadata: dict


class ProjectPageResponse(BaseModel):
    data: list[GreenProjectResponse]
    next_cursor: datetime | None = None


class AllocationRequest(BaseModel):
    requested_credits: Annotated[Decimal, Field(gt=0, max_digits=24, decimal_places=6)]
    idempotency_key: Annotated[str, Field(min_length=8, max_length=200)]


class AllocationResponse(BaseModel):
    allocation_id: UUID
    requested_credits: str
    allocated_credits: str
    partial: bool
    available_balance_credits: str
    project_remaining_credits: str | None = None
    project_status: str | None = None
    idempotent_replay: bool


class AllocationItemResponse(BaseModel):
    id: UUID
    project_id: UUID
    requested_credits: str
    allocated_credits: str
    status: Literal["confirmed", "refunded"]
    idempotency_key: str
    allocated_at: datetime


class AllocationPageResponse(BaseModel):
    data: list[AllocationItemResponse]
    next_cursor: datetime | None = None


class AccrualRequest(BaseModel):
    property_id: UUID
    period_start: datetime
    period_end: datetime

    @model_validator(mode="after")
    def validate_period(self) -> AccrualRequest:
        if self.period_start.tzinfo is None or self.period_end.tzinfo is None:
            raise ValueError("period timestamps must be timezone-aware")
        if self.period_end <= self.period_start:
            raise ValueError("period_end must be after period_start")
        return self


class AccrualResponse(BaseModel):
    processed_readings: int
    skipped_readings: int
    ledger_entries_created: int
    tenant_issued_credits: str
    owner_issued_credits: str
    unissued_credits: str
    warnings: list[dict[str, str]] = Field(default_factory=list)
