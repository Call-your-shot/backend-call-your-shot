"""Pure financial calculations. This module has no FastAPI dependency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import fsum

from .models import MonthlySolarRecord


@dataclass(frozen=True)
class CapitalRecoveryResult:
    recovered_dollars: float
    remaining_dollars: float
    capital_recovered_percentage: float
    net_roi_percentage: float | None


def calculate_net_installation_cost(
    gross_installation_cost_dollars: float,
    stc_benefit_dollars: float = 0.0,
    other_rebates_dollars: float = 0.0,
) -> float:
    net_cost = (
        gross_installation_cost_dollars - stc_benefit_dollars - other_rebates_dollars
    )
    if (
        min(
            gross_installation_cost_dollars,
            stc_benefit_dollars,
            other_rebates_dollars,
        )
        < 0
    ):
        raise ValueError("installation costs and rebates cannot be negative")
    if net_cost < 0:
        raise ValueError("rebates cannot exceed gross installation cost")
    return net_cost


def calculate_monthly_cashflow(record: MonthlySolarRecord) -> float:
    return (
        record.tenant_revenue_dollars
        + record.export_revenue_dollars
        - record.operating_cost_dollars
    )


def calculate_capital_recovery(
    installation_cost: float, monthly_cashflows: list[float]
) -> CapitalRecoveryResult:
    if installation_cost < 0:
        raise ValueError("installation_cost cannot be negative")
    recovered = fsum(monthly_cashflows)
    remaining = max(installation_cost - recovered, 0.0)
    if installation_cost == 0:
        return CapitalRecoveryResult(recovered, 0.0, 100.0, None)
    return CapitalRecoveryResult(
        recovered_dollars=recovered,
        remaining_dollars=remaining,
        capital_recovered_percentage=recovered / installation_cost * 100,
        net_roi_percentage=(recovered - installation_cost) / installation_cost * 100,
    )


def calculate_self_consumption_ratio(
    generation_kwh: float, solar_consumption_kwh: float
) -> float | None:
    if generation_kwh < 0 or solar_consumption_kwh < 0:
        raise ValueError("energy values cannot be negative")
    return None if generation_kwh == 0 else solar_consumption_kwh / generation_kwh


def calculate_export_ratio(generation_kwh: float, exports_kwh: float) -> float | None:
    if generation_kwh < 0 or exports_kwh < 0:
        raise ValueError("energy values cannot be negative")
    return None if generation_kwh == 0 else exports_kwh / generation_kwh


def find_historical_payback_month(
    installation_cost: float, history: list[MonthlySolarRecord]
) -> date | None:
    if installation_cost == 0:
        return history[0].month if history else None
    cumulative = 0.0
    for record in sorted(history, key=lambda item: item.month):
        cumulative += calculate_monthly_cashflow(record)
        if cumulative >= installation_cost:
            return record.month
    return None
