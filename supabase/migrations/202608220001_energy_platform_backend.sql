create extension if not exists "pgcrypto";

create type property_member_role as enum ('tenant', 'landlord', 'agent');
create type membership_status as enum ('invited', 'active', 'inactive');
create type meter_type as enum ('electricity', 'solar', 'hybrid');
create type meter_status as enum ('active', 'inactive');
create type energy_reading_source as enum ('mock', 'meter_api', 'manual', 'simulation');
create type adjustment_status as enum ('draft', 'pending', 'approved', 'rejected', 'applied');
create type bill_status as enum ('draft', 'issued', 'paid', 'overdue', 'cancelled');
create type solar_assessment_status as enum ('draft', 'completed', 'review_required');
create type lease_request_status as enum ('submitted', 'under_review', 'approved', 'rejected', 'cancelled');
create type proposal_type as enum ('solar', 'energy_price', 'ppa', 'lease');
create type proposal_status as enum ('draft', 'sent', 'accepted', 'rejected', 'expired');
create type contract_type as enum ('ppa', 'lease_amendment', 'energy_agreement');
create type contract_status as enum ('draft', 'review', 'sent', 'signed', 'cancelled');
create type energy_control_mode as enum ('automatic', 'self_consumption', 'backup', 'manual');
create type control_command_status as enum ('queued', 'sent', 'acknowledged', 'failed', 'cancelled');

create or replace function set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null,
  phone text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table properties (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address_line_1 text not null,
  address_line_2 text,
  suburb text not null,
  state text not null,
  postcode text not null,
  country text not null default 'Australia',
  latitude numeric,
  longitude numeric,
  timezone text not null default 'Australia/Sydney',
  roof_area_m2 numeric check (roof_area_m2 is null or roof_area_m2 >= 0),
  usable_roof_area_m2 numeric check (usable_roof_area_m2 is null or usable_roof_area_m2 >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table property_memberships (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role property_member_role not null,
  status membership_status not null default 'active',
  starts_at timestamptz,
  ends_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint property_membership_time_check check (ends_at is null or starts_at is null or ends_at > starts_at)
);

create unique index property_memberships_active_role_uidx
  on property_memberships(property_id, user_id, role)
  where status in ('invited', 'active');
create index property_memberships_user_idx on property_memberships(user_id, status);
create index property_memberships_property_role_idx on property_memberships(property_id, role, status);

create table meters (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  external_meter_id text,
  meter_type meter_type not null,
  provider text not null,
  status meter_status not null default 'active',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create unique index meters_external_provider_uidx on meters(provider, external_meter_id) where external_meter_id is not null;
create index meters_property_idx on meters(property_id);

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

create table lease_requests (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  tenant_user_id uuid not null references auth.users(id) on delete cascade,
  request_type text not null,
  message text not null,
  status lease_request_status not null default 'submitted',
  reviewed_by uuid references auth.users(id) on delete set null,
  review_notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table proposals (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  proposal_type proposal_type not null,
  title text not null,
  description text not null,
  proposed_by uuid not null references auth.users(id) on delete restrict,
  recipient_user_id uuid references auth.users(id) on delete set null,
  status proposal_status not null default 'draft',
  financial_summary jsonb not null default '{}'::jsonb,
  terms jsonb not null default '{}'::jsonb,
  valid_until timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table contracts (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  proposal_id uuid references proposals(id) on delete set null,
  contract_type contract_type not null,
  tenant_user_id uuid references auth.users(id) on delete set null,
  landlord_user_id uuid references auth.users(id) on delete set null,
  agent_user_id uuid references auth.users(id) on delete set null,
  status contract_status not null default 'draft',
  effective_from date,
  effective_to date,
  terms jsonb not null default '{}'::jsonb,
  document_path text,
  created_by uuid not null references auth.users(id) on delete restrict,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint contracts_effective_check check (effective_to is null or effective_from is null or effective_to > effective_from)
);

create table energy_control_settings (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null unique references properties(id) on delete cascade,
  mode energy_control_mode not null default 'automatic',
  battery_min_reserve_pct numeric not null default 20 check (battery_min_reserve_pct between 0 and 100),
  allow_grid_export boolean not null default true,
  max_grid_import_kw numeric check (max_grid_import_kw is null or max_grid_import_kw >= 0),
  updated_by uuid references auth.users(id) on delete set null,
  updated_at timestamptz not null default now()
);

create table energy_control_commands (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  command_type text not null,
  payload jsonb not null default '{}'::jsonb,
  status control_command_status not null default 'queued',
  requested_by uuid not null references auth.users(id) on delete restrict,
  requested_at timestamptz not null default now(),
  processed_at timestamptz,
  response jsonb
);

create table audit_logs (
  id uuid primary key default gen_random_uuid(),
  property_id uuid references properties(id) on delete set null,
  actor_user_id uuid references auth.users(id) on delete set null,
  action text not null,
  entity_type text not null,
  entity_id uuid,
  before_data jsonb,
  after_data jsonb,
  created_at timestamptz not null default now()
);

create index audit_logs_property_created_idx on audit_logs(property_id, created_at desc);
create index audit_logs_entity_idx on audit_logs(entity_type, entity_id);

create or replace function current_user_id()
returns uuid
language sql
stable
as $$
  select auth.uid()
$$;

create or replace function is_property_member(target_property_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from property_memberships pm
    where pm.property_id = target_property_id
      and pm.user_id = auth.uid()
      and pm.status = 'active'
      and (pm.starts_at is null or pm.starts_at <= now())
      and (pm.ends_at is null or pm.ends_at > now())
  )
$$;

create or replace function has_property_role(target_property_id uuid, allowed_roles property_member_role[])
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from property_memberships pm
    where pm.property_id = target_property_id
      and pm.user_id = auth.uid()
      and pm.role = any(allowed_roles)
      and pm.status = 'active'
      and (pm.starts_at is null or pm.starts_at <= now())
      and (pm.ends_at is null or pm.ends_at > now())
  )
$$;

create or replace function is_request_tenant(target_property_id uuid, tenant_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select auth.uid() = tenant_id and has_property_role(target_property_id, array['tenant']::property_member_role[])
$$;

create or replace function audit_row_change()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  target_property_id uuid;
  target_entity_id uuid;
begin
  target_property_id := coalesce(new.property_id, old.property_id);
  target_entity_id := coalesce(new.id, old.id);
  insert into audit_logs(property_id, actor_user_id, action, entity_type, entity_id, before_data, after_data)
  values (
    target_property_id,
    auth.uid(),
    tg_op,
    tg_table_name,
    target_entity_id,
    case when tg_op in ('UPDATE', 'DELETE') then to_jsonb(old) else null end,
    case when tg_op in ('INSERT', 'UPDATE') then to_jsonb(new) else null end
  );
  return coalesce(new, old);
end;
$$;

create trigger profiles_updated_at before update on profiles for each row execute function set_updated_at();
create trigger properties_updated_at before update on properties for each row execute function set_updated_at();
create trigger property_memberships_updated_at before update on property_memberships for each row execute function set_updated_at();
create trigger price_adjustments_updated_at before update on price_adjustments for each row execute function set_updated_at();
create trigger bills_updated_at before update on bills for each row execute function set_updated_at();
create trigger solar_assessments_updated_at before update on solar_assessments for each row execute function set_updated_at();
create trigger lease_requests_updated_at before update on lease_requests for each row execute function set_updated_at();
create trigger proposals_updated_at before update on proposals for each row execute function set_updated_at();
create trigger contracts_updated_at before update on contracts for each row execute function set_updated_at();

create trigger audit_energy_tariffs after insert or update or delete on energy_tariffs for each row execute function audit_row_change();
create trigger audit_price_adjustments after insert or update or delete on price_adjustments for each row execute function audit_row_change();
create trigger audit_lease_requests after insert or update or delete on lease_requests for each row execute function audit_row_change();
create trigger audit_contracts after insert or update or delete on contracts for each row execute function audit_row_change();
create trigger audit_energy_control_settings after insert or update or delete on energy_control_settings for each row execute function audit_row_change();
create trigger audit_energy_control_commands after insert or update or delete on energy_control_commands for each row execute function audit_row_change();

alter table profiles enable row level security;
alter table properties enable row level security;
alter table property_memberships enable row level security;
alter table meters enable row level security;
alter table energy_readings enable row level security;
alter table energy_tariffs enable row level security;
alter table price_adjustments enable row level security;
alter table bills enable row level security;
alter table solar_assessments enable row level security;
alter table solar_products enable row level security;
alter table lease_requests enable row level security;
alter table proposals enable row level security;
alter table contracts enable row level security;
alter table energy_control_settings enable row level security;
alter table energy_control_commands enable row level security;
alter table audit_logs enable row level security;

create policy profiles_select_self_or_shared_property on profiles
  for select using (
    id = auth.uid()
    or exists (
      select 1
      from property_memberships mine
      join property_memberships theirs on theirs.property_id = mine.property_id
      where mine.user_id = auth.uid()
        and mine.status = 'active'
        and theirs.user_id = profiles.id
        and theirs.status = 'active'
    )
  );
create policy profiles_update_self on profiles for update using (id = auth.uid()) with check (id = auth.uid());
create policy profiles_insert_self on profiles for insert with check (id = auth.uid());

create policy properties_select_members on properties for select using (is_property_member(id));
create policy properties_insert_managers on properties for insert with check (auth.uid() is not null);
create policy properties_update_managers on properties
  for update using (has_property_role(id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(id, array['landlord', 'agent']::property_member_role[]));

create policy memberships_select_related on property_memberships
  for select using (user_id = auth.uid() or is_property_member(property_id));
create policy memberships_manage_landlords on property_memberships
  for all using (has_property_role(property_id, array['landlord']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord']::property_member_role[]));

create policy meters_select_members on meters for select using (is_property_member(property_id));
create policy meters_manage_managers on meters
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy energy_readings_select_members on energy_readings for select using (is_property_member(property_id));
create policy energy_readings_insert_managers on energy_readings
  for insert with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy tariffs_select_members on energy_tariffs for select using (property_id is null or is_property_member(property_id));
create policy tariffs_manage_managers on energy_tariffs
  for all using (property_id is not null and has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (property_id is not null and has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy price_adjustments_select_members on price_adjustments for select using (is_property_member(property_id));
create policy price_adjustments_manage_managers on price_adjustments
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy bills_select_members on bills for select using (
  has_property_role(property_id, array['landlord', 'agent']::property_member_role[])
  or is_request_tenant(property_id, tenant_user_id)
);
create policy bills_manage_managers on bills
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy solar_assessments_select_members on solar_assessments for select using (is_property_member(property_id));
create policy solar_assessments_manage_managers on solar_assessments
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy solar_products_read_authenticated on solar_products for select using (auth.uid() is not null and active);

create policy lease_requests_select_allowed on lease_requests for select using (
  has_property_role(property_id, array['landlord', 'agent']::property_member_role[])
  or is_request_tenant(property_id, tenant_user_id)
);
create policy lease_requests_insert_tenant on lease_requests
  for insert with check (is_request_tenant(property_id, tenant_user_id));
create policy lease_requests_update_reviewers on lease_requests
  for update using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy proposals_select_allowed on proposals for select using (
  has_property_role(property_id, array['landlord', 'agent']::property_member_role[])
  or (recipient_user_id = auth.uid() and is_property_member(property_id))
);
create policy proposals_manage_managers on proposals
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy contracts_select_allowed on contracts for select using (
  has_property_role(property_id, array['landlord', 'agent']::property_member_role[])
  or tenant_user_id = auth.uid()
);
create policy contracts_manage_managers on contracts
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy controls_select_members on energy_control_settings for select using (is_property_member(property_id));
create policy controls_manage_managers on energy_control_settings
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));
create policy commands_select_members on energy_control_commands for select using (is_property_member(property_id));
create policy commands_insert_managers on energy_control_commands
  for insert with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));
create policy commands_update_managers on energy_control_commands
  for update using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy audit_logs_select_managers on audit_logs
  for select using (property_id is not null and has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

insert into storage.buckets (id, name, public)
values ('property-images', 'property-images', false), ('contracts', 'contracts', false)
on conflict (id) do update set public = excluded.public;

create policy property_images_members_read on storage.objects
  for select using (
    bucket_id = 'property-images'
    and exists (
      select 1 from properties p
      where p.id::text = split_part(name, '/', 1)
        and is_property_member(p.id)
    )
  );

create policy property_images_managers_write on storage.objects
  for insert with check (
    bucket_id = 'property-images'
    and exists (
      select 1 from properties p
      where p.id::text = split_part(name, '/', 1)
        and has_property_role(p.id, array['landlord', 'agent']::property_member_role[])
    )
  );

create policy contracts_members_read on storage.objects
  for select using (
    bucket_id = 'contracts'
    and exists (
      select 1 from properties p
      where p.id::text = split_part(name, '/', 1)
        and is_property_member(p.id)
    )
  );
