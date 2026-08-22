from datetime import date

import pytest

from app.models import MonthlySolarRecord
from app.roi import (
    calculate_capital_recovery,
    calculate_export_ratio,
    calculate_monthly_cashflow,
    calculate_net_installation_cost,
    calculate_self_consumption_ratio,
    find_historical_payback_month,
)


def record(month: date, revenue: float, cost: float = 0) -> MonthlySolarRecord:
    return MonthlySolarRecord(
        month=month,
        total_usage_kwh=100,
        solar_generation_kwh=100,
        solar_exported_kwh=40,
        tenant_revenue_dollars=revenue,
        export_revenue_dollars=10,
        operating_cost_dollars=cost,
    )


def test_net_installation_cost_subtracts_stc_and_rebate() -> None:
    assert calculate_net_installation_cost(9000, 1500, 500) == 7000


def test_net_installation_cost_rejects_excess_rebates() -> None:
    with pytest.raises(ValueError):
        calculate_net_installation_cost(1000, 800, 300)


def test_monthly_cashflow_adds_revenue_and_subtracts_cost() -> None:
    assert calculate_monthly_cashflow(record(date(2026, 1, 1), 100, 15)) == 95


def test_capital_recovery_preserves_over_recovery_and_clamps_remaining() -> None:
    result = calculate_capital_recovery(100, [60, 60])
    assert result.recovered_dollars == 120
    assert result.remaining_dollars == 0
    assert result.capital_recovered_percentage == 120
    assert result.net_roi_percentage == 20


def test_zero_installation_cost_is_immediately_recovered() -> None:
    result = calculate_capital_recovery(0, [0])
    assert result.capital_recovered_percentage == 100
    assert result.net_roi_percentage is None


def test_ratio_functions_handle_zero_generation() -> None:
    assert calculate_self_consumption_ratio(0, 0) is None
    assert calculate_export_ratio(0, 0) is None


def test_historical_payback_returns_first_crossing_month() -> None:
    history = [
        record(date(2026, 1, 1), 50),
        record(date(2026, 2, 1), 50),
        record(date(2026, 3, 1), 50),
    ]
    assert find_historical_payback_month(110, history) == date(2026, 2, 1)
