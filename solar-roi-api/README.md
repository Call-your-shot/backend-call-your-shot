# Solar ROI API

A production-oriented FastAPI microservice for explainable rooftop-solar return,
capital recovery, historical performance, and payback forecasting. It answers:

- How much solar energy was generated, consumed by tenants, and exported?
- How much tenant and feed-in-tariff revenue was earned?
- How much installation capital has been recovered, and how much remains?
- When should the system pay itself back?
- How does payback change under conservative, expected, and optimistic assumptions?

Historical forecasting remains deterministic. Initial estimates use an explicitly
assumption-based Monte Carlo model with reproducible seeds and bounded physical
variables. Neither mode uses machine learning, a database, or an external tariff
API.

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
│   ├── distributions.py  # bounded sampling, percentiles, rank correlation
│   ├── forecasting.py    # deterministic monthly projections/payback
│   ├── main.py           # thin FastAPI transport layer
│   ├── models.py         # Pydantic v2 request/response contracts
│   ├── monte_carlo.py     # assumption-based initial ROI simulation
│   ├── roi.py            # pure financial calculations
│   ├── scenarios.py      # scenario orchestration
│   ├── service.py        # shared application orchestration
│   └── utils.py          # date and display helpers
├── examples/
│   ├── example-request.json
│   ├── example-summary-response.json
│   ├── example-initial-estimate-request.json
│   └── example-initial-estimate-response.json
├── tests/
│   ├── conftest.py
│   ├── test_analytics.py
│   ├── test_api.py
│   ├── test_forecasting.py
│   ├── test_distributions.py
│   ├── test_monte_carlo.py
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
| `POST` | `/api/v1/roi/estimate-initial` | Assumption-based Monte Carlo estimate for new systems without history |

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

Initial Monte Carlo estimate:

```bash
curl --fail --show-error \
  -X POST http://127.0.0.1:8000/api/v1/roi/estimate-initial \
  -H 'Content-Type: application/json' \
  --data @examples/example-initial-estimate-request.json
```

See the complete [initial-estimate request](examples/example-initial-estimate-request.json)
and its calculated [response](examples/example-initial-estimate-response.json).

## Initial assumption-based Monte Carlo estimate

`POST /api/v1/roi/estimate-initial` is intentionally separate from the historical
endpoints. It is for new systems, pre-installation feasibility, or cases with too
little operating history to build a seasonal historical forecast. Its
`forecast_source` is always `assumption_based`.

Instead of pretending one future outcome is certain, the service creates
thousands of plausible versions of the future. Each path varies:

- solar generation;
- tenant demand;
- solar-demand overlap/self-consumption;
- grid and export tariffs when variability is requested;
- operating cost.

It applies monthly seasonal profiles, panel degradation, optional tariff and
usage growth, tenant/export revenue, and operating costs. Each path tracks
monthly cumulative cash flow and estimates fractional-month payback.

### Bounded assumptions

- Generation uses a normal distribution truncated to configurable lower and
  upper multipliers. It cannot become negative or exceed those bounds.
- Usage, tariffs, and operating costs use non-negative truncated normals.
- Self-consumption uses a triangular distribution defined by plausible minimum,
  most-likely, and maximum values, all constrained to `[0, 1]`.
- Tenant solar consumption is `min(generation × SCR, tenant demand)`.
- Exports are `generation - tenant solar consumption`; the energy balance is
  preserved in every simulation.
- Grid/export tariffs are resampled when export would exceed grid price.

The configurable default generation and demand profiles live in `app/config.py`.
Custom profiles must contain 12 non-negative weights summing to one. Missing
months are therefore not silently inferred from historical observations; these
are disclosed forward-looking assumptions.

### Pricing approximation

This service does not call or reproduce the separate pricing service. For an
initial dynamic-pricing estimate it uses the compatible equation:

```text
alpha(q) = alpha_min + (alpha_max - alpha_min) * exp(-k * q)
tenant rate = export rate + alpha(q) * (grid rate - export rate)
```

Annual tenant solar consumption is normalised to representative usage with:

```text
q = annual tenant solar consumption / (365 * active solar-use hours per day)
```

The default is six active hours. A direct interval-usage override is supported.
This approximation is designed to be replaced later by real smart-meter interval
output from the pricing service. Alternatively, `alpha_estimation_mode` can be
`triangular`, in which case the alpha assumption is explicitly sampled.

Fixed pricing uses the supplied fixed tenant solar rate. In either mode, only
tenant solar revenue and feed-in-tariff revenue belong to the owner. Grid energy
purchased by the tenant is never counted as owner revenue.

### Interpreting results

The response reports P05, P25, P50, P75, and P95 plus mean, median, standard
deviation, minimum, and maximum. The median (P50) is the headline because
simulated payback can be skewed. P05–P95 is labelled a **90% forecast interval**.

For the checked-in example request, the calculated output is approximately:

```text
Median payback: 7.83 years
Mean payback: 7.87 years
90% forecast interval: 7.10–8.91 years
Probability of payback within 7 years: 2.22%
Probability of payback within 10 years: 99.97%
```

This does **not** mean there is 90% statistical confidence that an unknown true
payback parameter lies in that range. It means 90% of simulated outcomes that
reached payback, under the supplied distributions and financial model, fell
between P05 and P95. The separate no-payback probability includes every
simulation that did not recover its cost within the horizon.

The response also supplies distributions for first-year generation, demand,
self-consumption, tenant solar consumption, exports, tenant/export revenue,
operating cost, annual cash flow, and cumulative ROI. A compact histogram and
annual CDF are ready for frontend charts.

### Sensitivity

Spearman rank correlations estimate which sampled first-year assumptions are
most associated with payback. Results are ranked by absolute influence. A
negative correlation means higher values tend to shorten payback; a positive
one means higher values tend to lengthen it. This is an association within the
simulation model, not proof of causation.

### Choosing a forecast source

The domain vocabulary supports a future transition without automatic switching:

```text
No history      -> assumption_based Monte Carlo estimate
Some history    -> future hybrid mode
Enough history  -> historical seasonal forecast
```

No Bayesian updating or hybrid inference is implemented yet. Observed seasonal
generation, self-consumption, exports, and payment behavior can later replace
the corresponding assumptions through the cleanly separated model boundary.

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
