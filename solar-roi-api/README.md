# Solar ROI API

A production-oriented FastAPI microservice for explainable rooftop-solar return,
capital recovery, historical performance, and payback forecasting. It answers:

- How much solar energy was generated, consumed by tenants, and exported?
- How much tenant and feed-in-tariff revenue was earned?
- How much installation capital has been recovered, and how much remains?
- When should the system pay itself back?
- How does payback change under conservative, expected, and optimistic assumptions?

The implementation is deterministic. It uses calendar-month averages, standard
Python mathematics, and explicit assumptions—no machine learning, database, or
external tariff API.

## Pricing-service boundary

Dynamic electricity pricing belongs to a separate service. This API does not
rebuild or depend on that service's internal pricing algorithm. It consumes
already-calculated values such as `tenant_revenue_dollars`,
`export_revenue_dollars`, and optional average rates. A later integration can
populate the same fields from the pricing service without changing the ROI
calculation layer.

```text
Smart meter / solar inverter
          |
          v
Historical energy data ---> Pricing Service ---> Historical tenant revenue
          |                                             |
          +---------------------+-----------------------+
                                v
                    +-------------------------+
Installation cost ->|       ROI Service       |
Generation data --->|                         |
Export history ---->|                         |
Revenue history --->|                         |
                    +------------+------------+
                                 |
                 +---------------+----------------+
                 v               v                v
        Historical analytics  Seasonal forecast  Scenario comparison
                                 |
                                 v
                          Payback estimate
```

## Project structure

```text
solar-roi-api/
├── app/
│   ├── __init__.py
│   ├── analytics.py      # history, seasonality, trends, warnings
│   ├── config.py         # configurable defaults and scenarios
│   ├── forecasting.py    # deterministic monthly projections/payback
│   ├── main.py           # thin FastAPI transport layer
│   ├── models.py         # Pydantic v2 request/response contracts
│   ├── roi.py            # pure financial calculations
│   ├── scenarios.py      # scenario orchestration
│   ├── service.py        # shared application orchestration
│   └── utils.py          # date and display helpers
├── examples/
│   ├── example-request.json
│   └── example-summary-response.json
├── tests/
│   ├── conftest.py
│   ├── test_analytics.py
│   ├── test_api.py
│   ├── test_forecasting.py
│   └── test_roi.py
├── .gitignore
├── .python-version
├── README.md
└── requirements.txt
```

Route functions only validate/serialize HTTP data and invoke the shared service.
The financial, analytics, forecasting, and scenario modules run independently of
FastAPI and are directly unit tested.

## Run locally

Python 3.12 or newer is required.

```bash
cd solar-roi-api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

- Swagger UI: <http://127.0.0.1:8000/docs>
- ReDoc: <http://127.0.0.1:8000/redoc>
- Health: <http://127.0.0.1:8000/health>

Run tests:

```bash
pytest -v
```

## API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Availability check |
| `POST` | `/api/v1/roi/analyse` | Complete historical, ROI, forecast, and scenario output |
| `POST` | `/api/v1/roi/summary` | Primary business metrics only |
| `POST` | `/api/v1/roi/forecast` | Future timeline, assumptions, payback, and scenarios |
| `POST` | `/api/v1/roi/history-analysis` | Historical energy, financial, yield, seasonality, and trend metrics |

All endpoints reuse the same domain engine; financial logic is not duplicated.

### Example requests

Complete analysis:

```bash
curl --fail --show-error \
  -X POST http://127.0.0.1:8000/api/v1/roi/analyse \
  -H 'Content-Type: application/json' \
  --data @examples/example-request.json
```

High-level summary:

```bash
curl --fail --show-error \
  -X POST http://127.0.0.1:8000/api/v1/roi/summary \
  -H 'Content-Type: application/json' \
  --data @examples/example-request.json
```

The complete request is in
[`examples/example-request.json`](examples/example-request.json), and a calculated
summary response is in
[`examples/example-summary-response.json`](examples/example-summary-response.json).

## Input rules

Each historical `month` must be the first day of a calendar month, for example
`2026-01-01`. Records may arrive in any order and are sorted internally.
Duplicate calendar months are rejected.

Costs, rebates, rates, revenue, and energy values cannot be negative. Zero is
valid. Exports cannot exceed generation. When explicit tenant consumption plus
exports exceeds generation by no more than the configurable meter tolerance
(default 1%), the request is accepted and a warning is returned. Larger
differences are rejected.

If tenant consumption is omitted, it is derived as:

```text
tenant solar consumption = generation - exports
```

Every derived record is labelled `derived`; the service never silently treats
exports as tenant consumption.

## Financial calculations

No intermediate response rounding is fed back into calculations. Totals use
`math.fsum`; rounding occurs only when response models are assembled.

```text
net installation cost
  = gross installation cost - STC benefit - other upfront rebates

monthly net cash flow
  = tenant revenue + export revenue - operating cost

recovered capital
  = sum of historical monthly net cash flows

remaining cost
  = max(net installation cost - recovered capital, 0)

capital recovered %
  = recovered capital / net installation cost * 100

net ROI %
  = (recovered capital - net installation cost) / net installation cost * 100
```

Recovered capital is not capped, so capital recovery can exceed 100%. Displayed
remaining cost never goes below zero. For a zero net installation cost, capital
recovery is 100%, net ROI is undefined (`null`), and payback is immediate.

The simple annual metrics are:

```text
annualised net cash flow = average observed monthly cash flow * 12
simple annual yield %    = annualised net cash flow / net installation cost * 100
```

NPV and IRR are intentionally not implemented. Simple payback is the primary
business metric and no discount-rate assumption is silently introduced.

## Historical energy and revenue analytics

```text
self-consumption ratio = tenant solar consumption / solar generation
export ratio           = solar exports / solar generation
specific yield         = generation kWh / installed capacity kW

revenue per generated kWh
  = (tenant revenue + export revenue) / generation

revenue per tenant solar kWh
  = tenant revenue / tenant solar consumption

export revenue per kWh
  = export revenue / exports
```

Undefined ratios return `null` when their denominator is zero. Annualised
specific yield is only returned when installed capacity is supplied.

Seasonality groups real observations by calendar month and calculates average
generation, usage, self-consumption, exports, and cash flow. Missing months are
reported and are never inserted into history.

Trends use a least-squares linear slope implemented with `math` and `statistics`.
The estimated change across the observed period is classified as `increasing`,
`stable`, or `decreasing`; the default stable band is ±5%. Fewer than three
usable observations returns `insufficient_data`. Year-over-year output compares
the latest two matching calendar months from different years.

## Forecasting

Future generation follows this priority for every target calendar month:

```text
matching calendar-month historical mean
  -> observations within two neighbouring calendar months
  -> overall observed monthly mean
```

No external generation values are invented. Every projected month reports the
method used, and the forecast summary reports whether the run was fully seasonal
or used fallbacks.

Expected self-consumption uses the matching seasonal ratio where available and
otherwise the same fallback profile. Projected consumption and exports are:

```text
projected tenant consumption = projected generation * expected SCR
projected exports            = projected generation - projected consumption
```

Panel degradation is applied monthly:

```text
generation = seasonal base * (1 - annual degradation) ** (months ahead / 12)
```

Tenant/export prices and operating costs can independently grow or decline:

```text
future value = base value * (1 + annual growth) ** (months ahead / 12)
```

Growth defaults to zero. Degradation defaults to 0.5% annually.

### Revenue modes

`historical_cashflow` forecasts the historical calendar-month revenue/cost
components, with seasonal fallback and configured degradation/growth. This is
appropriate when payment data—possibly from the pricing service—is authoritative.

`energy_based` calculates projected revenue from projected energy and explicit or
historically derived effective rates:

```text
tenant revenue = tenant solar kWh * tenant cents/kWh / 100
export revenue = exported kWh * export cents/kWh / 100
net cash flow  = tenant revenue + export revenue - operating cost
```

Missing rates do not fail the historical analysis. The affected future revenue
is zero and a structured warning is returned.

### Payback simulation

The forecast starts with unrecovered cost after historical cash flow, then
simulates each future month:

```text
next remaining cost = current remaining cost - projected monthly net cash flow
```

The first crossing is the forecast payback month. Partial-month payback is
estimated as `entering balance / positive monthly cash flow`. Forecasting stops
at payback or the configured horizon (360 months by default), so it cannot loop
forever. If projected average cash flow is non-positive, the response explains
that cash flow is insufficient. If positive cash flow still cannot pay back by
the horizon, the response reports the horizon reason.

If historical cumulative cash flow already crossed the investment, the first
historical crossing month is returned and months remaining is zero. A separate
12-month performance projection remains available for plotting.

## Scenarios

Defaults live in `app/config.py` and can be overridden in the request:

| Scenario | Generation | Self-consumption | Tenant rate | Operating cost |
|---|---:|---:|---:|---:|
| Conservative | 90% | 90% | 95% | 110% |
| Expected | 100% | 100% | 100% | 100% |
| Optimistic | 105% | 110% (capped at 100% SCR) | 105% | 100% |

Each scenario runs the same month-by-month payback function and returns the exact
multipliers used.

## Optional opportunity and tenant-savings metrics

When `potential_tenant_rate_cents_per_kwh` is supplied, export opportunity is:

```text
exports * max(potential tenant rate - effective export rate, 0) / 100
```

It is explicitly labelled as a **maximum theoretical export conversion value**;
it is not guaranteed lost revenue because coincident tenant demand is unknown.

Tenant savings are returned only when each month has a grid rate and
`actual_grid_cost_dollars`:

```text
baseline grid cost = total usage * grid rate
actual cost        = actual grid cost + tenant solar payment
tenant savings     = baseline - actual cost
```

Missing optional savings data never fails the ROI analysis.

## Data-quality warnings

Warnings are separate from HTTP validation errors and include short history,
insufficient seasonal coverage, derived consumption, tolerated/reconciling meter
differences, month gaps, missing installed capacity, non-positive cash flow,
history before installation, zero net installation cost, and unavailable rates
for energy-based forecasts.

HTTP `422` is reserved for invalid input such as negative values, duplicate
months, non-canonical dates, exports above generation, or energy imbalance beyond
the configured tolerance.

## Future compatibility

The API is stateless and its models can be extended with property/system/tenant
identifiers, meter IDs, pricing contracts, batteries, weather adjustment,
maintenance events, financing, tax, and discount-rate fields. The domain modules
do not assume a particular property, retailer, network, pricing provider, or data
store.
