from datetime import datetime, timezone
from typing import Any

from .schemas import DashboardAnalyticsResponse, HourlyBreakdownItem
from .utils.pricing import calculate_interval_price


def get_import_rate(hour: int) -> float:
    """
    Time-of-Use Import Tariff:
    - Peak (17:00–21:00) = $0.38/kWh
    - Shoulder (07:00–17:00) = $0.24/kWh
    - Off-Peak (21:00–07:00) = $0.16/kWh
    """
    if 17 <= hour < 21:
        return 0.38
    elif 7 <= hour < 17:
        return 0.24
    else:
        return 0.16


FEED_IN_RATE = 0.07  # $0.07/kWh export tariff
EMISSIONS_FACTOR = 0.70  # 0.70 kg CO2 / kWh of solar generated


def parse_timestamp_hour(ts_str: str) -> int:
    try:
        if ts_str.endswith("Z"):
            ts_str = ts_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts_str)
        return dt.hour
    except Exception:
        return 0


def parse_timestamp(ts_str: str) -> datetime:
    value = ts_str[:-1] + "+00:00" if ts_str.endswith("Z") else ts_str
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)


def process_telemetry_timeseries(
    date_str: str,
    raw_packets: list[dict[str, Any]],
) -> DashboardAnalyticsResponse:
    breakdown_items: list[HourlyBreakdownItem] = []

    for index, curr in enumerate(raw_packets):
        if index == 0:
            prev = curr
        else:
            prev = raw_packets[index - 1]

        timestamp = curr.get("timestamp", f"{date_str}T{index:02d}:00:00Z")
        timestamp_dt = parse_timestamp(timestamp)

        # 1. Compute interval energy deltas (kWh)
        solar_gen = max(
            0.0,
            float(curr["solar_inverter"]["energy_total_generated_kwh"])
            - float(prev["solar_inverter"]["energy_total_generated_kwh"]),
        )
        grid_import = max(
            0.0,
            float(curr["grid_meter"]["energy_import_total_kwh"])
            - float(prev["grid_meter"]["energy_import_total_kwh"]),
        )
        grid_export = max(
            0.0,
            float(curr["grid_meter"]["energy_export_total_kwh"])
            - float(prev["grid_meter"]["energy_export_total_kwh"]),
        )
        bat_charge = max(
            0.0,
            float(curr["battery_bms"]["energy_charged_total_kwh"])
            - float(prev["battery_bms"]["energy_charged_total_kwh"]),
        )
        bat_discharge = max(
            0.0,
            float(curr["battery_bms"]["energy_discharged_total_kwh"])
            - float(prev["battery_bms"]["energy_discharged_total_kwh"]),
        )

        # 2. Physical room energy balance & solar self-consumed
        room_load = max(0.0, solar_gen + grid_import - grid_export - bat_charge + bat_discharge)
        solar_self_consumed = max(0.0, solar_gen - grid_export - bat_charge)

        # 3. Tariff & financial logic. The canonical dynamic-pricing engine
        # owns tariff resolution and tenant pricing; analytics only supplies
        # the physical interval energy balance.
        solar_available_for_tenant = max(0.0, solar_gen - bat_charge)
        priced = calculate_interval_price(
            usage_kwh=room_load,
            solar_available_kwh=solar_available_for_tenant,
            timestamp=timestamp_dt,
            pricing_mode="dynamic",
        )
        import_rate = priced.grid_rate_cents_per_kwh / 100
        cost_without_solar = priced.tenant_grid_cost_without_solar_dollars
        actual_cost = priced.total_charge_dollars
        hourly_savings = priced.tenant_saving_dollars
        export_revenue = grid_export * priced.export_rate_cents_per_kwh / 100
        landlord_revenue = priced.solar_charge_dollars + export_revenue
        co2_offset = solar_gen * EMISSIONS_FACTOR
        soc_pct = float(curr["battery_bms"].get("soc_percent", 0.0))

        item = HourlyBreakdownItem(
            timestamp=timestamp,
            solar_gen_kwh=round(solar_gen, 4),
            grid_import_kwh=round(grid_import, 4),
            grid_export_kwh=round(grid_export, 4),
            bat_charge_kwh=round(bat_charge, 4),
            bat_discharge_kwh=round(bat_discharge, 4),
            room_load_kwh=round(room_load, 4),
            solar_self_consumed_kwh=round(solar_self_consumed, 4),
            soc_percent=round(soc_pct, 2),
            import_rate=round(import_rate, 4),
            solar_rate_cents_per_kwh=priced.solar_rate_cents_per_kwh,
            export_rate_cents_per_kwh=priced.export_rate_cents_per_kwh,
            cost_without_solar=round(cost_without_solar, 4),
            actual_cost=round(actual_cost, 4),
            hourly_savings=round(hourly_savings, 4),
            tenant_solar_charge_dollars=priced.solar_charge_dollars,
            export_revenue_dollars=round(export_revenue, 4),
            landlord_revenue_dollars=round(landlord_revenue, 4),
            co2_offset_kg=round(co2_offset, 4),
        )
        breakdown_items.append(item)

    # 4. Aggregations across 24 hours
    total_load = sum(item.room_load_kwh for item in breakdown_items)
    total_solar = sum(item.solar_gen_kwh for item in breakdown_items)
    total_imported = sum(item.grid_import_kwh for item in breakdown_items)
    total_exported = sum(item.grid_export_kwh for item in breakdown_items)
    total_energy_saved = total_load - total_imported
    total_money_saved = sum(item.hourly_savings for item in breakdown_items)
    total_landlord_revenue = sum(item.landlord_revenue_dollars for item in breakdown_items)

    if total_load > 0:
        self_sufficiency = (total_energy_saved / total_load) * 100.0
    else:
        self_sufficiency = 0.0

    total_co2 = total_solar * EMISSIONS_FACTOR

    return DashboardAnalyticsResponse(
        date=date_str,
        total_load_kwh=round(total_load, 4),
        total_solar_generated_kwh=round(total_solar, 4),
        total_grid_imported_kwh=round(total_imported, 4),
        total_grid_exported_kwh=round(total_exported, 4),
        total_energy_saved_kwh=round(total_energy_saved, 4),
        total_money_saved_usd=round(total_money_saved, 4),
        total_tenant_savings_dollars=round(total_money_saved, 4),
        total_landlord_revenue_dollars=round(total_landlord_revenue, 4),
        self_sufficiency_percent=round(self_sufficiency, 2),
        total_co2_offset_kg=round(total_co2, 4),
        hourly_breakdown=breakdown_items,
    )
