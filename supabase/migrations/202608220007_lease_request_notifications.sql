do $$
begin
  if exists (
    select 1
    from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    where t.typname = 'lease_request_status'
      and e.enumlabel = 'rejected'
  ) and not exists (
    select 1
    from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    where t.typname = 'lease_request_status'
      and e.enumlabel = 'declined'
  ) then
    alter type lease_request_status rename value 'rejected' to 'declined';
  end if;
end $$;

alter table lease_requests
  add column if not exists landlord_user_id uuid references auth.users(id) on delete set null,
  add column if not exists requested_move_out_date date,
  add column if not exists proposed_move_in_date date,
  add column if not exists target_property_id uuid references properties(id) on delete set null,
  add column if not exists status_history jsonb not null default '[]'::jsonb;

do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'lease_requests'
      and column_name = 'reviewed_by'
  ) and not exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'lease_requests'
      and column_name = 'reviewed_by_user_id'
  ) then
    alter table lease_requests rename column reviewed_by to reviewed_by_user_id;
  end if;
end $$;

create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  recipient_user_id uuid references auth.users(id) on delete cascade,
  recipient_role property_member_role not null,
  property_id uuid references properties(id) on delete cascade,
  entity_type text not null,
  entity_id uuid not null,
  title text not null,
  message text not null,
  status text not null default 'unread' check (status in ('unread', 'read')),
  created_at timestamptz not null default now(),
  read_at timestamptz
);

do $$
begin
  if not exists (
    select 1 from pg_trigger
    where tgname = 'audit_notifications'
  ) then
    create trigger audit_notifications after insert or update or delete on notifications
      for each row execute function audit_row_change();
  end if;
end $$;

alter table notifications enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'notifications'
      and policyname = 'notifications_select_recipient'
  ) then
    create policy notifications_select_recipient on notifications for select using (
      recipient_user_id = auth.uid()
      or (property_id is not null and has_property_role(property_id, array[recipient_role]::property_member_role[]))
    );
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'notifications'
      and policyname = 'notifications_update_recipient_read'
  ) then
    create policy notifications_update_recipient_read on notifications
      for update using (recipient_user_id = auth.uid())
      with check (recipient_user_id = auth.uid());
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public'
      and tablename = 'notifications'
      and policyname = 'notifications_insert_members'
  ) then
    create policy notifications_insert_members on notifications
      for insert with check (
        property_id is null
        or has_property_role(property_id, array['tenant', 'landlord', 'agent']::property_member_role[])
      );
  end if;
end $$;
