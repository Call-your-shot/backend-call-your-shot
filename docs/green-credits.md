# Green Credits API

The green-credit subsystem rewards verified rooftop-solar electricity consumed
by platform members and lets them permanently allocate those rewards to a
curated environmental project.

Green credits are private platform reward units. They are not money, carbon
offset certificates, securities, or transferable assets. Allocating credits is
a non-refundable contribution and does not create ownership or a financial
return.

## Earning model

- `1 verified tenant-consumed solar kWh = 1.000000 green credit` by default.
- The demo property awards 70% to active tenants and 30% to active landlords.
- A role share is divided equally between members active at the reading time.
- Agents, grid consumption, exports, battery charging, and unverified battery
  discharge do not earn credits.
- Only normalized readings with both `solar_consumed_by_tenant_kwh` and
  `finalized_at` are eligible.
- Credits never expire in this version.

Balances are stored as integer microcredits (`1 credit = 1,000,000
microcredits`). The immutable ledger is the source of truth.

## Configuration

Add the following environment values. Never expose the secret or internal key
to the browser.

```text
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=...
SUPABASE_SECRET_KEY=...
GREEN_CREDIT_INTERNAL_KEY=...
```

Apply the Supabase migrations and seed, then run the primary backend:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

Interactive documentation is available at `http://localhost:8001/docs`.

## User endpoints

All user endpoints require `Authorization: Bearer <supabase-access-token>`.

```text
GET  /api/v1/green-credits/wallet
GET  /api/v1/green-credits/ledger
GET  /api/v1/green-credits/allocations
GET  /api/v1/green-projects
GET  /api/v1/green-projects/{project_id}
POST /api/v1/green-projects/{project_id}/allocations
```

Allocation example:

```bash
curl -X POST http://localhost:8001/api/v1/green-projects/PROJECT_UUID/allocations \
  -H "Authorization: Bearer $SUPABASE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "requested_credits": "25.000000",
    "idempotency_key": "project-allocation-2026-08-22-001"
  }'
```

If only 10 credits remain before the project reaches its target, the response
records a partial 10-credit allocation and leaves the other 15 credits in the
wallet. Insufficient wallet balance is rejected rather than partially spent.

## Daily accrual

The ingestion/orchestration process should invoke the internal endpoint after a
day's normalized readings are finalized:

```bash
curl -X POST http://localhost:8001/api/v1/internal/green-credits/accrue \
  -H "X-Internal-API-Key: $GREEN_CREDIT_INTERNAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "property_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    "period_start": "2026-08-21T00:00:00+10:00",
    "period_end": "2026-08-22T00:00:00+10:00"
  }'
```

Accrual and project allocation are implemented by transactional database
functions. Replaying the same accrual window or allocation idempotency key does
not spend or award credits twice.
