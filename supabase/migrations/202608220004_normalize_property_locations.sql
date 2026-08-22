-- Normalize property location data while preserving existing denormalized columns
-- as compatibility/cache fields for current application code.

create table if not exists countries (
  code text primary key,
  name text not null unique,
  created_at timestamptz not null default now(),
  constraint countries_code_format_check check (code = upper(code) and length(code) between 2 and 3)
);

create table if not exists localities (
  id uuid primary key default gen_random_uuid(),
  country_code text not null references countries(code) on delete restrict,
  state text not null,
  suburb text not null,
  postcode text not null,
  created_at timestamptz not null default now(),
  constraint localities_unique_location unique (country_code, state, suburb, postcode)
);

create table if not exists property_addresses (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null unique references properties(id) on delete cascade,
  locality_id uuid not null references localities(id) on delete restrict,
  address_line_1 text not null,
  address_line_2 text,
  latitude numeric,
  longitude numeric,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table properties
  add column if not exists primary_address_id uuid references property_addresses(id) on delete set null;

insert into countries(code, name)
select distinct
  case
    when upper(country) in ('AU', 'AUS', 'AUSTRALIA') then 'AU'
    else left(upper(country), 3)
  end as code,
  case
    when upper(country) in ('AU', 'AUS') then 'Australia'
    else country
  end as name
from properties
where country is not null
on conflict (code) do update set name = excluded.name;

insert into localities(country_code, state, suburb, postcode)
select distinct
  case
    when upper(country) in ('AU', 'AUS', 'AUSTRALIA') then 'AU'
    else left(upper(country), 3)
  end as country_code,
  state,
  suburb,
  postcode
from properties
on conflict (country_code, state, suburb, postcode) do nothing;

insert into property_addresses(property_id, locality_id, address_line_1, address_line_2, latitude, longitude)
select
  p.id,
  l.id,
  p.address_line_1,
  p.address_line_2,
  p.latitude,
  p.longitude
from properties p
join localities l
  on l.country_code = case
    when upper(p.country) in ('AU', 'AUS', 'AUSTRALIA') then 'AU'
    else left(upper(p.country), 3)
  end
  and l.state = p.state
  and l.suburb = p.suburb
  and l.postcode = p.postcode
on conflict (property_id) do update set
  locality_id = excluded.locality_id,
  address_line_1 = excluded.address_line_1,
  address_line_2 = excluded.address_line_2,
  latitude = excluded.latitude,
  longitude = excluded.longitude,
  updated_at = now();

update properties p
set primary_address_id = pa.id
from property_addresses pa
where pa.property_id = p.id
  and p.primary_address_id is distinct from pa.id;

create index if not exists localities_country_state_idx on localities(country_code, state, suburb);
create index if not exists property_addresses_locality_idx on property_addresses(locality_id);
create index if not exists properties_primary_address_idx on properties(primary_address_id);

drop trigger if exists property_addresses_updated_at on property_addresses;
create trigger property_addresses_updated_at before update on property_addresses for each row execute function set_updated_at();

alter table energy_tariffs
  add constraint energy_tariffs_property_required check (property_id is not null) not valid;

alter table raw_grid_meter_telemetry
  alter column packet_id set not null;
alter table raw_solar_inverter_telemetry
  alter column packet_id set not null;
alter table raw_battery_bms_telemetry
  alter column packet_id set not null;

create unique index if not exists raw_grid_meter_telemetry_packet_uidx on raw_grid_meter_telemetry(packet_id);
create unique index if not exists raw_solar_inverter_telemetry_packet_uidx on raw_solar_inverter_telemetry(packet_id);
create unique index if not exists raw_battery_bms_telemetry_packet_uidx on raw_battery_bms_telemetry(packet_id);

alter table countries enable row level security;
alter table localities enable row level security;
alter table property_addresses enable row level security;

drop policy if exists countries_read_authenticated on countries;
create policy countries_read_authenticated on countries for select using (auth.uid() is not null);

drop policy if exists localities_read_authenticated on localities;
create policy localities_read_authenticated on localities for select using (auth.uid() is not null);

drop policy if exists property_addresses_select_members on property_addresses;
create policy property_addresses_select_members on property_addresses for select using (is_property_member(property_id));

drop policy if exists property_addresses_manage_managers on property_addresses;
create policy property_addresses_manage_managers on property_addresses
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));
