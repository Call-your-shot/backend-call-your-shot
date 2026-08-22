from __future__ import annotations

from fastapi import APIRouter

from ..clients.supabase_client import check_postgres_connection

router = APIRouter(prefix="/api/supabase", tags=["supabase"])


@router.get("/health")
def supabase_health() -> dict:
    return check_postgres_connection()
