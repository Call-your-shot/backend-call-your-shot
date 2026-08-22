import os
from typing import Any
import httpx
from fastapi import HTTPException, status


def get_mock_iot_api_url() -> str:
    url = os.getenv("MOCK_IOT_API_URL", "http://localhost:8000").rstrip("/")
    return url


async def fetch_timeseries_telemetry(date_str: str, weather: str) -> list[dict[str, Any]]:
    base_url = get_mock_iot_api_url()
    endpoint = f"{base_url}/api/v1/telemetry/timeseries"
    params = {
        "date": date_str,
        "interval_minutes": 60,
        "weather": weather,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError("Expected a list of telemetry packets")
            return data
    except (httpx.HTTPError, httpx.RequestError, ValueError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch telemetry from external IoT mock server ({base_url}): {str(exc)}",
        ) from exc
