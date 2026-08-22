from fastapi import APIRouter

from ..schemas.roi import (
    AnalysisRequest,
    AnalysisResponse,
    ForecastOnlyResponse,
    HistoricalAnalysisResponse,
    InitialEstimateRequest,
    InitialEstimateResponse,
    SummaryResponse,
)
from ..utils.roi_engine.monte_carlo import run_monte_carlo_roi
from ..utils.roi_engine.service import analyse_roi, build_forecast_response, build_history_response, build_summary

router = APIRouter(prefix="/api/v1/roi", tags=["roi"])


@router.post("/analyse", response_model=AnalysisResponse)
def analyse(request: AnalysisRequest) -> AnalysisResponse:
    return analyse_roi(request)


@router.post("/summary", response_model=SummaryResponse)
def summary(request: AnalysisRequest) -> SummaryResponse:
    return build_summary(analyse_roi(request))


@router.post("/forecast", response_model=ForecastOnlyResponse)
def forecast(request: AnalysisRequest) -> ForecastOnlyResponse:
    return build_forecast_response(analyse_roi(request))


@router.post("/history-analysis", response_model=HistoricalAnalysisResponse)
def history_analysis(request: AnalysisRequest) -> HistoricalAnalysisResponse:
    return build_history_response(request)


@router.post("/estimate-initial", response_model=InitialEstimateResponse)
def estimate_initial(request: InitialEstimateRequest) -> InitialEstimateResponse:
    return run_monte_carlo_roi(request)
