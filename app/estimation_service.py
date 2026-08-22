import re
from calendar import month_name, monthrange
from datetime import date, datetime
from typing import Optional, Union

from fastapi import HTTPException, status
from .schemas import AnnualEstimationRequest, AnnualEstimationResponse, SurveyFormData


def parse_hours_bucket(hours_str: Optional[str]) -> float:
    """
    Parses hoursBucket strings:
    - "0-2" -> 1.0
    - "2-4" -> 3.0
    - "4-6" -> 5.0
    - "6+" -> 7.0
    - "0" or "none" or None -> 0.0
    """
    if not hours_str or hours_str.lower() in ("0", "none", "null"):
        return 0.0

    hours_str = hours_str.strip()

    # Range format: "X-Y"
    range_match = re.match(r"^(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$", hours_str)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return (low + high) / 2.0

    # Plus format: "X+"
    plus_match = re.match(r"^(\d+(?:\.\d+)?)\s*\+$", hours_str)
    if plus_match:
        return float(plus_match.group(1)) + 1.0

    # Single number format
    try:
        return float(hours_str)
    except ValueError:
        return 0.0


def parse_billing_date(value: Union[str, date]) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def calculate_annual_energy_estimation(request: AnnualEstimationRequest) -> AnnualEstimationResponse:
    form: SurveyFormData = request.form_data

    # Parse billing period start and end dates
    try:
        start_date = parse_billing_date(form.billing_period_start)
        end_date = parse_billing_date(form.billing_period_end)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format in billingPeriodStart or billingPeriodEnd. Expected YYYY-MM-DD: {str(exc)}",
        ) from exc

    bill_days = (end_date - start_date).days
    if bill_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="billingPeriodEnd must be after billingPeriodStart",
        )

    # Base daily usage from bill
    base_daily_kwh = form.bill_usage_kwh / float(bill_days)

    # Daytime occupancy changes the share of demand that can overlap solar.
    # It must never reduce an observed electricity bill or total annual load.
    daytime_ratio_map = {
        "most": 0.55,
        "sometimes": 0.40,
        "rarely": 0.25,
    }
    daytime_usage_ratio = daytime_ratio_map.get(
        form.home_during_day or "sometimes", 0.40
    )

    # Appliance hourly loads
    cooling_hrs = (
        parse_hours_bucket(form.cooling_hours)
        if form.cooling_not_used_this_month
        else 0.0
    )
    cooling_addition = cooling_hrs * 1.5

    heating_hrs = (
        parse_hours_bucket(form.heating_hours)
        if form.heating_not_used_this_month
        else 0.0
    )
    heating_addition = heating_hrs * 1.5

    pool_hrs = (
        parse_hours_bucket(form.pool_hours)
        if form.pool_not_used_this_month
        else 0.0
    )
    pool_addition = pool_hrs * 1.2

    ev_hrs = (
        parse_hours_bucket(form.ev_hours) if form.ev_not_used_this_month else 0.0
    )
    ev_addition = ev_hrs * 3.5

    hot_water_hrs = (
        parse_hours_bucket(form.hot_water_hours)
        if form.hot_water_not_used_this_month
        else 0.0
    )
    hot_water_addition = hot_water_hrs * 1.5

    year_round_addition = pool_addition + ev_addition + hot_water_addition

    observed_bill_days_by_month = {month: 0 for month in range(1, 13)}
    cursor = start_date
    while cursor < end_date:
        observed_bill_days_by_month[cursor.month] += 1
        cursor = date.fromordinal(cursor.toordinal() + 1)

    observed_monthly = {
        record.month.month: record.usage_kwh
        for record in form.observed_monthly_usage
    }
    monthly_results = []

    for month_idx in range(1, 13):
        days = monthrange(2025, month_idx)[1]
        if month_idx in observed_monthly:
            monthly_kwh = observed_monthly[month_idx]
            source = "observed_bill"
            monthly_results.append(
                {
                    "calendar_month": month_idx,
                    "month_name": month_name[month_idx],
                    "usage_kwh": round(monthly_kwh, 1),
                    "daytime_usage_ratio": daytime_usage_ratio,
                    "source": source,
                }
            )
            continue

        extra_daily_kwh = year_round_addition
        if month_idx in (1, 2, 12):
            extra_daily_kwh += cooling_addition
        elif month_idx in (6, 7, 8):
            extra_daily_kwh += heating_addition
        elif month_idx == 5:
            extra_daily_kwh += heating_addition * 0.33
        elif month_idx == 11:
            extra_daily_kwh += cooling_addition * 0.33

        # The bill already contains real usage for the days it covers. Survey
        # additions only apply to the remainder of that representative month.
        derived_days = max(0, days - observed_bill_days_by_month[month_idx])
        monthly_kwh = base_daily_kwh * days + extra_daily_kwh * derived_days
        source = (
            "bill_period_derived"
            if observed_bill_days_by_month[month_idx] > 0
            else "survey_derived"
        )
        monthly_results.append(
            {
                "calendar_month": month_idx,
                "month_name": month_name[month_idx],
                "usage_kwh": round(monthly_kwh, 1),
                "daytime_usage_ratio": daytime_usage_ratio,
                "source": source,
            }
        )

    total_annual_kwh = sum(month["usage_kwh"] for month in monthly_results)
    observed_count = len(observed_monthly)
    if observed_count == 12:
        profile_source = "observed_bills"
        data_quality = "high"
    elif observed_count > 0:
        profile_source = "observed_and_survey_derived"
        data_quality = "medium"
    else:
        profile_source = "single_bill_and_survey"
        data_quality = "low"

    return AnnualEstimationResponse(
        estimated_annual_usage_kwh=round(total_annual_kwh, 1),
        monthly_usage=monthly_results,
        observed_month_count=observed_count or 1,
        profile_source=profile_source,
        data_quality=data_quality,
    )
