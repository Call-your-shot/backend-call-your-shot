create table energy_readings (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  meter_id uuid references meters(id) on delete set null,
  interval_start timestamptz not null,
  interval_end timestamptz not null,
  consumption_kwh numeric not null default 0 check (consumption_kwh >= 0),
  solar_generation_kwh numeric not null default 0 check (solar_generation_kwh >= 0),
  solar_consumed_by_tenant_kwh numeric not null default 0 check (solar_consumed_by_tenant_kwh >= 0),
  grid_import_kwh numeric not null default 0 check (grid_import_kwh >= 0),
  grid_export_kwh numeric not null default 0 check (grid_export_kwh >= 0),
  battery_charge_kwh numeric not null default 0 check (battery_charge_kwh >= 0),
  battery_discharge_kwh numeric not null default 0 check (battery_discharge_kwh >= 0),
  battery_soc_pct numeric check (battery_soc_pct is null or battery_soc_pct between 0 and 100),
  interval_minutes integer not null default 60 check (interval_minutes > 0),
  quality_status reading_quality_status not null default 'raw',
  raw_packet_id uuid references raw_iot_telemetry_packets(id) on delete set null,
  source energy_reading_source not null default 'manual',
  created_at timestamptz not null default now(),
  constraint energy_readings_interval_check check (interval_end > interval_start)
);

create unique index energy_readings_property_meter_interval_uidx
  on energy_readings(property_id, meter_id, interval_start, interval_end, source) nulls not distinct;
create index energy_readings_property_interval_idx on energy_readings(property_id, interval_start desc);
create index energy_readings_meter_interval_idx on energy_readings(meter_id, interval_start desc);
create index energy_readings_raw_packet_idx on energy_readings(raw_packet_id);

create table energy_tariffs (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  name text not null,
  usage_rate_per_kwh numeric not null check (usage_rate_per_kwh >= 0),
  grid_rate_cents_per_kwh numeric not null default 34 check (grid_rate_cents_per_kwh >= 0),
  feed_in_rate_per_kwh numeric not null default 0 check (feed_in_rate_per_kwh >= 0),
  daily_supply_charge numeric not null default 0 check (daily_supply_charge >= 0),
  currency text not null default 'AUD',
  valid_from timestamptz not null,
  valid_to timestamptz,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  constraint energy_tariffs_validity_check check (valid_to is null or valid_to > valid_from)
);

create index energy_tariffs_property_validity_idx on energy_tariffs(property_id, valid_from desc);

create table price_adjustments (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  previous_tariff_id uuid references energy_tariffs(id) on delete set null,
  proposed_usage_rate numeric check (proposed_usage_rate is null or proposed_usage_rate >= 0),
  proposed_feed_in_rate numeric check (proposed_feed_in_rate is null or proposed_feed_in_rate >= 0),
  proposed_daily_charge numeric check (proposed_daily_charge is null or proposed_daily_charge >= 0),
  fixed_solar_rate_cents_per_kwh numeric check (fixed_solar_rate_cents_per_kwh is null or fixed_solar_rate_cents_per_kwh >= 0),
  reason text,
  effective_from timestamptz not null,
  status adjustment_status not null default 'draft',
  created_by uuid not null references auth.users(id) on delete restrict,
  approved_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table bills (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  tenant_user_id uuid references auth.users(id) on delete set null,
  tariff_id uuid not null references energy_tariffs(id) on delete restrict,
  period_start timestamptz not null,
  period_end timestamptz not null,
  consumption_kwh numeric not null default 0 check (consumption_kwh >= 0),
  solar_generation_kwh numeric not null default 0 check (solar_generation_kwh >= 0),
  grid_import_kwh numeric not null default 0 check (grid_import_kwh >= 0),
  grid_export_kwh numeric not null default 0 check (grid_export_kwh >= 0),
  usage_cost numeric not null default 0,
  supply_cost numeric not null default 0,
  solar_credit numeric not null default 0,
  total_amount numeric not null default 0,
  estimated_savings numeric not null default 0,
  carbon_avoided_kg numeric,
  status bill_status not null default 'draft',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint bills_period_check check (period_end > period_start)
);

create index bills_property_period_idx on bills(property_id, period_start desc);
create index bills_tenant_idx on bills(tenant_user_id);

create table solar_assessments (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  provider text,
  image_path text,
  image_source text,
  latitude numeric,
  longitude numeric,
  imagery_date date,
  imagery_quality text,
  roof_area_m2 numeric check (roof_area_m2 is null or roof_area_m2 >= 0),
  usable_roof_area_m2 numeric not null check (usable_roof_area_m2 >= 0),
  panel_count integer check (panel_count is null or panel_count >= 0),
  panel_wattage numeric check (panel_wattage is null or panel_wattage >= 0),
  estimated_panel_count integer not null check (estimated_panel_count >= 0),
  estimated_system_kw numeric not null check (estimated_system_kw >= 0),
  estimated_annual_generation_kwh numeric not null check (estimated_annual_generation_kwh >= 0),
  estimated_installation_cost numeric not null check (estimated_installation_cost >= 0),
  estimated_annual_savings numeric not null,
  estimated_payback_years numeric not null,
  estimated_roi_pct numeric not null,
  estimated_carbon_reduction_kg_year numeric not null,
  monthly_generation_weights numeric[] not null default array[]::numeric[],
  generation_uncertainty_percentage numeric check (generation_uncertainty_percentage is null or generation_uncertainty_percentage >= 0),
  roof_segments_json jsonb not null default '{}'::jsonb,
  selected_configuration_json jsonb not null default '{}'::jsonb,
  assumptions jsonb not null,
  status solar_assessment_status not null default 'draft',
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table solar_products (
  id uuid primary key default gen_random_uuid(),
  manufacturer text not null,
  model text not null,
  panel_power_w numeric not null check (panel_power_w > 0),
  panel_area_m2 numeric not null check (panel_area_m2 > 0),
  unit_cost numeric check (unit_cost is null or unit_cost >= 0),
  warranty_years integer check (warranty_years is null or warranty_years >= 0),
  efficiency_pct numeric check (efficiency_pct is null or efficiency_pct between 0 and 100),
  metadata jsonb not null default '{}'::jsonb,
  active boolean not null default true,
  created_at timestamptz not null default now()
);

create table solar_installations (
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

create table pricing_contracts (
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

create table interval_pricing_results (
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

create table cashflow_events (
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

create table roi_analysis_runs (
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

create index solar_installations_property_idx on solar_installations(property_id);
create index pricing_contracts_property_tenant_idx on pricing_contracts(property_id, tenant_id, effective_from desc);
create index interval_pricing_results_contract_interval_idx on interval_pricing_results(pricing_contract_id, interval_start desc);
create index cashflow_events_installation_time_idx on cashflow_events(installation_id, occurred_at desc);
create index roi_analysis_runs_installation_created_idx on roi_analysis_runs(installation_id, created_at desc);
