from __future__ import annotations

import math


DEFAULT_SOLAR_ASSUMPTIONS = {
    "panelWattageW": 440,
    "panelAreaM2": 2.0,
    "usableRoofPercentage": 0.65,
    "specificAnnualYieldKwhPerKw": 1450,
    "installationCostPerKw": 1450,
    "electricityRatePerKwh": 0.34,
    "feedInRatePerKwh": 0.08,
    "selfConsumptionRatio": 0.72,
    "annualDegradationPct": 0.005,
    "analysisPeriodYears": 20,
    "gridEmissionsKgPerKwh": 0.68,
}


def rounded(value: float, places: int = 2) -> float:
    return round(value + 1e-9, places)


def estimate_solar(input_data: dict) -> dict:
    assumptions = {**DEFAULT_SOLAR_ASSUMPTIONS, **(input_data.get("assumptions") or {})}
    roof_area = float(input_data.get("roof_area_m2") or 0)
    usable_roof_area = input_data.get("usable_roof_area_m2")
    if usable_roof_area is None:
        usable_roof_area = max(0.0, roof_area) * float(assumptions["usableRoofPercentage"])

    panel_area = max(float(assumptions["panelAreaM2"]), 0.01)
    estimated_panel_count = math.floor(float(usable_roof_area) / panel_area)
    estimated_system_kw = rounded((estimated_panel_count * float(assumptions["panelWattageW"])) / 1000)
    estimated_annual_generation_kwh = rounded(estimated_system_kw * float(assumptions["specificAnnualYieldKwhPerKw"]))
    estimated_installation_cost = rounded(estimated_system_kw * float(assumptions["installationCostPerKw"]))
    self_consumed_kwh = estimated_annual_generation_kwh * float(assumptions["selfConsumptionRatio"])
    exported_kwh = estimated_annual_generation_kwh - self_consumed_kwh
    estimated_annual_savings = rounded(
        self_consumed_kwh * float(assumptions["electricityRatePerKwh"])
        + exported_kwh * float(assumptions["feedInRatePerKwh"])
    )
    estimated_payback_years = rounded(estimated_installation_cost / estimated_annual_savings) if estimated_annual_savings > 0 else 0
    lifetime_savings = estimated_annual_savings * float(assumptions["analysisPeriodYears"])
    estimated_roi_pct = (
        rounded(((lifetime_savings - estimated_installation_cost) / estimated_installation_cost) * 100)
        if estimated_installation_cost > 0
        else 0
    )

    return {
        "usable_roof_area_m2": rounded(float(usable_roof_area)),
        "estimated_panel_count": estimated_panel_count,
        "estimated_system_kw": estimated_system_kw,
        "estimated_annual_generation_kwh": estimated_annual_generation_kwh,
        "estimated_installation_cost": estimated_installation_cost,
        "estimated_annual_savings": estimated_annual_savings,
        "estimated_payback_years": estimated_payback_years,
        "estimated_roi_pct": estimated_roi_pct,
        "estimated_carbon_reduction_kg_year": rounded(
            estimated_annual_generation_kwh * float(assumptions["gridEmissionsKgPerKwh"])
        ),
        "assumptions": assumptions,
    }
