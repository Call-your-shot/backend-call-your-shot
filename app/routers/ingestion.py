from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Query, status

from ..utils.ingestion import ingest_raw_telemetry, query_raw_telemetry
from ..schemas import IngestTelemetryResponse, RawTelemetryQueryResponse

router = APIRouter(prefix="/api/v1/ingestion", tags=["ingestion"])


@router.post(
    "/telemetry",
    response_model=IngestTelemetryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_telemetry_endpoint(
    date: str = Query(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        description="Target date YYYY-MM-DD for telemetry ingestion",
    ),
    weather: Literal["sunny", "cloudy", "rainy"] = Query(
        "sunny",
        description="Simulated weather state for IoT devices",
    ),
) -> IngestTelemetryResponse:
    """
    Fetch 24-hour raw hardware telemetry from external IoT mock server
    and persist raw telemetry packets into the database.
    """
    return await ingest_raw_telemetry(date_str=date, weather=weather)


@router.get(
    "/telemetry",
    response_model=RawTelemetryQueryResponse,
)
def get_raw_telemetry_records(
    date: Optional[str] = Query(
        None,
        description="Filter stored raw telemetry by date (YYYY-MM-DD)",
    ),
) -> RawTelemetryQueryResponse:
    """
    Retrieve stored raw IoT telemetry packets from database storage.
    """
    return query_raw_telemetry(date_str=date)
