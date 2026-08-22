from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.analytics import analyse_history, build_seasonal_profile
from app.models import AnalysisRequest


def test_missing_consumption_is_derived(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["history"][0].pop("solar_consumed_by_tenant_kwh")
    result = analyse_history(AnalysisRequest.model_validate(payload))
    month = result.monthly_history[0]
    assert month.solar_consumed_by_tenant_kwh == 330
    assert month.solar_consumption_source == "derived"
    assert "DERIVED_SOLAR_CONSUMPTION" in {warning.code for warning in result.warnings}


def test_zero_generation_and_usage_do_not_divide_by_zero(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["history"] = [
        {
            "month": "2025-07-01",
            "total_usage_kwh": 0,
            "solar_generation_kwh": 0,
            "solar_exported_kwh": 0,
            "tenant_revenue_dollars": 0,
            "export_revenue_dollars": 0,
        }
    ]
    result = analyse_history(AnalysisRequest.model_validate(payload))
    assert result.historical_performance.self_consumption_ratio is None
    assert result.revenue_metrics.revenue_per_generated_kwh_dollars is None


def test_history_is_sorted_and_gaps_are_reported(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["history"][1]["month"] = "2025-09-01"
    payload["history"].reverse()
    result = analyse_history(AnalysisRequest.model_validate(payload))
    assert [item.month for item in result.monthly_history] == ["2025-07", "2025-09"]
    assert "MISSING_MONTHS" in {warning.code for warning in result.warnings}


def test_duplicate_months_are_rejected(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["history"][1]["month"] = payload["history"][0]["month"]
    with pytest.raises(ValidationError, match="duplicate"):
        AnalysisRequest.model_validate(payload)


def test_export_greater_than_generation_is_rejected(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["history"][0]["solar_exported_kwh"] = 541
    with pytest.raises(ValidationError, match="cannot exceed"):
        AnalysisRequest.model_validate(payload)


def test_small_meter_difference_warns_but_is_accepted(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["history"][0]["solar_consumed_by_tenant_kwh"] = 334
    result = analyse_history(AnalysisRequest.model_validate(payload))
    assert "METER_TOLERANCE_APPLIED" in {warning.code for warning in result.warnings}


def test_meter_difference_beyond_tolerance_is_rejected(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["history"][0]["solar_consumed_by_tenant_kwh"] = 340
    with pytest.raises(ValidationError, match="meter tolerance"):
        AnalysisRequest.model_validate(payload)


def test_seasonal_profile_uses_matching_calendar_months(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    january = deepcopy(payload["history"][0])
    january.update(
        {
            "month": "2026-01-01",
            "solar_generation_kwh": 1000,
            "solar_consumed_by_tenant_kwh": 600,
            "solar_exported_kwh": 400,
        }
    )
    payload["history"] = [january]
    request = AnalysisRequest.model_validate(payload)
    assert build_seasonal_profile(request.history).by_month[1].generation_kwh == 1000


def test_export_opportunity_is_explicitly_theoretical(valid_payload: dict) -> None:
    payload = deepcopy(valid_payload)
    payload["revenue_assumptions"] = {"potential_tenant_rate_cents_per_kwh": 25}
    result = analyse_history(AnalysisRequest.model_validate(payload))
    assert result.export_opportunity is not None
    assert "theoretical" in result.export_opportunity.qualification.lower()
