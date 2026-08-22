alter table price_adjustments
  add column if not exists fixed_solar_rate_cents_per_kwh numeric
    check (fixed_solar_rate_cents_per_kwh is null or fixed_solar_rate_cents_per_kwh >= 0);
