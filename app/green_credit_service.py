"""Application service mapping storage records to stable API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .green_credit_models import (
    AccrualResponse,
    AllocationItemResponse,
    AllocationPageResponse,
    AllocationResponse,
    GreenProjectResponse,
    LedgerEntryResponse,
    LedgerPageResponse,
    ProjectPageResponse,
    WalletResponse,
)
from .green_credit_repository import GreenCreditRepository
from .green_credits import microcredits_to_credits


def _integer(row: dict[str, Any], field: str) -> int:
    return int(row.get(field) or 0)


def build_wallet(repository: GreenCreditRepository) -> WalletResponse:
    row = repository.get_wallet()
    if row is None:
        return WalletResponse(
            account_id=None,
            status=None,
            available_credits="0.000000",
            lifetime_earned_credits="0.000000",
            lifetime_allocated_credits="0.000000",
            verified_solar_kwh=None,
        )
    return WalletResponse(
        account_id=row["account_id"],
        status=row["status"],
        available_credits=microcredits_to_credits(
            _integer(row, "available_microcredits")
        ),
        lifetime_earned_credits=microcredits_to_credits(
            _integer(row, "lifetime_earned_microcredits")
        ),
        lifetime_allocated_credits=microcredits_to_credits(
            _integer(row, "lifetime_allocated_microcredits")
        ),
        verified_solar_kwh=(
            float(row["verified_solar_kwh"])
            if row.get("verified_solar_kwh") is not None
            else None
        ),
    )


def build_ledger_page(
    repository: GreenCreditRepository, limit: int, cursor: datetime | None
) -> LedgerPageResponse:
    rows = repository.list_ledger(limit, cursor)
    data = [
        LedgerEntryResponse(
            id=row["id"],
            entry_type=row["entry_type"],
            amount_credits=microcredits_to_credits(
                _integer(row, "amount_microcredits")
            ),
            property_id=row.get("property_id"),
            project_id=row.get("project_id"),
            source_energy_reading_id=row.get("source_energy_reading_id"),
            source_solar_kwh=(
                float(row["source_solar_kwh"])
                if row.get("source_solar_kwh") is not None
                else None
            ),
            beneficiary_role=row.get("beneficiary_role"),
            description=row["description"],
            occurred_at=row["occurred_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]
    return LedgerPageResponse(
        data=data,
        next_cursor=data[-1].created_at if len(rows) == limit else None,
    )


def _project(row: dict[str, Any]) -> GreenProjectResponse:
    target = _integer(row, "target_microcredits")
    funded = _integer(row, "funded_microcredits")
    percentage = round(funded / target * 100, 2) if target else 0.0
    return GreenProjectResponse(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        category=row["category"],
        location=row.get("location"),
        image_path=row.get("image_path"),
        target_credits=microcredits_to_credits(target),
        funded_credits=microcredits_to_credits(funded),
        remaining_credits=microcredits_to_credits(
            _integer(row, "remaining_microcredits")
        ),
        minimum_allocation_credits=microcredits_to_credits(
            _integer(row, "minimum_allocation_microcredits")
        ),
        funding_percentage=percentage,
        status=row["status"],
        impact_unit=row["impact_unit"],
        expected_impact=(
            float(row["expected_impact"])
            if row.get("expected_impact") is not None
            else None
        ),
        verification_method=row["verification_method"],
        opens_at=row.get("opens_at"),
        closes_at=row.get("closes_at"),
        metadata=row.get("metadata") or {},
    )


def build_project_page(
    repository: GreenCreditRepository,
    status: str | None,
    limit: int,
    cursor: datetime | None,
) -> ProjectPageResponse:
    rows = repository.list_projects(status, limit, cursor)
    data = [_project(row) for row in rows]
    next_cursor = None
    if len(rows) == limit:
        next_cursor = datetime.fromisoformat(
            str(rows[-1]["created_at"]).replace("Z", "+00:00")
        )
    return ProjectPageResponse(data=data, next_cursor=next_cursor)


def build_project(
    repository: GreenCreditRepository, project_id: str
) -> GreenProjectResponse | None:
    row = repository.get_project(project_id)
    return _project(row) if row else None


def allocate_to_project(
    repository: GreenCreditRepository,
    project_id: str,
    requested_microcredits: int,
    idempotency_key: str,
) -> AllocationResponse:
    row = repository.allocate(project_id, requested_microcredits, idempotency_key)
    return AllocationResponse(
        allocation_id=row["allocation_id"],
        requested_credits=microcredits_to_credits(
            _integer(row, "requested_microcredits")
        ),
        allocated_credits=microcredits_to_credits(
            _integer(row, "allocated_microcredits")
        ),
        partial=bool(row.get("partial")),
        available_balance_credits=microcredits_to_credits(
            _integer(row, "available_balance_microcredits")
        ),
        project_remaining_credits=(
            microcredits_to_credits(_integer(row, "project_remaining_microcredits"))
            if row.get("project_remaining_microcredits") is not None
            else None
        ),
        project_status=row.get("project_status"),
        idempotent_replay=bool(row.get("idempotent_replay")),
    )


def build_allocation_page(
    repository: GreenCreditRepository, limit: int, cursor: datetime | None
) -> AllocationPageResponse:
    rows = repository.list_allocations(limit, cursor)
    data = [
        AllocationItemResponse(
            id=row["id"],
            project_id=row["project_id"],
            requested_credits=microcredits_to_credits(
                _integer(row, "requested_microcredits")
            ),
            allocated_credits=microcredits_to_credits(
                _integer(row, "allocated_microcredits")
            ),
            status=row["status"],
            idempotency_key=row["idempotency_key"],
            allocated_at=row["allocated_at"],
        )
        for row in rows
    ]
    return AllocationPageResponse(
        data=data,
        next_cursor=data[-1].allocated_at if len(rows) == limit else None,
    )


def accrue_period(
    repository: GreenCreditRepository,
    property_id: str,
    period_start: datetime,
    period_end: datetime,
) -> AccrualResponse:
    row = repository.accrue(property_id, period_start, period_end)
    unissued = _integer(row, "unissued_microcredits")
    warnings = []
    if unissued:
        warnings.append(
            {
                "code": "MISSING_ROLE_BENEFICIARY",
                "message": "Some role shares were not issued because no active member existed at the reading time.",
            }
        )
    return AccrualResponse(
        processed_readings=_integer(row, "processed_readings"),
        skipped_readings=_integer(row, "skipped_readings"),
        ledger_entries_created=_integer(row, "ledger_entries_created"),
        tenant_issued_credits=microcredits_to_credits(
            _integer(row, "tenant_issued_microcredits")
        ),
        owner_issued_credits=microcredits_to_credits(
            _integer(row, "owner_issued_microcredits")
        ),
        unissued_credits=microcredits_to_credits(unissued),
        warnings=warnings,
    )
