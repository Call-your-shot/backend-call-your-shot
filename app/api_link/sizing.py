from fastapi import APIRouter

from ..schemas.sizing import SolarSizingRequest, SolarSizingResponse
from ..utils.solar_sizing import recommend_solar_system


router = APIRouter(prefix="/api/v1/solar-sizing", tags=["solar-sizing"])


@router.post(
    "/recommend",
    response_model=SolarSizingResponse,
    summary="Recommend a demand-matched rooftop solar system",
    description=(
        "Evaluates physical roof candidates against a 12-month household demand profile, "
        "tenant savings, export share, marginal economics, and Monte Carlo payback."
    ),
)
def recommend_system(payload: SolarSizingRequest) -> SolarSizingResponse:
    return recommend_solar_system(payload)
