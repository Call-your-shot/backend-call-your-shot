import re
from datetime import datetime
from typing import Optional

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


def calculate_annual_energy_estimation(request: AnnualEstimationRequest) -> AnnualEstimationResponse:
    form: SurveyFormData = request.form_data

    # Parse billing period start and end dates
    try:
        start_date = datetime.strptime(form.billing_period_start, "%Y-%m-%d").date()
        end_date = datetime.strptime(form.billing_period_end, "%Y-%m-%d").date()
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

    # Occupancy multiplier
    occupancy_map = {
        "most": 1.0,
        "sometimes": 0.75,
        "rarely": 0.50,
    }

    occupancy_factor = occupancy_map.get(form.home_during_day or "most", 1.0)
    adjusted_base_daily_kwh = base_daily_kwh * occupancy_factor

    # Appliance hourly loads
    cooling_hrs = parse_hours_bucket(form.cooling_hours)
    cooling_addition = cooling_hrs * 1.5

    heating_hrs = parse_hours_bucket(form.heating_hours)
    heating_addition = heating_hrs * 1.5
    hot_water_winter_penalty = 1.5

    pool_hrs = parse_hours_bucket(form.pool_hours) if not form.pool_not_used_this_month else 0.0
    pool_addition = pool_hrs * 1.2

    ev_hrs = parse_hours_bucket(form.ev_hours) if not form.ev_not_used_this_month else 0.0
    ev_addition = ev_hrs * 3.5

    year_round_addition = pool_addition + ev_addition

    # Month days in standard non-leap year (Jan=1..Dec=12)
    month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    monthly_totals: list[float] = []

    for month_idx, days in enumerate(month_days, start=1):
        if month_idx in (1, 2, 12):
            # Summer Peak: Cooling load active
            daily_load = adjusted_base_daily_kwh + cooling_addition + year_round_addition
        elif month_idx in (6, 7, 8):
            # Winter Peak: Space Heating load + Hot Water thermal load active
            daily_load = adjusted_base_daily_kwh + heating_addition + hot_water_winter_penalty + year_round_addition
        elif month_idx == 5:
            # May: Shoulder / Cool transition
            mild_heating = heating_addition * 0.33 if heating_addition > 0 else 1.5
            daily_load = adjusted_base_daily_kwh + mild_heating + year_round_addition
        elif month_idx == 11:
            # Nov: Shoulder / Warm transition
            mild_cooling = cooling_addition * 0.33 if cooling_addition > 0 else 1.5
            daily_load = adjusted_base_daily_kwh + mild_cooling + year_round_addition
        else:
            # Mar, Apr, Sep, Oct: Mild Shoulder baseline
            daily_load = adjusted_base_daily_kwh + year_round_addition

        monthly_totals.append(daily_load * days)

    total_annual_kwh = sum(monthly_totals)

    return AnnualEstimationResponse(
        estimated_annual_usage_kwh=round(total_annual_kwh, 1),
    )
