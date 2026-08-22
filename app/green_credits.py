"""Pure green-credit calculations and API-facing domain models."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MICROCREDITS_PER_CREDIT = 1_000_000
BASIS_POINTS_TOTAL = 10_000


def credits_to_microcredits(credits: Decimal | float | str) -> int:
    """Convert display credits to exact integer microcredits."""
    value = Decimal(str(credits))
    if not value.is_finite() or value <= 0:
        raise ValueError("credits must be a positive finite value")
    return int(
        (value * MICROCREDITS_PER_CREDIT).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    )


def microcredits_to_credits(value: int) -> str:
    """Return a stable six-decimal credit string for JSON responses."""
    return f"{Decimal(value) / MICROCREDITS_PER_CREDIT:.6f}"


def solar_kwh_to_microcredits(
    solar_consumed_kwh: Decimal | float | str,
    credits_per_kwh_microcredits: int = MICROCREDITS_PER_CREDIT,
) -> int:
    """Convert verified tenant-consumed solar to reward microcredits."""
    kwh = Decimal(str(solar_consumed_kwh))
    if not kwh.is_finite() or kwh < 0:
        raise ValueError("solar consumption must be a non-negative finite value")
    if credits_per_kwh_microcredits <= 0:
        raise ValueError("credits per kWh must be positive")
    return int(
        (kwh * credits_per_kwh_microcredits).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


@dataclass(frozen=True)
class MemberCredit:
    user_id: str
    role: str
    amount_microcredits: int


@dataclass(frozen=True)
class CreditSplit:
    total_microcredits: int
    allocations: tuple[MemberCredit, ...]
    unissued_microcredits: int


def _divide_role_share(
    role: str, role_microcredits: int, user_ids: list[str]
) -> tuple[MemberCredit, ...]:
    members = sorted(set(user_ids))
    if not members or role_microcredits <= 0:
        return ()
    base, remainder = divmod(role_microcredits, len(members))
    return tuple(
        MemberCredit(
            user_id=user_id,
            role=role,
            amount_microcredits=base + (1 if index < remainder else 0),
        )
        for index, user_id in enumerate(members)
        if base + (1 if index < remainder else 0) > 0
    )


def split_green_credits(
    total_microcredits: int,
    tenant_user_ids: list[str],
    owner_user_ids: list[str],
    tenant_share_bps: int = 7_000,
    owner_share_bps: int = 3_000,
) -> CreditSplit:
    """Split one earning event by role and equally within each role."""
    if total_microcredits < 0:
        raise ValueError("total microcredits cannot be negative")
    if tenant_share_bps < 0 or owner_share_bps < 0:
        raise ValueError("share basis points cannot be negative")
    if tenant_share_bps + owner_share_bps != BASIS_POINTS_TOTAL:
        raise ValueError("tenant and owner shares must total 10,000 basis points")

    tenant_share = total_microcredits * tenant_share_bps // BASIS_POINTS_TOTAL
    owner_share = total_microcredits - tenant_share
    tenant_allocations = _divide_role_share("tenant", tenant_share, tenant_user_ids)
    owner_allocations = _divide_role_share("landlord", owner_share, owner_user_ids)
    issued = sum(
        item.amount_microcredits for item in (*tenant_allocations, *owner_allocations)
    )
    return CreditSplit(
        total_microcredits=total_microcredits,
        allocations=(*tenant_allocations, *owner_allocations),
        unissued_microcredits=total_microcredits - issued,
    )
