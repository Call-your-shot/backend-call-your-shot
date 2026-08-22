-- Green-credit rewards and curated project allocations.
-- One verified tenant-consumed solar kWh creates 1,000,000 microcredits by default.

alter table energy_readings
  add column if not exists solar_consumed_by_tenant_kwh numeric
    check (solar_consumed_by_tenant_kwh is null or solar_consumed_by_tenant_kwh >= 0),
  add column if not exists battery_charge_kwh numeric not null default 0
    check (battery_charge_kwh >= 0),
  add column if not exists battery_discharge_kwh numeric not null default 0
    check (battery_discharge_kwh >= 0),
  add column if not exists finalized_at timestamptz;

alter table energy_readings
  drop constraint if exists energy_readings_solar_consumption_check;

alter table energy_readings
  add constraint energy_readings_solar_consumption_check check (
    solar_consumed_by_tenant_kwh is null
    or (
      solar_consumed_by_tenant_kwh <= consumption_kwh + 0.001
      and solar_consumed_by_tenant_kwh <= solar_generation_kwh + 0.001
    )
  );

do $$ begin
  create type green_credit_account_status as enum ('active', 'suspended', 'closed');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type green_credit_entry_type as enum ('earn', 'allocate', 'refund', 'adjustment');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type green_project_status as enum ('draft', 'open', 'funded', 'active', 'completed', 'cancelled');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type green_allocation_status as enum ('confirmed', 'refunded');
exception when duplicate_object then null;
end $$;

create table green_credit_programs (
  id uuid primary key default gen_random_uuid(),
  property_id uuid not null references properties(id) on delete cascade,
  name text not null,
  version integer not null check (version > 0),
  credits_per_kwh_microcredits bigint not null default 1000000
    check (credits_per_kwh_microcredits > 0),
  tenant_share_bps integer not null default 7000
    check (tenant_share_bps between 0 and 10000),
  owner_share_bps integer not null default 3000
    check (owner_share_bps between 0 and 10000),
  enabled boolean not null default true,
  effective_from timestamptz not null,
  effective_to timestamptz,
  created_at timestamptz not null default now(),
  constraint green_credit_program_share_check
    check (tenant_share_bps + owner_share_bps = 10000),
  constraint green_credit_program_period_check
    check (effective_to is null or effective_to > effective_from),
  unique (property_id, version)
);

create index green_credit_program_property_period_idx
  on green_credit_programs(property_id, effective_from desc);

create table green_credit_accounts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  status green_credit_account_status not null default 'active',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table green_projects (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  description text not null,
  category text not null,
  location text,
  image_path text,
  target_microcredits bigint not null check (target_microcredits > 0),
  funded_microcredits bigint not null default 0 check (funded_microcredits >= 0),
  minimum_allocation_microcredits bigint not null default 1000000
    check (minimum_allocation_microcredits > 0),
  status green_project_status not null default 'draft',
  impact_unit text not null,
  expected_impact numeric check (expected_impact is null or expected_impact >= 0),
  verification_method text not null,
  opens_at timestamptz,
  closes_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint green_project_period_check
    check (closes_at is null or opens_at is null or closes_at > opens_at),
  constraint green_project_funding_check
    check (funded_microcredits <= target_microcredits)
);

create table green_project_allocations (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references green_projects(id) on delete restrict,
  account_id uuid not null references green_credit_accounts(id) on delete restrict,
  user_id uuid not null references auth.users(id) on delete restrict,
  requested_microcredits bigint not null check (requested_microcredits > 0),
  allocated_microcredits bigint not null check (allocated_microcredits > 0),
  status green_allocation_status not null default 'confirmed',
  idempotency_key text not null check (length(idempotency_key) between 8 and 200),
  allocated_at timestamptz not null default now(),
  refunded_at timestamptz,
  unique (account_id, idempotency_key)
);

create index green_project_allocations_project_idx
  on green_project_allocations(project_id, allocated_at desc);
create index green_project_allocations_user_idx
  on green_project_allocations(user_id, allocated_at desc);

create table green_credit_ledger_entries (
  id uuid primary key default gen_random_uuid(),
  account_id uuid not null references green_credit_accounts(id) on delete restrict,
  entry_type green_credit_entry_type not null,
  amount_microcredits bigint not null check (amount_microcredits <> 0),
  property_id uuid references properties(id) on delete restrict,
  program_id uuid references green_credit_programs(id) on delete restrict,
  source_energy_reading_id uuid references energy_readings(id) on delete restrict,
  project_id uuid references green_projects(id) on delete restrict,
  allocation_id uuid references green_project_allocations(id) on delete restrict,
  source_solar_kwh numeric check (source_solar_kwh is null or source_solar_kwh >= 0),
  beneficiary_role property_member_role,
  description text not null,
  metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null,
  created_at timestamptz not null default now(),
  constraint green_credit_entry_shape_check check (
    (entry_type = 'earn' and amount_microcredits > 0 and source_energy_reading_id is not null)
    or (entry_type = 'allocate' and amount_microcredits < 0 and allocation_id is not null)
    or entry_type in ('refund', 'adjustment')
  )
);

create unique index green_credit_earn_once_idx
  on green_credit_ledger_entries(account_id, source_energy_reading_id, entry_type)
  where entry_type = 'earn';
create unique index green_credit_allocation_entry_idx
  on green_credit_ledger_entries(allocation_id)
  where allocation_id is not null and entry_type = 'allocate';
create index green_credit_ledger_account_created_idx
  on green_credit_ledger_entries(account_id, created_at desc, id desc);

create or replace view green_credit_wallets with (security_invoker = true) as
select
  account.id as account_id,
  account.user_id,
  account.status,
  coalesce(sum(entry.amount_microcredits), 0)::bigint as available_microcredits,
  coalesce(sum(entry.amount_microcredits) filter (where entry.amount_microcredits > 0), 0)::bigint
    as lifetime_earned_microcredits,
  coalesce(sum(-entry.amount_microcredits) filter (where entry.entry_type = 'allocate'), 0)::bigint
    as lifetime_allocated_microcredits,
  account.created_at,
  account.updated_at
from green_credit_accounts account
left join green_credit_ledger_entries entry on entry.account_id = account.id
group by account.id;

create or replace view green_project_funding with (security_invoker = true) as
select
  project.*,
  greatest(project.target_microcredits - project.funded_microcredits, 0)::bigint
    as remaining_microcredits
from green_projects project;

create trigger green_credit_accounts_updated_at
  before update on green_credit_accounts
  for each row execute function set_updated_at();
create trigger green_projects_updated_at
  before update on green_projects
  for each row execute function set_updated_at();

alter table green_credit_programs enable row level security;
alter table green_credit_accounts enable row level security;
alter table green_projects enable row level security;
alter table green_project_allocations enable row level security;
alter table green_credit_ledger_entries enable row level security;

create policy green_credit_programs_read_members on green_credit_programs
  for select using (is_property_member(property_id));
create policy green_credit_accounts_read_self on green_credit_accounts
  for select using (user_id = auth.uid());
create policy green_projects_read_authenticated on green_projects
  for select using (auth.uid() is not null and status <> 'draft');
create policy green_allocations_read_self on green_project_allocations
  for select using (user_id = auth.uid());
create policy green_ledger_read_self on green_credit_ledger_entries
  for select using (
    exists (
      select 1 from green_credit_accounts account
      where account.id = green_credit_ledger_entries.account_id
        and account.user_id = auth.uid()
    )
  );

create or replace function accrue_green_credits(
  target_property_id uuid,
  period_start timestamptz,
  period_end timestamptz
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  reading_record record;
  program_record green_credit_programs%rowtype;
  member_record record;
  member_count integer;
  member_index integer;
  total_microcredits bigint;
  role_microcredits bigint;
  member_microcredits bigint;
  tenant_issued bigint := 0;
  owner_issued bigint := 0;
  unissued bigint := 0;
  inserted_count integer := 0;
  processed_readings integer := 0;
  skipped_readings integer := 0;
  account_uuid uuid;
  inserted_rows integer;
begin
  if period_end <= period_start then
    raise exception 'period_end must be after period_start' using errcode = '22023';
  end if;

  for reading_record in
    select * from energy_readings
    where property_id = target_property_id
      and interval_start >= period_start
      and interval_start < period_end
      and finalized_at is not null
      and solar_consumed_by_tenant_kwh is not null
      and solar_consumed_by_tenant_kwh > 0
    order by interval_start, id
  loop
    select * into program_record
    from green_credit_programs
    where property_id = target_property_id
      and enabled
      and effective_from <= reading_record.interval_start
      and (effective_to is null or effective_to > reading_record.interval_start)
    order by version desc
    limit 1;

    if not found then
      skipped_readings := skipped_readings + 1;
      continue;
    end if;

    total_microcredits := round(
      reading_record.solar_consumed_by_tenant_kwh
      * program_record.credits_per_kwh_microcredits
    );
    if total_microcredits <= 0 then
      skipped_readings := skipped_readings + 1;
      continue;
    end if;

    processed_readings := processed_readings + 1;

    for member_record in
      select role_name, user_id, row_number() over (partition by role_name order by user_id) as role_index
      from (
        select role::text as role_name, user_id
        from property_memberships
        where property_id = target_property_id
          and role in ('tenant', 'landlord')
          and status = 'active'
          and (starts_at is null or starts_at <= reading_record.interval_start)
          and (ends_at is null or ends_at > reading_record.interval_start)
      ) members
      order by role_name, user_id
    loop
      select count(*) into member_count
      from property_memberships
      where property_id = target_property_id
        and role::text = member_record.role_name
        and status = 'active'
        and (starts_at is null or starts_at <= reading_record.interval_start)
        and (ends_at is null or ends_at > reading_record.interval_start);

      if member_record.role_name = 'tenant' then
        role_microcredits := floor(total_microcredits * program_record.tenant_share_bps / 10000.0);
      else
        role_microcredits := total_microcredits
          - floor(total_microcredits * program_record.tenant_share_bps / 10000.0);
      end if;

      member_index := member_record.role_index;
      member_microcredits := floor(role_microcredits::numeric / member_count);
      if member_index <= (role_microcredits % member_count) then
        member_microcredits := member_microcredits + 1;
      end if;
      if member_microcredits <= 0 then
        continue;
      end if;

      insert into green_credit_accounts(user_id)
      values (member_record.user_id)
      on conflict (user_id) do nothing;
      select id into account_uuid from green_credit_accounts where user_id = member_record.user_id;

      insert into green_credit_ledger_entries (
        account_id, entry_type, amount_microcredits, property_id, program_id,
        source_energy_reading_id, source_solar_kwh, beneficiary_role,
        description, occurred_at
      ) values (
        account_uuid, 'earn', member_microcredits, target_property_id, program_record.id,
        reading_record.id, reading_record.solar_consumed_by_tenant_kwh,
        member_record.role_name::property_member_role,
        'Green credits earned from verified tenant-consumed solar energy',
        reading_record.interval_end
      ) on conflict do nothing;
      get diagnostics inserted_rows = row_count;
      inserted_count := inserted_count + inserted_rows;
      if inserted_rows = 1 and member_record.role_name = 'tenant' then
        tenant_issued := tenant_issued + member_microcredits;
      elsif inserted_rows = 1 then
        owner_issued := owner_issued + member_microcredits;
      end if;
    end loop;

    select count(*) into member_count
    from property_memberships
    where property_id = target_property_id and role = 'tenant' and status = 'active'
      and (starts_at is null or starts_at <= reading_record.interval_start)
      and (ends_at is null or ends_at > reading_record.interval_start);
    if member_count = 0 then
      unissued := unissued + floor(total_microcredits * program_record.tenant_share_bps / 10000.0);
    end if;

    select count(*) into member_count
    from property_memberships
    where property_id = target_property_id and role = 'landlord' and status = 'active'
      and (starts_at is null or starts_at <= reading_record.interval_start)
      and (ends_at is null or ends_at > reading_record.interval_start);
    if member_count = 0 then
      unissued := unissued + total_microcredits
        - floor(total_microcredits * program_record.tenant_share_bps / 10000.0);
    end if;
  end loop;

  return jsonb_build_object(
    'processed_readings', processed_readings,
    'skipped_readings', skipped_readings,
    'ledger_entries_created', inserted_count,
    'tenant_issued_microcredits', tenant_issued,
    'owner_issued_microcredits', owner_issued,
    'unissued_microcredits', unissued
  );
end;
$$;

create or replace function allocate_green_credits(
  target_project_id uuid,
  requested_microcredits bigint,
  request_idempotency_key text
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  caller_id uuid := auth.uid();
  account_record green_credit_accounts%rowtype;
  project_record green_projects%rowtype;
  existing_allocation green_project_allocations%rowtype;
  available_balance bigint;
  funded bigint;
  remaining bigint;
  allocated bigint;
  allocation_uuid uuid;
begin
  if caller_id is null then
    raise exception 'Authentication is required' using errcode = '28000';
  end if;
  if requested_microcredits <= 0 then
    raise exception 'requested_microcredits must be positive' using errcode = '22023';
  end if;
  if length(request_idempotency_key) < 8 or length(request_idempotency_key) > 200 then
    raise exception 'idempotency key must contain 8 to 200 characters' using errcode = '22023';
  end if;

  select * into account_record from green_credit_accounts
  where user_id = caller_id for update;
  if not found then
    raise exception 'Green-credit account not found' using errcode = 'P0002';
  end if;
  if account_record.status <> 'active' then
    raise exception 'Green-credit account is not active' using errcode = 'P0001';
  end if;

  select * into existing_allocation from green_project_allocations
  where account_id = account_record.id and idempotency_key = request_idempotency_key;
  if found then
    if existing_allocation.project_id <> target_project_id
      or existing_allocation.requested_microcredits <> requested_microcredits then
      raise exception 'Idempotency key was already used for a different request' using errcode = '23505';
    end if;
    select coalesce(sum(amount_microcredits), 0)::bigint into available_balance
      from green_credit_ledger_entries where account_id = account_record.id;
    return jsonb_build_object(
      'allocation_id', existing_allocation.id,
      'requested_microcredits', existing_allocation.requested_microcredits,
      'allocated_microcredits', existing_allocation.allocated_microcredits,
      'partial', existing_allocation.allocated_microcredits < existing_allocation.requested_microcredits,
      'available_balance_microcredits', available_balance,
      'idempotent_replay', true
    );
  end if;

  select * into project_record from green_projects
  where id = target_project_id for update;
  if not found then
    raise exception 'Green project not found' using errcode = 'P0002';
  end if;
  if project_record.status <> 'open'
    or (project_record.opens_at is not null and project_record.opens_at > now())
    or (project_record.closes_at is not null and project_record.closes_at <= now()) then
    raise exception 'Green project is not open for allocations' using errcode = 'P0001';
  end if;

  funded := project_record.funded_microcredits;
  remaining := greatest(project_record.target_microcredits - funded, 0);
  if remaining = 0 then
    raise exception 'Green project is fully funded' using errcode = 'P0001';
  end if;

  allocated := least(requested_microcredits, remaining);
  if allocated < project_record.minimum_allocation_microcredits and allocated <> remaining then
    raise exception 'Allocation is below the project minimum' using errcode = '22023';
  end if;

  select coalesce(sum(amount_microcredits), 0)::bigint into available_balance
  from green_credit_ledger_entries where account_id = account_record.id;
  if available_balance < allocated then
    raise exception 'Insufficient green-credit balance' using errcode = 'P0001';
  end if;

  insert into green_project_allocations (
    project_id, account_id, user_id, requested_microcredits,
    allocated_microcredits, idempotency_key
  ) values (
    target_project_id, account_record.id, caller_id, requested_microcredits,
    allocated, request_idempotency_key
  ) returning id into allocation_uuid;

  insert into green_credit_ledger_entries (
    account_id, entry_type, amount_microcredits, project_id, allocation_id,
    description, occurred_at
  ) values (
    account_record.id, 'allocate', -allocated, target_project_id, allocation_uuid,
    'Green credits allocated to a curated project', now()
  );

  update green_projects
  set funded_microcredits = funded_microcredits + allocated,
      status = case when allocated = remaining then 'funded' else status end
  where id = target_project_id;

  return jsonb_build_object(
    'allocation_id', allocation_uuid,
    'requested_microcredits', requested_microcredits,
    'allocated_microcredits', allocated,
    'partial', allocated < requested_microcredits,
    'available_balance_microcredits', available_balance - allocated,
    'project_remaining_microcredits', remaining - allocated,
    'project_status', case when allocated = remaining then 'funded' else 'open' end,
    'idempotent_replay', false
  );
end;
$$;

revoke all on function accrue_green_credits(uuid, timestamptz, timestamptz) from public, anon, authenticated;
grant execute on function accrue_green_credits(uuid, timestamptz, timestamptz) to service_role;
revoke all on function allocate_green_credits(uuid, bigint, text) from public, anon;
grant execute on function allocate_green_credits(uuid, bigint, text) to authenticated;

grant select on green_credit_wallets to authenticated;
grant select on green_project_funding to authenticated;
grant select on green_credit_programs, green_credit_accounts, green_projects,
  green_project_allocations, green_credit_ledger_entries to authenticated;
