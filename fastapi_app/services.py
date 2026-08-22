from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from .data import BATTERY, TARIFF


def money(value: float) -> float:
    return round(value + 1e-9, 2)


def build_readings(hours: int = 24) -> list[dict]:
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = now - timedelta(hours=hours)
    capacity_kwh = float(BATTERY["usable_capacity_kwh"])
    reserve_kwh = capacity_kwh * (float(BATTERY["reserve_pct"]) / 100)
    battery_kwh = capacity_kwh * (float(BATTERY["soc_pct"]) / 100)
    readings: list[dict] = []

    for index in range(hours):
        interval_start = start + timedelta(hours=index)
        hour = interval_start.hour
        daylight = max(0.0, math.sin((hour - 6) / 12 * math.pi))
        consumption = 1.15 + (0.75 if 17 <= hour <= 21 else 0.0) + (0.25 if 6 <= hour <= 8 else 0.0)
        solar = daylight * 3.4
        net = consumption - solar
        grid_import = 0.0
        grid_export = 0.0
        battery_charge = 0.0
        battery_discharge = 0.0

        if net > 0:
            available = max(0.0, battery_kwh - reserve_kwh)
            battery_discharge = min(available, net, float(BATTERY["max_discharge_kw"]))
            battery_kwh -= battery_discharge
            grid_import = net - battery_discharge
        else:
            surplus = abs(net)
            charge_room = capacity_kwh - battery_kwh
            battery_charge = min(charge_room, surplus, float(BATTERY["max_charge_kw"]))
            battery_kwh += battery_charge
            grid_export = surplus - battery_charge

        readings.append(
            {
                "interval_start": interval_start.isoformat(),
                "interval_end": (interval_start + timedelta(hours=1)).isoformat(),
                "consumption_kwh": money(consumption),
                "solar_generation_kwh": money(solar),
                "grid_import_kwh": money(grid_import),
                "grid_export_kwh": money(grid_export),
                "battery_charge_kwh": money(battery_charge),
                "battery_discharge_kwh": money(battery_discharge),
                "battery_soc_pct": money((battery_kwh / capacity_kwh) * 100),
                "source": "fastapi_demo",
            }
        )

    return readings


def battery_snapshot(readings: list[dict]) -> dict:
    latest = readings[-1]
    status = "idle"
    if latest["battery_charge_kwh"] > 0:
        status = "charging"
    elif latest["battery_discharge_kwh"] > 0:
        status = "discharging"
    elif latest["battery_soc_pct"] <= float(BATTERY["reserve_pct"]):
        status = "reserve"

    return {
        **BATTERY,
        "soc_pct": latest["battery_soc_pct"],
        "status": status,
        "last_seen_at": latest["interval_end"],
    }


def dashboard_summary(granularity: str) -> dict:
    readings = build_readings()
    totals = {
        "consumptionKwh": money(sum(row["consumption_kwh"] for row in readings)),
        "solarGenerationKwh": money(sum(row["solar_generation_kwh"] for row in readings)),
        "gridImportKwh": money(sum(row["grid_import_kwh"] for row in readings)),
        "gridExportKwh": money(sum(row["grid_export_kwh"] for row in readings)),
        "batteryChargeKwh": money(sum(row["battery_charge_kwh"] for row in readings)),
        "batteryDischargeKwh": money(sum(row["battery_discharge_kwh"] for row in readings)),
        "batterySocPct": readings[-1]["battery_soc_pct"],
    }
    grid_rate_per_kwh = float(TARIFF["grid_rate_cents_per_kwh"]) / 100
    estimated_cost = money(totals["gridImportKwh"] * grid_rate_per_kwh - totals["gridExportKwh"] * float(TARIFF["feed_in_rate_per_kwh"]))
    estimated_savings = money(
        max(0, totals["solarGenerationKwh"] - totals["gridExportKwh"]) * grid_rate_per_kwh
        + totals["gridExportKwh"] * float(TARIFF["feed_in_rate_per_kwh"])
    )

    return {
        "period": {
            "from": readings[0]["interval_start"],
            "to": readings[-1]["interval_end"],
            "granularity": granularity,
        },
        "energy": totals,
        "battery": battery_snapshot(readings),
        "financial": {
            "estimatedCost": estimated_cost,
            "estimatedSavings": estimated_savings,
            "currency": TARIFF["currency"],
            "gridRateCentsPerKwh": TARIFF["grid_rate_cents_per_kwh"],
        },
        "sustainability": {"carbonAvoidedKg": money(totals["solarGenerationKwh"] * 0.68)},
        "units": {"energy": "kWh", "currency": "AUD", "carbon": "kgCO2e"},
        "series": readings,
    }
