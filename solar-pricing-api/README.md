# Solar Tenant Pricing API

A **FastAPI** microservice that dynamically prices rooftop solar electricity
supplied by a landlord to a tenant in **Wollongong, NSW, Australia**.

The core goal: **the tenant pays less than grid retail, while the landlord
earns more than the solar feed-in tariff**.

```
P_export(t)  <  P_tenant(t,q)  <  P_grid(t)
```

---

## How the Pricing Works

### The Value-Sharing Range

```
Grid retail price (P_grid)          ← tenant's alternative cost
      │
      │  ← landlord/tenant value-sharing range →
      │
Solar export price (P_export)       ← landlord's opportunity cost
```

The tenant solar price sits **inside** this range. Both parties benefit:
- **Tenant** pays less than buying from a retailer.
- **Landlord** earns more than exporting surplus solar to the grid.

### Dynamic Pricing Formula

The tenant's solar electricity rate is:

```
P_solar(t, q) = P_export(t) + α(q) × (P_grid(t) − P_export(t))
```

where the landlord share factor α decays with usage:

```
α(q) = α_min + (α_max − α_min) × e^(−k × q)
```

| Parameter | Meaning | Default |
|-----------|---------|---------|
| `α_min` | Share factor floor (high usage) | 0.40 |
| `α_max` | Share factor ceiling (low usage) | 0.75 |
| `k` | Decay sensitivity | 0.50 |

**Result:** Higher solar consumption → lower price per kWh → incentive to use solar when it's available.

### Fixed Pricing Mode

Alternatively, use `"pricing_mode": "fixed"` with a flat `fixed_solar_rate_cents_per_kwh` (e.g. 22 c/kWh).

---

## Quick Start

```bash
# Clone and enter the project
cd solar-pricing-api

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload
```

Then open: **http://localhost:8000/docs**

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/price/calculate` | Price a single usage interval |
| `POST` | `/api/v1/price/calculate-batch` | Price multiple intervals with summary |
| `GET` | `/api/v1/price/preview` | Quick pricing preview via query params |
| `GET` | `/api/v1/tariffs` | Current TOU tariff schedule |
| `GET` | `/health` | Health check |

Interactive docs at `/docs` (Swagger UI) and `/redoc` (ReDoc).

---

## Example: Single Calculation

```bash
curl -X POST http://localhost:8000/api/v1/price/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "usage_kwh": 2.5,
    "solar_available_kwh": 3.0,
    "timestamp": "2026-08-22T12:30:00+10:00",
    "pricing_mode": "dynamic",
    "alpha_min": 0.40,
    "alpha_max": 0.75,
    "discount_sensitivity": 0.50
  }'
```

### Example Response

```json
{
  "timestamp": "2026-08-22T12:30:00+10:00",
  "pricing_mode": "dynamic",
  "usage_kwh": 2.5,
  "solar_available_kwh": 3.0,
  "solar_usage_kwh": 2.5,
  "grid_usage_kwh": 0.0,
  "grid_rate_cents_per_kwh": 12.35,
  "export_rate_cents_per_kwh": 3.2,
  "alpha": 0.5003,
  "solar_rate_cents_per_kwh": 7.778,
  "solar_charge_dollars": 0.1945,
  "grid_charge_dollars": 0.0,
  "total_charge_dollars": 0.1945,
  "tenant_grid_cost_without_solar_dollars": 0.3088,
  "tenant_saving_dollars": 0.1143,
  "tenant_saving_percentage": 37.01,
  "landlord_export_value_dollars": 0.08,
  "landlord_additional_revenue_dollars": 0.1145
}
```

---

## Example: Batch Calculation

```bash
curl -X POST http://localhost:8000/api/v1/price/calculate-batch \
  -H "Content-Type: application/json" \
  -d '{
    "intervals": [
      {"usage_kwh": 0.8, "solar_available_kwh": 1.2, "timestamp": "2026-08-22T11:00:00+10:00"},
      {"usage_kwh": 2.0, "solar_available_kwh": 3.5, "timestamp": "2026-08-22T12:00:00+10:00"},
      {"usage_kwh": 3.1, "solar_available_kwh": 1.0, "timestamp": "2026-08-22T18:00:00+10:00"}
    ],
    "pricing_mode": "dynamic",
    "alpha_min": 0.40,
    "alpha_max": 0.75,
    "discount_sensitivity": 0.50
  }'
```

---

## Example: Preview

```bash
curl "http://localhost:8000/api/v1/price/preview?usage_kwh=3&solar_available_kwh=4&timestamp=2026-08-22T12:00:00%2B10:00"
```

---

## Example: View Tariffs

```bash
curl http://localhost:8000/api/v1/tariffs
```

---

## Running Tests

```bash
pytest -v
```

---

## Default Tariff Schedule (Wollongong / Endeavour Energy)

### Grid Rates (cents/kWh)

| Period | Rate |
|--------|------|
| 00:00–10:00 | 35.69 |
| 10:00–14:00 | 12.35 |
| 14:00–16:00 | 35.69 |
| 16:00–20:00 | 46.85 |
| 20:00–24:00 | 35.69 |

### Export Rates (cents/kWh)

| Period | Rate |
|--------|------|
| 00:00–10:00 | 4.00 |
| 10:00–14:00 | 3.20 |
| 14:00–16:00 | 6.00 |
| 16:00–20:00 | 18.00 |
| 20:00–24:00 | 4.00 |

Rates are configured in `app/tariffs.py` and can be overridden per-request.

---

## Project Structure

```
solar-pricing-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI application & routes
│   ├── models.py         # Pydantic v2 request/response models
│   ├── pricing.py        # Core pricing engine (pure functions)
│   ├── tariffs.py        # TOU tariff schedules & resolvers
│   └── config.py         # Location & default parameters
├── tests/
│   ├── __init__.py
│   ├── test_api.py       # Endpoint integration tests
│   └── test_pricing.py   # Pricing engine unit tests
├── requirements.txt
├── README.md
└── .gitignore
```

---

## Architecture

```
Client
  ↓
FastAPI endpoint
  ↓
Pydantic request validation
  ↓
Tariff resolver  (app/tariffs.py)
  ↓
Pricing engine   (app/pricing.py)
  ↓
Calculation result
  ↓
JSON response
```

Tariffs, pricing logic, and the API layer are fully decoupled.
The static tariff configuration can later be replaced by:
- Retailer APIs (AGL, Origin, EnergyAustralia, etc.)
- Database-stored contracts
- Smart-meter data
- Solar inverter / weather forecasts

---

## Assumptions

1. All rates are in **Australian cents per kWh**; charges returned in **AUD**.
2. Timestamps must be **timezone-aware** (AEST/AEDT via `Australia/Sydney`).
3. The API calculates **consumption pricing only** — it does not manage metering, billing, or authentication.
4. Tariff schedules are based on modelling estimates for the Endeavour Energy / Wollongong area and should be updated with actual retailer data.
5. No database, no authentication, no frontend — this is a **pricing calculation microservice**.
