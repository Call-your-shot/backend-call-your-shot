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

