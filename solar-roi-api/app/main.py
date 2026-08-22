"""FastAPI transport layer; all business logic lives in domain modules."""

from __future__ import annotations

from fastapi import FastAPI

from .config import API_TITLE, API_VERSION, SERVICE_TIMEZONE
from .models import (
    AnalysisRequest,
    AnalysisResponse,
    ForecastOnlyResponse,
    HealthResponse,
    HistoricalAnalysisResponse,
    InitialEstimateRequest,
    InitialEstimateResponse,
    SummaryResponse,
)
from .monte_carlo import run_monte_carlo_roi
from .service import (
    analyse_roi,
    build_forecast_response,
    build_history_response,
    build_summary,
)

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    summary="Explainable rooftop-solar ROI and payback forecasting",
    description=f"""
This service calculates historical capital recovery and deterministic, seasonal
payback forecasts for rooftop solar installations. Calendar interpretation uses
the `{SERVICE_TIMEZONE.key}` timezone.

The service **does not calculate dynamic electricity prices**. It accepts tenant
and feed-in-tariff revenue produced by metering, billing, or a separate pricing
service. No database, external tariff API, or pricing-engine dependency is used.
""",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "health", "description": "Service availability."},
        {"name": "roi", "description": "Solar ROI, history, and forecast analysis."},
    ],
)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Check service health",
)
def health() -> HealthResponse:
    return HealthResponse()


@app.post(
    "/api/v1/roi/analyse",
    response_model=AnalysisResponse,
    tags=["roi"],
    summary="Run complete ROI analysis",
    description="Returns historical energy and cash-flow analytics, capital recovery, seasonal forecasts, payback timing, scenarios, and data-quality warnings.",
)
def analyse(request: AnalysisRequest) -> AnalysisResponse:
    return analyse_roi(request)


@app.post(
    "/api/v1/roi/summary",
    response_model=SummaryResponse,
    tags=["roi"],
    summary="Get high-level ROI results",
    description="Runs the shared analysis engine and returns only the primary business outputs.",
)
def summary(request: AnalysisRequest) -> SummaryResponse:
    return build_summary(analyse_roi(request))


@app.post(
    "/api/v1/roi/forecast",
    response_model=ForecastOnlyResponse,
    tags=["roi"],
    summary="Forecast future performance and payback",
    description="Returns the expected monthly projection, payback estimate, assumptions, and configurable scenarios.",
)
def forecast(request: AnalysisRequest) -> ForecastOnlyResponse:
    return build_forecast_response(analyse_roi(request))


@app.post(
    "/api/v1/roi/history-analysis",
    response_model=HistoricalAnalysisResponse,
    tags=["roi"],
    summary="Analyse historical performance",
    description="Returns deterministic historical energy, financial, seasonality, yield, trend, and data-quality metrics without future projections.",
)
def history_analysis(request: AnalysisRequest) -> HistoricalAnalysisResponse:
    return build_history_response(request)


@app.post(
    "/api/v1/roi/estimate-initial",
    response_model=InitialEstimateResponse,
    tags=["roi"],
    summary="Estimate initial ROI with Monte Carlo simulation",
    description=(
        "For new or pre-installation systems with little or no operating history. "
        "Creates bounded, assumption-based future paths and returns simulation "
        "percentiles and a forecast interval—not a statistical confidence interval. "
        "The historical ROI endpoints and dynamic pricing service remain separate."
    ),
)
def estimate_initial(request: InitialEstimateRequest) -> InitialEstimateResponse:
    return run_monte_carlo_roi(request)
