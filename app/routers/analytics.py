from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Query

from ..analytics_service import process_telemetry_timeseries
from ..clients.mock_iot_client import fetch_timeseries_telemetry
from ..schemas import DashboardAnalyticsResponse

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardAnalyticsResponse)
async def get_analytics_dashboard(
    date: str = Query(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        description="Target date in YYYY-MM-DD format",
    ),
    weather: Literal["sunny", "cloudy", "rainy"] = Query(
        "sunny",
        description="Simulated weather pattern",
    ),
) -> DashboardAnalyticsResponse:
    """
    Fetch 24-hour raw hardware telemetry from external IoT mock server
    and compute processed dashboard energy & financial metrics.
    """
    raw_packets = await fetch_timeseries_telemetry(date_str=date, weather=weather)
    analytics_response = process_telemetry_timeseries(date_str=date, raw_packets=raw_packets)
    return analytics_response
