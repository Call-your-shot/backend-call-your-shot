insert into auth.users (id, email, encrypted_password, email_confirmed_at, raw_app_meta_data, raw_user_meta_data, created_at, updated_at)
values
  ('11111111-1111-4111-8111-111111111111', 'tenant@example.com', crypt('demo-password-change-me', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now()),
  ('22222222-2222-4222-8222-222222222222', 'landlord@example.com', crypt('demo-password-change-me', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now()),
  ('33333333-3333-4333-8333-333333333333', 'agent@example.com', crypt('demo-password-change-me', gen_salt('bf')), now(), '{"provider":"email","providers":["email"]}', '{}', now(), now())
on conflict (id) do nothing;

insert into profiles (id, full_name, phone)
values
  ('11111111-1111-4111-8111-111111111111', 'Tia Tenant', '+61 400 000 001'),
  ('22222222-2222-4222-8222-222222222222', 'Lana Landlord', '+61 400 000 002'),
  ('33333333-3333-4333-8333-333333333333', 'Ari Agent', '+61 400 000 003')
on conflict (id) do update set full_name = excluded.full_name, phone = excluded.phone;

insert into properties (id, name, address_line_1, suburb, state, postcode, country, latitude, longitude, timezone, roof_area_m2, usable_roof_area_m2)
values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Bellambi Solar Rental', '12 Demo Street', 'Bellambi', 'NSW', '2518', 'Australia', -34.366, 150.912, 'Australia/Sydney', 118, 76),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'Unrelated Wollongong Property', '8 Example Avenue', 'Wollongong', 'NSW', '2500', 'Australia', -34.427, 150.893, 'Australia/Sydney', 96, 61)
on conflict (id) do update set name = excluded.name;

insert into property_memberships (property_id, user_id, role, status)
values
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111', 'tenant', 'active'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '22222222-2222-4222-8222-222222222222', 'landlord', 'active'),
  ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '33333333-3333-4333-8333-333333333333', 'agent', 'active'),
  ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', '22222222-2222-4222-8222-222222222222', 'landlord', 'active')
on conflict do nothing;

insert into meters (id, property_id, external_meter_id, meter_type, provider, status, metadata)
values
  ('cccccccc-cccc-4ccc-8ccc-cccccccccccc', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'DEMO-METER-001', 'hybrid', 'mock', 'active', '{"interval":"hour"}')
on conflict (id) do nothing;

insert into energy_tariffs (id, property_id, name, usage_rate_per_kwh, grid_rate_cents_per_kwh, feed_in_rate_per_kwh, daily_supply_charge, currency, valid_from, created_by)
values
  ('dddddddd-dddd-4ddd-8ddd-dddddddddddd', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'Demo Residential Solar Tariff', 0.34, 34, 0.08, 1.12, 'AUD', now() - interval '90 days', '22222222-2222-4222-8222-222222222222')
on conflict (id) do nothing;

insert into energy_readings (
  property_id,
  meter_id,
  interval_start,
  interval_end,
  consumption_kwh,
  solar_generation_kwh,
  solar_consumed_by_tenant_kwh,
  grid_import_kwh,
  grid_export_kwh,
  battery_charge_kwh,
  battery_discharge_kwh,
  battery_soc_pct,
  source,
  finalized_at
)
select
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'::uuid,
  'cccccccc-cccc-4ccc-8ccc-cccccccccccc'::uuid,
  slot,
  slot + interval '1 hour',
  round((0.45 + case when extract(hour from slot) between 17 and 22 then 0.55 else 0.15 end)::numeric, 3),
  round((case when extract(hour from slot) between 6 and 18 then sin(((extract(hour from slot) - 6) / 12.0) * pi()) * 2.8 else 0 end)::numeric, 3),
  round(least(
    (0.45 + case when extract(hour from slot) between 17 and 22 then 0.55 else 0.15 end),
    (case when extract(hour from slot) between 6 and 18 then sin(((extract(hour from slot) - 6) / 12.0) * pi()) * 2.8 else 0 end)
  )::numeric, 3),
  round(greatest(0, (0.45 + case when extract(hour from slot) between 17 and 22 then 0.55 else 0.15 end) - (case when extract(hour from slot) between 6 and 18 then sin(((extract(hour from slot) - 6) / 12.0) * pi()) * 2.8 else 0 end) * 0.7)::numeric, 3),
  round(greatest(0, (case when extract(hour from slot) between 6 and 18 then sin(((extract(hour from slot) - 6) / 12.0) * pi()) * 2.8 else 0 end) - (0.45 + case when extract(hour from slot) between 17 and 22 then 0.55 else 0.15 end))::numeric, 3),
  0,
  0,
  round((45 + 35 * sin(extract(epoch from slot) / 86400.0))::numeric, 1),
  'mock',
  now()
from generate_series(
  date_trunc('hour', now() - interval '30 days'),
  date_trunc('hour', now() - interval '1 hour'),
  interval '1 hour'
) as slot
on conflict (property_id, meter_id, interval_start, interval_end, source) do update set
  consumption_kwh = excluded.consumption_kwh,
  solar_generation_kwh = excluded.solar_generation_kwh,
  solar_consumed_by_tenant_kwh = excluded.solar_consumed_by_tenant_kwh,
  grid_import_kwh = excluded.grid_import_kwh,
  grid_export_kwh = excluded.grid_export_kwh,
  battery_soc_pct = excluded.battery_soc_pct,
  finalized_at = excluded.finalized_at;

insert into bills (id, property_id, tenant_user_id, tariff_id, period_start, period_end, consumption_kwh, solar_generation_kwh, grid_import_kwh, grid_export_kwh, usage_cost, supply_cost, solar_credit, total_amount, estimated_savings, carbon_avoided_kg, status)
values
  ('eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', now() - interval '30 days', now(), 430, 780, 155, 338, 52.70, 33.60, 27.04, 59.26, 173.54, 530.40, 'issued')
on conflict (id) do nothing;

insert into solar_products (id, manufacturer, model, panel_power_w, panel_area_m2, unit_cost, warranty_years, efficiency_pct, metadata, active)
values
  ('ffffffff-ffff-4fff-8fff-ffffffffffff', 'Demo Solar', 'DS-440', 440, 2.0, 210, 25, 22.1, '{"reference":"hackathon"}', true)
on conflict (id) do nothing;

insert into solar_assessments (id, property_id, roof_area_m2, usable_roof_area_m2, estimated_panel_count, estimated_system_kw, estimated_annual_generation_kwh, estimated_installation_cost, estimated_annual_savings, estimated_payback_years, estimated_roi_pct, estimated_carbon_reduction_kg_year, assumptions, status, created_by)
values
  ('99999999-9999-4999-8999-999999999999', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 118, 76, 38, 16.72, 24244, 24244, 6244.83, 3.88, 415.1, 16485.92, '{"panelWattageW":440,"panelAreaM2":2,"usableRoofPercentage":0.65,"specificAnnualYieldKwhPerKw":1450,"installationCostPerKw":1450,"electricityRatePerKwh":0.34,"feedInRatePerKwh":0.08,"selfConsumptionRatio":0.72,"annualDegradationPct":0.005,"analysisPeriodYears":20,"gridEmissionsKgPerKwh":0.68}', 'completed', '22222222-2222-4222-8222-222222222222')
on conflict (id) do nothing;

insert into lease_requests (id, property_id, tenant_user_id, request_type, message, status)
values
  ('88888888-8888-4888-8888-888888888888', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '11111111-1111-4111-8111-111111111111', 'solar_installation_notice', 'I would like to review the proposed solar PPA terms.', 'submitted')
on conflict (id) do nothing;

insert into price_adjustments (id, property_id, previous_tariff_id, proposed_usage_rate, proposed_feed_in_rate, proposed_daily_charge, reason, effective_from, status, created_by)
values
  ('77777777-7777-4777-8777-777777777777', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'dddddddd-dddd-4ddd-8ddd-dddddddddddd', 0.31, 0.08, 1.12, 'Share solar savings with tenant after installation.', now() + interval '14 days', 'pending', '22222222-2222-4222-8222-222222222222')
on conflict (id) do nothing;

insert into proposals (id, property_id, proposal_type, title, description, proposed_by, recipient_user_id, status, financial_summary, terms, valid_until)
values
  ('66666666-6666-4666-8666-666666666666', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'ppa', 'Demo Solar PPA Draft', 'Draft PPA proposal for rooftop solar and tenant energy pricing.', '22222222-2222-4222-8222-222222222222', '11111111-1111-4111-8111-111111111111', 'sent', '{"estimatedAnnualSavings":6244.83,"currency":"AUD"}', '{"draftNotice":"DRAFT - Requires human/legal review before execution"}', now() + interval '30 days')
on conflict (id) do nothing;

insert into contracts (id, property_id, proposal_id, contract_type, tenant_user_id, landlord_user_id, agent_user_id, status, terms, created_by)
values
  ('55555555-5555-4555-8555-555555555555', 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', '66666666-6666-4666-8666-666666666666', 'ppa', '11111111-1111-4111-8111-111111111111', '22222222-2222-4222-8222-222222222222', '33333333-3333-4333-8333-333333333333', 'draft', '{"draftNotice":"DRAFT - Requires human/legal review before execution"}', '22222222-2222-4222-8222-222222222222')
on conflict (id) do nothing;

insert into energy_control_settings (property_id, mode, battery_min_reserve_pct, allow_grid_export, max_grid_import_kw, updated_by)
values ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'automatic', 20, true, 8, '22222222-2222-4222-8222-222222222222')
on conflict (property_id) do update set mode = excluded.mode, battery_min_reserve_pct = excluded.battery_min_reserve_pct;

insert into green_credit_programs (
  id, property_id, name, version, credits_per_kwh_microcredits,
  tenant_share_bps, owner_share_bps, enabled, effective_from
) values (
  '12121212-1212-4121-8121-121212121212',
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  'Demo verified solar rewards',
  1,
  1000000,
  7000,
  3000,
  true,
  now() - interval '1 year'
) on conflict (property_id, version) do update set
  credits_per_kwh_microcredits = excluded.credits_per_kwh_microcredits,
  tenant_share_bps = excluded.tenant_share_bps,
  owner_share_bps = excluded.owner_share_bps,
  enabled = excluded.enabled;

insert into green_projects (
  id, slug, title, description, category, location, image_path,
  target_microcredits,
  minimum_allocation_microcredits, status, impact_unit, expected_impact,
  verification_method, opens_at, closes_at, metadata
) values
  (
    '13131313-1313-4131-8131-131313131313',
    'illawarra-community-battery',
    'Illawarra Community Battery',
    'Support shared battery capacity that helps local households use more renewable electricity.',
    'energy_storage',
    'Illawarra, NSW',
    '/green-projects/illawarra-community-battery.webp',
    250000000000,
    1000000,
    'open',
    'kWh of community storage supported',
    500,
    'Quarterly operator reports and commissioned-capacity evidence',
    now() - interval '7 days',
    now() + interval '180 days',
    '{"curated":true,"featured":true,"sponsor_name":"BrightGrid Community Fund","sponsor_commitment_dollars":2500,"credits_per_sponsor_dollar":100}'
  ),
  (
    '14141414-1414-4141-8141-141414141414',
    'social-housing-solar',
    'Solar for Social Housing',
    'Fund rooftop solar installations for households facing energy hardship.',
    'rooftop_solar',
    'New South Wales',
    '/green-projects/social-housing-solar.webp',
    400000000000,
    1000000,
    'open',
    'solar capacity installed (kW)',
    25,
    'Installer certificates, inverter commissioning records, and annual generation reports',
    now() - interval '7 days',
    now() + interval '270 days',
    '{"curated":true,"sponsor_name":"Green Horizon Foundation","sponsor_commitment_dollars":4000,"credits_per_sponsor_dollar":100}'
  ),
  (
    '15151515-1515-4151-8151-151515151515',
    'coastal-habitat-restoration',
    'Coastal Habitat Restoration',
    'Restore native coastal vegetation and improve habitat resilience.',
    'habitat_restoration',
    'South Coast, NSW',
    '/green-projects/coastal-habitat-restoration.webp',
    150000000000,
    500000,
    'open',
    'square metres restored',
    10000,
    'Geotagged planting records and independent completion review',
    now() - interval '7 days',
    now() + interval '150 days',
    '{"curated":true,"sponsor_name":"Coast & Country Impact Pool","sponsor_commitment_dollars":1500,"credits_per_sponsor_dollar":100}'
  )
on conflict (id) do update set
  title = excluded.title,
  description = excluded.description,
  target_microcredits = excluded.target_microcredits,
  minimum_allocation_microcredits = excluded.minimum_allocation_microcredits,
  status = excluded.status,
  image_path = excluded.image_path,
  metadata = excluded.metadata;

select accrue_green_credits(
  'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
  now() - interval '30 days',
  now()
);
