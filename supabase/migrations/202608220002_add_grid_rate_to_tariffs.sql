alter table energy_tariffs
  add column if not exists grid_rate_cents_per_kwh numeric not null default 34 check (grid_rate_cents_per_kwh >= 0);

comment on column energy_tariffs.grid_rate_cents_per_kwh is
  'Retail grid electricity rate in cents/kWh, used when battery/storage cannot cover demand and energy is imported from the grid.';
