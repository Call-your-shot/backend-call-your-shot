-- Migration: Create Raw IoT Telemetry Storage Tables

create table if not exists raw_iot_telemetry_packets (
  id uuid primary key default gen_random_uuid(),
  property_id uuid references properties(id) on delete set null,
  date date not null,
  weather text not null default 'sunny',
  timestamp timestamptz not null,
  provider text not null default 'mock_iot',
  external_packet_id text,
  raw_payload jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists raw_iot_telemetry_packets_date_idx on raw_iot_telemetry_packets(date, timestamp desc);
create index if not exists raw_iot_telemetry_packets_ts_idx on raw_iot_telemetry_packets(timestamp desc);
create unique index if not exists raw_iot_telemetry_packets_provider_external_uidx
  on raw_iot_telemetry_packets(provider, external_packet_id)
  where external_packet_id is not null;

create table if not exists raw_grid_meter_telemetry (
  id uuid primary key default gen_random_uuid(),
  packet_id uuid not null references raw_iot_telemetry_packets(id) on delete cascade,
  property_id uuid references properties(id) on delete set null,
  meter_id uuid references meters(id) on delete set null,
  provider text not null default 'mock_iot',
  external_packet_id text,
  device_id text not null,
  timestamp timestamptz not null,
  voltage_rms_v numeric not null,
  current_rms_a numeric not null,
  active_power_w numeric not null,
  reactive_power_var numeric not null,
  power_factor numeric not null,
  frequency_hz numeric not null,
  energy_import_total_kwh numeric not null,
  energy_export_total_kwh numeric not null,
  created_at timestamptz not null default now()
);

create index if not exists raw_grid_meter_telemetry_ts_idx on raw_grid_meter_telemetry(timestamp desc);
create index if not exists raw_grid_meter_telemetry_device_idx on raw_grid_meter_telemetry(device_id);
create unique index if not exists raw_grid_meter_telemetry_packet_uidx on raw_grid_meter_telemetry(packet_id);
create unique index if not exists raw_grid_meter_telemetry_provider_device_ts_uidx
  on raw_grid_meter_telemetry(provider, device_id, timestamp);

create table if not exists raw_solar_inverter_telemetry (
  id uuid primary key default gen_random_uuid(),
  packet_id uuid not null references raw_iot_telemetry_packets(id) on delete cascade,
  property_id uuid references properties(id) on delete set null,
  inverter_id uuid,
  provider text not null default 'mock_iot',
  external_packet_id text,
  device_id text not null,
  timestamp timestamptz not null,
  pv_voltage_dc_v numeric not null,
  pv_current_dc_a numeric not null,
  pv_power_dc_w numeric not null,
  ac_power_w numeric not null,
  inverter_temp_c numeric not null,
  operating_status text not null,
  energy_total_generated_kwh numeric not null,
  created_at timestamptz not null default now()
);

create index if not exists raw_solar_inverter_telemetry_ts_idx on raw_solar_inverter_telemetry(timestamp desc);
create index if not exists raw_solar_inverter_telemetry_device_idx on raw_solar_inverter_telemetry(device_id);
create unique index if not exists raw_solar_inverter_telemetry_packet_uidx on raw_solar_inverter_telemetry(packet_id);
create unique index if not exists raw_solar_inverter_telemetry_provider_device_ts_uidx
  on raw_solar_inverter_telemetry(provider, device_id, timestamp);

create table if not exists raw_battery_bms_telemetry (
  id uuid primary key default gen_random_uuid(),
  packet_id uuid not null references raw_iot_telemetry_packets(id) on delete cascade,
  property_id uuid references properties(id) on delete set null,
  battery_id uuid,
  provider text not null default 'mock_iot',
  external_packet_id text,
  device_id text not null,
  timestamp timestamptz not null,
  soc_percent numeric not null,
  soh_percent numeric not null,
  pack_voltage_v numeric not null,
  pack_current_a numeric not null,
  battery_power_w numeric not null,
  cell_temp_c numeric not null,
  bms_state text not null,
  cycle_count integer not null,
  energy_charged_total_kwh numeric not null,
  energy_discharged_total_kwh numeric not null,
  created_at timestamptz not null default now()
);

create index if not exists raw_battery_bms_telemetry_ts_idx on raw_battery_bms_telemetry(timestamp desc);
create index if not exists raw_battery_bms_telemetry_device_idx on raw_battery_bms_telemetry(device_id);
create unique index if not exists raw_battery_bms_telemetry_packet_uidx on raw_battery_bms_telemetry(packet_id);
create unique index if not exists raw_battery_bms_telemetry_provider_device_ts_uidx
  on raw_battery_bms_telemetry(provider, device_id, timestamp);
