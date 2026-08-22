from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from ..clients.supabase_client import get_supabase_client
from ..clients.mock_iot_client import fetch_timeseries_telemetry
from ..data import PROPERTY_ID
from ..schemas import IngestTelemetryResponse, RawTelemetryQueryResponse, TelemetryPacket

RAW_TELEMETRY_DB: list[dict[str, Any]] = []


def _persist_raw_telemetry_to_supabase(records: list[dict[str, Any]]) -> None:
    sb = get_supabase_client()
    if not sb or not records:
        return

    packet_rows = [
        {
            "id": record["id"],
            "property_id": record["property_id"],
            "date": record["date"],
            "weather": record["weather"],
            "timestamp": record["timestamp"],
            "provider": record["provider"],
            "external_packet_id": record["external_packet_id"],
            "raw_payload": record["raw_payload"],
            "created_at": record["created_at"],
        }
        for record in records
    ]
    packet_result = sb.from_("raw_iot_telemetry_packets").insert(packet_rows).execute()
    if packet_result.error:
        print(f"[Supabase] Warning inserting raw telemetry packets: {packet_result.error}")
        return

    device_tables = {
        "grid_meter": "raw_grid_meter_telemetry",
        "solar_inverter": "raw_solar_inverter_telemetry",
        "battery_bms": "raw_battery_bms_telemetry",
    }
    for payload_key, table_name in device_tables.items():
        rows = []
        for record in records:
            device_payload = record.get(payload_key)
            if not device_payload:
                continue
            rows.append(
                {
                    **device_payload,
                    "packet_id": record["id"],
                    "property_id": record["property_id"],
                    "provider": record["provider"],
                    "external_packet_id": record["external_packet_id"],
                    "created_at": record["created_at"],
                }
            )
        if rows:
            result = sb.from_(table_name).insert(rows).execute()
            if result.error:
                print(f"[Supabase] Warning inserting {table_name}: {result.error}")


def _query_raw_telemetry_from_supabase(date_str: Optional[str] = None) -> RawTelemetryQueryResponse | None:
    sb = get_supabase_client()
    if not sb:
        return None

    query = sb.from_("raw_iot_telemetry_packets").select("date,raw_payload,timestamp").order("timestamp", desc=True)
    if date_str:
        query = query.eq("date", date_str)
    result = query.execute()
    if result.error:
        print(f"[Supabase] Warning querying raw telemetry packets: {result.error}")
        return None
    telemetry_packets = [TelemetryPacket(**row["raw_payload"]) for row in result.data]
    return RawTelemetryQueryResponse(date=date_str, count=len(telemetry_packets), data=telemetry_packets)


async def ingest_raw_telemetry(date_str: str, weather: str) -> IngestTelemetryResponse:
    raw_packets = await fetch_timeseries_telemetry(date_str=date_str, weather=weather)
    ingested_at = datetime.now(timezone.utc).isoformat()
    parsed_records: list[TelemetryPacket] = []
    records_to_persist: list[dict[str, Any]] = []

    for packet in raw_packets:
        packet_id = str(uuid4())
        external_packet_id = packet.get("external_packet_id") or f"{date_str}:{weather}:{packet.get('timestamp')}"
        record = {
            "id": packet_id,
            "property_id": PROPERTY_ID,
            "date": date_str,
            "weather": weather,
            "timestamp": packet.get("timestamp"),
            "provider": "mock_iot",
            "external_packet_id": external_packet_id,
            "raw_payload": packet,
            "grid_meter": packet.get("grid_meter"),
            "solar_inverter": packet.get("solar_inverter"),
            "battery_bms": packet.get("battery_bms"),
            "created_at": ingested_at,
        }
        RAW_TELEMETRY_DB.append(record)
        records_to_persist.append(record)
        parsed_records.append(TelemetryPacket(**packet))

    _persist_raw_telemetry_to_supabase(records_to_persist)

    return IngestTelemetryResponse(
        status="success",
        message=f"Successfully ingested {len(parsed_records)} raw IoT telemetry packets into database",
        date=date_str,
        weather=weather,
        count=len(parsed_records),
        ingested_at=ingested_at,
        records=parsed_records,
    )


def query_raw_telemetry(date_str: Optional[str] = None) -> RawTelemetryQueryResponse:
    supabase_response = _query_raw_telemetry_from_supabase(date_str)
    if supabase_response is not None:
        return supabase_response

    records = [r for r in RAW_TELEMETRY_DB if r["date"] == date_str] if date_str else list(RAW_TELEMETRY_DB)
    telemetry_packets = [TelemetryPacket(**r["raw_payload"]) for r in records]
    return RawTelemetryQueryResponse(date=date_str, count=len(telemetry_packets), data=telemetry_packets)
