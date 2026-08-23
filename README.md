# Call Your Shot Backend

FastAPI backend for the energy, solar, pricing, ROI, and contract workflow demo.

## What This API Covers

- Dashboard data for tenant, landlord, and agent views
- Electric usage, solar generation, grid import/export, and battery state
- Annual load estimation from bill/survey data
- Solar assessment and installation estimate records
- Dynamic and fixed solar pricing calculations
- Tenant savings and landlord revenue calculations
- ROI analysis and Monte Carlo initial estimate routes
- Price adjustment workflow for landlord/agent approval
- Lease request workflow
- Draft PPA / contract generation
- Raw IoT telemetry ingestion and analytics

## Project Structure

```text
app/
  main.py                  FastAPI app entrypoint
  api_link/                Active API routers
  routers/                 Legacy-compatible router modules
  schemas/                 Pydantic request/response models
  utils/                   Calculation and workflow functions
  clients/                 External/mock API clients
  data.py                  In-memory demo data store

supabase/
  migrations/              Deployable database migrations
  schema/                  Readable split SQL schema files

tests/                     Python API and utility tests
```

## Run Locally

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Start the API:

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Open:

```text
http://127.0.0.1:8001
http://127.0.0.1:8001/docs
```

## Test

```bash
PYTHONPYCACHEPREFIX=/private/tmp/pycache python3 -m pytest tests
```

Current verified status:

```text
80 passed
```

## Main Endpoints

Health:

```text
GET /api/health
```

Dashboard:

```text
GET /api/properties
GET /api/properties/{property_id}
GET /api/properties/{property_id}/dashboard?role=tenant
GET /api/properties/{property_id}/dashboard?role=landlord
GET /api/properties/{property_id}/dashboard?role=agent
```

Energy and solar:

```text
GET  /api/properties/{property_id}/energy-readings
POST /api/properties/{property_id}/energy-readings
GET  /api/properties/{property_id}/batteries
GET  /api/properties/{property_id}/tariffs
POST /api/properties/{property_id}/tariffs
GET  /api/properties/{property_id}/solar-assessments
POST /api/properties/{property_id}/solar-assessments
GET  /api/properties/{property_id}/solar-installations
POST /api/properties/{property_id}/solar-installations
```

Pricing:

```text
GET  /api/v1/pricing/tariffs
POST /api/v1/pricing/calculate
POST /api/v1/pricing/calculate-batch
```

ROI:

```text
POST /api/v1/roi/analyse
POST /api/v1/roi/summary
POST /api/v1/roi/forecast
POST /api/v1/roi/history-analysis
POST /api/v1/roi/estimate-initial
POST /api/v1/assessments/initial
GET  /api/v1/assessments/{assessment_id}
```

`/roi/estimate-initial` is the pure Monte Carlo engine. The assessment routes
are the application-facing orchestration layer: they combine roof, household,
installation-cost, and pricing assumptions, persist the result for the current
process, and return separate tenant-savings and landlord-payback economics.
Proposals can reference the saved assessment so they do not recalculate a
different financial result.

The default assumption-based dynamic-pricing approximation uses an aggressive
landlord-optimistic alpha range of `0.65 / 0.80 / 0.95` (minimum / mode / maximum).
Higher alpha increases the tenant solar tariff within the export-to-grid price
spread, shortening modelled landlord payback while preserving the invariant
`export rate <= tenant solar rate <= grid rate`. These defaults do not change
the separate live hourly pricing engine, and callers of `/roi/estimate-initial`
can still provide explicit alpha assumptions.

Annual estimation:

```text
POST /api/v1/analytics/estimate-annual-load
POST /api/v1/solar-sizing/recommend
```

The annual-load route produces a complete January-to-December demand profile.
Real monthly bills are preserved exactly; missing months are derived from the
observed bill period and survey-only appliance usage. Daytime occupancy changes
the expected solar overlap, not the household's measured consumption.

The sizing route evaluates the physical configurations that fit the roof. It
does not automatically select the roof maximum. Each candidate is simulated
against monthly demand and screened for tenant savings probability, onsite
self-consumption, export share, median payback, and the marginal payback of the
additional panels. The largest candidate passing every configurable guardrail
is returned with the rejected alternatives and an explainable reason. The same
monthly profiles and sizing snapshot can then be passed into
`/api/v1/assessments/initial`, keeping the final ROI and proposal consistent
with the panel recommendation.

Telemetry:

```text
POST /api/v1/ingestion/telemetry
GET  /api/v1/ingestion/telemetry
GET  /api/v1/analytics/dashboard
GET  /api/v1/telemetry/live
```

Frontend views:

```text
GET /api/dashboard?email={email}
GET /api/plans?email={email}
GET /api/plans/{id}?email={email}
POST /api/plans/{id}/leave
GET /api/properties?email={email}
GET /api/properties/{id}?email={email}
POST /api/properties/{id}/leave-request/approve
POST /api/properties/{id}/invite
POST /api/properties/{id}/invite/accept
GET /api/notifications?email={email}
```

Green credits and sponsor-backed projects:

```text
GET  /api/v1/green-credits/wallet?email={email}
GET  /api/v1/green-credits/ledger?email={email}
GET  /api/v1/green-credits/allocations?email={email}
GET  /api/v1/green-projects?email={email}
GET  /api/v1/green-projects/{project_id}?email={email}
POST /api/v1/green-projects/{project_id}/allocations?email={email}
```

### Green-credit frontend authentication

The green-credit API supports two identity paths behind the same service and
response models:

- Production clients send `Authorization: Bearer <supabase-access-token>`.
- The current email-only demo UI sends `?email=<account-email>` while
  `GREEN_CREDIT_DEMO_AUTH=true`.

A bearer token always takes precedence when both are supplied. Email-only
identity is disabled automatically when `APP_ENV=production` unless it is
explicitly re-enabled, and should remain disabled in a real deployment. The
demo repository is process-local: allocations persist across requests but are
reset when the API process restarts.

The seeded UI identities are:

```text
sarah.chen@example.com
david.marino@example.com
qimatx@example.com
tenant@example.com
landlord@example.com
```

Any other valid demo email receives an empty wallet rather than another
person's credits.

Example frontend reads:

```bash
curl "http://127.0.0.1:8001/api/v1/green-credits/wallet?email=sarah.chen%40example.com"

curl "http://127.0.0.1:8001/api/v1/green-projects?email=sarah.chen%40example.com"
```

Example allocation (the idempotency key must be unique per user action):

```bash
curl -X POST \
  "http://127.0.0.1:8001/api/v1/green-projects/13131313-1313-4131-8131-131313131313/allocations?email=sarah.chen%40example.com" \
  -H "Content-Type: application/json" \
  -d '{
    "requested_credits": "250.000000",
    "idempotency_key": "green-ui-20260822-0001"
  }'
```

The frontend should treat credit amounts as decimal strings, not binary
floating-point balances. Wallet responses include `verified_solar_kwh` for the
reward-summary display. Project sponsor display fields are exposed in each
project's `metadata` object (`sponsor_name`,
`sponsor_commitment_dollars`, and `credits_per_sponsor_dollar`). Allocation
responses return the authoritative new wallet balance, while the wallet,
ledger, allocation, and project endpoints can be re-fetched after a write.

Workflow:

```text
GET  /api/properties/{property_id}/price-adjustments
POST /api/properties/{property_id}/price-adjustments
GET  /api/properties/{property_id}/lease-requests
POST /api/properties/{property_id}/lease-requests
POST /api/properties/{property_id}/lease-requests/leave
POST /api/properties/{property_id}/house-applications
PATCH /api/properties/{property_id}/lease-requests/{request_id}/status
GET  /api/properties/{property_id}/my-plan
GET  /api/properties/{property_id}/my-properties
GET  /api/properties/{property_id}/notifications
PATCH /api/properties/{property_id}/notifications/{notification_id}/read
GET  /api/properties/{property_id}/contracts
POST /api/properties/{property_id}/contracts/generate
```

Lease request status flow:

```text
submitted -> under_review -> approved
submitted -> under_review -> declined
submitted -> cancelled
```

When a tenant submits a leave request or new-house application, the landlord receives a notification. When the landlord reviews, approves, or declines it, the tenant receives a status-change notification.

## Demo Property

The in-memory demo API uses:

```text
11111111-1111-4111-8111-111111111111
```

The UI-facing demo accounts are `sarah.chen@example.com`,
`david.marino@example.com`, and `qimatx@example.com`. Dashboard and
workflow data remain process-local in demo mode and reset when FastAPI
restarts. Green credits can use either the demo repository or Supabase. A
production deployment must use the prepared Supabase schema rather than
treating these seeds as durable data.

Example:

```bash
curl "http://127.0.0.1:8001/api/properties/11111111-1111-4111-8111-111111111111/dashboard?role=landlord"
```

## Database Notes

Direct Supabase Postgres connection uses `DATABASE_URL`.

```bash
cp .env.example .env
```

Then set your real password:

```bash
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.ybsiutwhsrtzyycopdip.supabase.co:5432/postgres
```

If the password has special characters, percent-encode it before putting it in the URL.

Connection check:

```text
GET /api/supabase/health
```

Supabase migrations live in:

```text
supabase/migrations/
```

Important additions include:

- normalized property location tables
- extended `energy_readings`
- raw telemetry identity fields
- `solar_installations`
- `pricing_contracts`
- `interval_pricing_results`
- `cashflow_events`
- `roi_analysis_runs`
- fixed solar rate field for `price_adjustments`

The migrations are prepared but are not automatically applied by running the FastAPI demo server.

## Current Backend Direction

This repo has been consolidated into a Python FastAPI backend under `app/`.

The old TypeScript backend and standalone `solar-roi-api` / `solar-pricing-api` folders were removed after their functionality was merged into this app.
