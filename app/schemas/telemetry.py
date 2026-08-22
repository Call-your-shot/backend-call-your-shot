from __future__ import annotations

from typing import Optional

from .common import ApiModel


class GridMeterTelemetry(ApiModel):
    device_id: str
    timestamp: str
    voltage_rms_v: float
    current_rms_a: float
    active_power_w: float
    reactive_power_var: float
    power_factor: float
    frequency_hz: float
    energy_import_total_kwh: float
    energy_export_total_kwh: float


class SolarInverterTelemetry(ApiModel):
    device_id: str
    timestamp: str
    pv_voltage_dc_v: float
    pv_current_dc_a: float
    pv_power_dc_w: float
    ac_power_w: float
    inverter_temp_c: float
    operating_status: str
    energy_total_generated_kwh: float


class BatteryBMSTelemetry(ApiModel):
    device_id: str
    timestamp: str
    soc_percent: float
    soh_percent: float
    pack_voltage_v: float
    pack_current_a: float
    battery_power_w: float
    cell_temp_c: float
    bms_state: str
    cycle_count: int
    energy_charged_total_kwh: float
    energy_discharged_total_kwh: float


class TelemetryPacket(ApiModel):
    timestamp: str
    grid_meter: GridMeterTelemetry
    solar_inverter: SolarInverterTelemetry
    battery_bms: BatteryBMSTelemetry


class HourlyBreakdownItem(ApiModel):
    timestamp: str
    solar_gen_kwh: float
    grid_import_kwh: float
    grid_export_kwh: float
    bat_charge_kwh: float
    bat_discharge_kwh: float
    room_load_kwh: float
    solar_self_consumed_kwh: float
    soc_percent: float
    import_rate: float
    cost_without_solar: float
    actual_cost: float
    hourly_savings: float
    co2_offset_kg: float


class DashboardAnalyticsResponse(ApiModel):
    date: str
    total_load_kwh: float
    total_solar_generated_kwh: float
    total_grid_imported_kwh: float
    total_grid_exported_kwh: float
    total_energy_saved_kwh: float
    total_money_saved_usd: float
    self_sufficiency_percent: float
    total_co2_offset_kg: float
    hourly_breakdown: list[HourlyBreakdownItem]


class IngestTelemetryResponse(ApiModel):
    status: str
    message: str
    date: str
    weather: str
    count: int
    ingested_at: str
    records: list[TelemetryPacket]


class RawTelemetryQueryResponse(ApiModel):
    date: Optional[str] = None
    count: int
    data: list[TelemetryPacket]
