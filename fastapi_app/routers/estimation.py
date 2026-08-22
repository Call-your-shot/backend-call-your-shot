from fastapi import APIRouter

from ..estimation_service import calculate_annual_energy_estimation
from ..schemas import AnnualEstimationRequest, AnnualEstimationResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.post(
    "/estimate-annual-load",
    response_model=AnnualEstimationResponse,
    summary="Estimate Annual Energy Usage",
    description="Accepts user bill survey data, deconstructs baseline daily load, applies Wollongong seasonal climate modifiers, and returns the estimated annual energy usage (kWh).",
)
def estimate_annual_load_endpoint(payload: AnnualEstimationRequest) -> AnnualEstimationResponse:
    return calculate_annual_energy_estimation(payload)
