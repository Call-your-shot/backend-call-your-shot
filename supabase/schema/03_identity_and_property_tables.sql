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
  primary_address_id uuid,
  -- Legacy cache fields kept for API compatibility. Canonical address data lives
  -- in countries, localities, and property_addresses.
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

create table countries (
  code text primary key,
  name text not null unique,
  created_at timestamptz not null default now(),
  constraint countries_code_format_check check (code = upper(code) and length(code) between 2 and 3)
);

create table localities (
  id uuid primary key default gen_random_uuid(),
  country_code text not null references countries(code) on delete restrict,
  state text not null,
  suburb text not null,
  postcode text not null,
  created_at timestamptz not null default now(),
  constraint localities_unique_location unique (country_code, state, suburb, postcode)
);

create table property_addresses (
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
  add constraint properties_primary_address_fk foreign key (primary_address_id) references property_addresses(id) on delete set null;

create index localities_country_state_idx on localities(country_code, state, suburb);
create index property_addresses_locality_idx on property_addresses(locality_id);
create index properties_primary_address_idx on properties(primary_address_id);

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
