# Legacy Supabase Schema Layout

This schema is not used by the active backend anymore. The current backend is FastAPI under `backend/app/`.

The Supabase files are kept only as a migration archive until they are explicitly deleted.

These files split the Supabase schema by responsibility so it is easier to read and update.

The deployable migration files still live in `backend/supabase/migrations/`. Keep those migrations as the source Supabase applies in order. When changing schema, update the relevant readable schema file here and add a new timestamped migration for the actual database change.

## Files

- `01_extensions_and_types.sql`: extensions and enum types.
- `02_pre_table_functions.sql`: shared trigger helpers that can be created before tables.
- `03_identity_and_property_tables.sql`: profiles, properties, memberships, and meters.
- `04_energy_and_solar_tables.sql`: readings, tariffs, bills, assessments, and products.
- `05_workflow_control_and_audit_tables.sql`: lease requests, proposals, contracts, control settings, commands, and audit logs.
- `06_auth_and_audit_functions.sql`: auth helper, role helper, and audit functions that depend on tables.
- `07_triggers.sql`: `updated_at` and audit triggers.
- `08_rls_policies.sql`: row-level security enables and policies.
- `09_storage.sql`: storage buckets and object policies.
- `10_grid_rate_patch.sql`: follow-up migration for `grid_rate_cents_per_kwh`.
