do $$ begin
  create type reading_quality_status as enum ('raw', 'validated', 'estimated', 'corrected', 'missing');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type solar_installation_status as enum ('planned', 'installed', 'commissioned', 'decommissioned');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type pricing_mode as enum ('fixed', 'dynamic');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type cashflow_event_category as enum (
    'tenant_solar_revenue',
    'export_revenue',
    'maintenance',
    'repair',
    'replacement',
    'rebate',
    'adjustment'
  );
exception when duplicate_object then null;
end $$;

do $$ begin
  create type cashflow_event_status as enum ('pending', 'posted', 'void');
exception when duplicate_object then null;
end $$;

alter table raw_iot_telemetry_packets
  add column if not exists property_id uuid references properties(id) on delete set null,
  add column if not exists provider text not null default 'mock_iot',
  add column if not exists external_packet_id text;

alter table raw_grid_meter_telemetry
  add column if not exists property_id uuid references properties(id) on delete set null,
  add column if not exists meter_id uuid references meters(id) on delete set null,
  add column if not exists provider text not null default 'mock_iot',
  add column if not exists external_packet_id text;

alter table raw_solar_inverter_telemetry
  add column if not exists property_id uuid references properties(id) on delete set null,
  add column if not exists inverter_id uuid,
  add column if not exists provider text not null default 'mock_iot',
  add column if not exists external_packet_id text;

alter table raw_battery_bms_telemetry
  add column if not exists property_id uuid references properties(id) on delete set null,
  add column if not exists battery_id uuid,
  add column if not exists provider text not null default 'mock_iot',
  add column if not exists external_packet_id text;

create unique index if not exists raw_iot_telemetry_packets_provider_external_uidx
  on raw_iot_telemetry_packets(provider, external_packet_id)
  where external_packet_id is not null;
create unique index if not exists raw_grid_meter_telemetry_provider_device_ts_uidx
  on raw_grid_meter_telemetry(provider, device_id, timestamp);
create unique index if not exists raw_solar_inverter_telemetry_provider_device_ts_uidx
  on raw_solar_inverter_telemetry(provider, device_id, timestamp);
create unique index if not exists raw_battery_bms_telemetry_provider_device_ts_uidx
  on raw_battery_bms_telemetry(provider, device_id, timestamp);

alter table energy_readings
  add column if not exists solar_consumed_by_tenant_kwh numeric not null default 0 check (solar_consumed_by_tenant_kwh >= 0),
  add column if not exists battery_charge_kwh numeric not null default 0 check (battery_charge_kwh >= 0),
  add column if not exists battery_discharge_kwh numeric not null default 0 check (battery_discharge_kwh >= 0),
  add column if not exists interval_minutes integer not null default 60 check (interval_minutes > 0),
  add column if not exists quality_status reading_quality_status not null default 'raw',
  add column if not exists raw_packet_id uuid references raw_iot_telemetry_packets(id) on delete set null;

create index if not exists energy_readings_raw_packet_idx on energy_readings(raw_packet_id);

alter table solar_assessments
  add column if not exists provider text,
  add column if not exists latitude numeric,
  add column if not exists longitude numeric,
  add column if not exists imagery_date date,
  add column if not exists imagery_quality text,
  add column if not exists panel_count integer check (panel_count is null or panel_count >= 0),
  add column if not exists panel_wattage numeric check (panel_wattage is null or panel_wattage >= 0),
  add column if not exists monthly_generation_weights numeric[] not null default array[]::numeric[],
  add column if not exists generation_uncertainty_percentage numeric check (generation_uncertainty_percentage is null or generation_uncertainty_percentage >= 0),
  add column if not exists roof_segments_json jsonb not null default '{}'::jsonb,
  add column if not exists selected_configuration_json jsonb not null default '{}'::jsonb;

create table if not exists solar_installations (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  solar_assessment_id uuid references solar_assessments(id) on delete set null,
  installation_date date,
  commissioned_at timestamptz,
  installed_capacity_kw numeric not null check (installed_capacity_kw >= 0),
  gross_installation_cost_cents bigint not null check (gross_installation_cost_cents >= 0),
  stc_benefit_cents bigint not null default 0 check (stc_benefit_cents >= 0),
  other_rebates_cents bigint not null default 0 check (other_rebates_cents >= 0),
  currency text not null default 'AUD',
  status solar_installation_status not null default 'planned',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint solar_installations_rebate_check check (stc_benefit_cents + other_rebates_cents <= gross_installation_cost_cents)
);

create table if not exists pricing_contracts (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  tenant_id uuid not null references auth.users(id) on delete cascade,
  pricing_mode pricing_mode not null default 'dynamic',
  alpha_min numeric not null default 0.40 check (alpha_min between 0 and 1),
  alpha_max numeric not null default 0.75 check (alpha_max between 0 and 1),
  discount_sensitivity numeric not null default 0.50 check (discount_sensitivity > 0),
  fixed_solar_rate_cents_per_kwh numeric check (fixed_solar_rate_cents_per_kwh is null or fixed_solar_rate_cents_per_kwh >= 0),
  effective_from timestamptz not null,
  effective_to timestamptz,
  model_version text not null default 'v1',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint pricing_contracts_alpha_check check (alpha_min <= alpha_max),
  constraint pricing_contracts_effective_check check (effective_to is null or effective_to > effective_from)
);

create table if not exists interval_pricing_results (
  id uuid primary key default gen_random_uuid(),
  energy_reading_id uuid not null references energy_readings(id) on delete cascade,
  pricing_contract_id uuid not null references pricing_contracts(id) on delete cascade,
  interval_start timestamptz not null,
  tenant_usage_kwh numeric not null check (tenant_usage_kwh >= 0),
  tenant_solar_consumption_kwh numeric not null check (tenant_solar_consumption_kwh >= 0),
  grid_usage_kwh numeric not null check (grid_usage_kwh >= 0),
  grid_rate_cents_per_kwh numeric not null check (grid_rate_cents_per_kwh >= 0),
  export_rate_cents_per_kwh numeric not null check (export_rate_cents_per_kwh >= 0),
  tenant_solar_rate_cents_per_kwh numeric not null check (tenant_solar_rate_cents_per_kwh >= 0),
  alpha numeric check (alpha is null or alpha between 0 and 1),
  tenant_solar_revenue_cents bigint not null default 0,
  actual_export_revenue_cents bigint not null default 0,
  tenant_savings_cents bigint not null default 0,
  pricing_model_version text not null default 'v1',
  created_at timestamptz not null default now(),
  constraint interval_pricing_results_reading_contract_uidx unique (energy_reading_id, pricing_contract_id)
);

create table if not exists cashflow_events (
  id uuid primary key default gen_random_uuid(),
  installation_id uuid not null references solar_installations(id) on delete cascade,
  occurred_at timestamptz not null,
  category cashflow_event_category not null,
  amount_cents bigint not null,
  status cashflow_event_status not null default 'posted',
  source text,
  source_reference_id uuid,
  created_at timestamptz not null default now()
);

create table if not exists roi_analysis_runs (
  id uuid primary key default gen_random_uuid(),
  installation_id uuid not null references solar_installations(id) on delete cascade,
  forecast_source text not null,
  as_of_date date not null,
  model_version text not null,
  random_seed bigint,
  request_snapshot_json jsonb not null default '{}'::jsonb,
  result_summary_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists solar_installations_property_idx on solar_installations(property_id);
create index if not exists pricing_contracts_property_tenant_idx on pricing_contracts(property_id, tenant_id, effective_from desc);
create index if not exists interval_pricing_results_contract_interval_idx on interval_pricing_results(pricing_contract_id, interval_start desc);
create index if not exists cashflow_events_installation_time_idx on cashflow_events(installation_id, occurred_at desc);
create index if not exists roi_analysis_runs_installation_created_idx on roi_analysis_runs(installation_id, created_at desc);

drop trigger if exists solar_installations_updated_at on solar_installations;
create trigger solar_installations_updated_at before update on solar_installations for each row execute function set_updated_at();
drop trigger if exists pricing_contracts_updated_at on pricing_contracts;
create trigger pricing_contracts_updated_at before update on pricing_contracts for each row execute function set_updated_at();

alter table solar_installations enable row level security;
alter table pricing_contracts enable row level security;
alter table interval_pricing_results enable row level security;
alter table cashflow_events enable row level security;
alter table roi_analysis_runs enable row level security;

create policy solar_installations_select_members on solar_installations for select using (is_property_member(property_id));
create policy solar_installations_manage_managers on solar_installations
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy pricing_contracts_select_allowed on pricing_contracts for select using (
  has_property_role(property_id, array['landlord', 'agent']::property_member_role[])
  or (tenant_id = auth.uid() and is_property_member(property_id))
);
create policy pricing_contracts_manage_managers on pricing_contracts
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy interval_pricing_results_select_allowed on interval_pricing_results for select using (
  exists (
    select 1 from pricing_contracts pc
    where pc.id = interval_pricing_results.pricing_contract_id
      and (
        has_property_role(pc.property_id, array['landlord', 'agent']::property_member_role[])
        or (pc.tenant_id = auth.uid() and is_property_member(pc.property_id))
      )
  )
);

create policy cashflow_events_select_managers on cashflow_events for select using (
  exists (
    select 1 from solar_installations si
    where si.id = cashflow_events.installation_id
      and has_property_role(si.property_id, array['landlord', 'agent']::property_member_role[])
  )
);

create policy roi_analysis_runs_select_managers on roi_analysis_runs for select using (
  exists (
    select 1 from solar_installations si
    where si.id = roi_analysis_runs.installation_id
      and has_property_role(si.property_id, array['landlord', 'agent']::property_member_role[])
  )
);
