alter table profiles enable row level security;
alter table properties enable row level security;
alter table countries enable row level security;
alter table localities enable row level security;
alter table property_addresses enable row level security;
alter table property_memberships enable row level security;
alter table meters enable row level security;
alter table energy_readings enable row level security;
alter table energy_tariffs enable row level security;
alter table price_adjustments enable row level security;
alter table bills enable row level security;
alter table solar_assessments enable row level security;
alter table solar_products enable row level security;
alter table solar_installations enable row level security;
alter table pricing_contracts enable row level security;
alter table interval_pricing_results enable row level security;
alter table cashflow_events enable row level security;
alter table roi_analysis_runs enable row level security;
alter table lease_requests enable row level security;
alter table notifications enable row level security;
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

create policy countries_read_authenticated on countries for select using (auth.uid() is not null);
create policy localities_read_authenticated on localities for select using (auth.uid() is not null);
create policy property_addresses_select_members on property_addresses for select using (is_property_member(property_id));
create policy property_addresses_manage_managers on property_addresses
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

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

create policy solar_installations_select_members on solar_installations for select using (is_property_member(property_id));
create policy solar_installations_manage_managers on solar_installations
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy pricing_contracts_select_allowed on pricing_contracts for select using (
  has_property_role(property_id, array['landlord', 'agent']::property_member_role[])
  or (tenant_id = auth.uid() and is_property_member(property_id))
);
create policy pricing_contracts_manage_managers on pricing_contracts
  for all using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy interval_pricing_results_select_allowed on interval_pricing_results for select using (
  exists (
    select 1 from pricing_contracts pc
    where pc.id = interval_pricing_results.pricing_contract_id
      and (
        has_property_role(pc.property_id, array['landlord', 'agent']::property_member_role[])
        or (pc.tenant_id = auth.uid() and is_property_member(pc.property_id))
      )
  )
);

create policy cashflow_events_select_managers on cashflow_events for select using (
  exists (
    select 1 from solar_installations si
    where si.id = cashflow_events.installation_id
      and has_property_role(si.property_id, array['landlord', 'agent']::property_member_role[])
  )
);

create policy roi_analysis_runs_select_managers on roi_analysis_runs for select using (
  exists (
    select 1 from solar_installations si
    where si.id = roi_analysis_runs.installation_id
      and has_property_role(si.property_id, array['landlord', 'agent']::property_member_role[])
  )
);

create policy lease_requests_select_allowed on lease_requests for select using (
  has_property_role(property_id, array['landlord', 'agent']::property_member_role[])
  or is_request_tenant(property_id, tenant_user_id)
);
create policy lease_requests_insert_tenant on lease_requests
  for insert with check (is_request_tenant(property_id, tenant_user_id));
create policy lease_requests_update_reviewers on lease_requests
  for update using (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]))
  with check (has_property_role(property_id, array['landlord', 'agent']::property_member_role[]));

create policy notifications_select_recipient on notifications for select using (
  recipient_user_id = auth.uid()
  or (property_id is not null and has_property_role(property_id, array[recipient_role]::property_member_role[]))
);
create policy notifications_update_recipient_read on notifications
  for update using (recipient_user_id = auth.uid())
  with check (recipient_user_id = auth.uid());
create policy notifications_insert_members on notifications
  for insert with check (
    property_id is null
    or has_property_role(property_id, array['tenant', 'landlord', 'agent']::property_member_role[])
  );

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
