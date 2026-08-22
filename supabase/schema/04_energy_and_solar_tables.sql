create table energy_readings (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  meter_id uuid references meters(id) on delete set null,
  interval_start timestamptz not null,
  interval_end timestamptz not null,
  consumption_kwh numeric not null default 0 check (consumption_kwh >= 0),
  solar_generation_kwh numeric not null default 0 check (solar_generation_kwh >= 0),
  grid_import_kwh numeric not null default 0 check (grid_import_kwh >= 0),
  grid_export_kwh numeric not null default 0 check (grid_export_kwh >= 0),
  battery_soc_pct numeric check (battery_soc_pct is null or battery_soc_pct between 0 and 100),
  source energy_reading_source not null default 'manual',
  created_at timestamptz not null default now(),
  constraint energy_readings_interval_check check (interval_end > interval_start)
);

create unique index energy_readings_property_meter_interval_uidx
  on energy_readings(property_id, meter_id, interval_start, interval_end, source) nulls not distinct;
create index energy_readings_property_interval_idx on energy_readings(property_id, interval_start desc);
create index energy_readings_meter_interval_idx on energy_readings(meter_id, interval_start desc);

create table energy_tariffs (
  id uuid primary key default gen_random_uuid(),
  property_id uuid references properties(id) on delete cascade,
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
  image_path text,
  image_source text,
  roof_area_m2 numeric check (roof_area_m2 is null or roof_area_m2 >= 0),
  usable_roof_area_m2 numeric not null check (usable_roof_area_m2 >= 0),
  estimated_panel_count integer not null check (estimated_panel_count >= 0),
  estimated_system_kw numeric not null check (estimated_system_kw >= 0),
  estimated_annual_generation_kwh numeric not null check (estimated_annual_generation_kwh >= 0),
  estimated_installation_cost numeric not null check (estimated_installation_cost >= 0),
  estimated_annual_savings numeric not null,
  estimated_payback_years numeric not null,
  estimated_roi_pct numeric not null,
  estimated_carbon_reduction_kg_year numeric not null,
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

