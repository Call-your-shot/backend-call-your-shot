-- Readable schema entry point for the green-credit subsystem.
-- The deployable migration remains the source of truth; \ir resolves relative
-- to this file when the modular schema is loaded with psql.
\ir ../migrations/202608220007_green_credits.sql
