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
