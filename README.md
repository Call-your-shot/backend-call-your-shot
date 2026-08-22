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
14 passed
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
```

Annual estimation:

```text
POST /api/v1/analytics/estimate-annual-load
```

Telemetry:

```text
POST /api/v1/ingestion/telemetry
GET  /api/v1/ingestion/telemetry
GET  /api/v1/analytics/dashboard
GET  /api/v1/telemetry/live
```

Frontend views:

```text
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

Example:

```bash
curl "http://127.0.0.1:8001/api/properties/11111111-1111-4111-8111-111111111111/dashboard?role=landlord"
```

## Database Notes

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
