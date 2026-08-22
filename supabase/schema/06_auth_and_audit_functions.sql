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

