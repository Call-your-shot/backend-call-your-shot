from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local")


class SupabaseRestClient:
    """Lightweight REST client for Supabase PostgREST endpoints."""

    def __init__(self, url: str, key: str):
        self.url = url.rstrip("/")
        self.key = key
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def table(self, table_name: str) -> SupabaseTableRequestBuilder:
        return SupabaseTableRequestBuilder(self.url, table_name, self.headers)


class SupabaseTableRequestBuilder:

    def __init__(self, base_url: str, table_name: str, headers: dict[str, str]):
        self.endpoint = f"{base_url}/rest/v1/{table_name}"
        self.headers = headers

    def insert(self, rows: list[dict[str, Any]]) -> dict:
        try:
            with httpx.Client(timeout=10.0) as client:
                res = client.post(self.endpoint, json=rows, headers=self.headers)
                if res.is_success:
                    return {"data": res.json(), "error": None}
                return {"data": None, "error": res.text}
        except Exception as exc:
            return {"data": None, "error": str(exc)}

    def select(self, query: str = "*") -> SupabaseQueryBuilder:
        return SupabaseQueryBuilder(self.endpoint, self.headers, select_fields=query)

    def update(self, payload: dict[str, Any]) -> SupabaseQueryBuilder:
        return SupabaseQueryBuilder(self.endpoint, self.headers, update_payload=payload)


class SupabaseQueryBuilder:

    def __init__(self, endpoint: str, headers: dict[str, str], select_fields: str = "*", update_payload: Optional[dict[str, Any]] = None):
        self.endpoint = endpoint
        self.headers = headers
        self.params: dict[str, str] = {"select": select_fields}
        self.update_payload = update_payload

    def eq(self, column: str, value: Any) -> SupabaseQueryBuilder:
        self.params[column] = f"eq.{value}"
        return self

    def execute(self) -> dict:
        try:
            with httpx.Client(timeout=10.0) as client:
                if self.update_payload is not None:
                    res = client.patch(self.endpoint, params=self.params, json=self.update_payload, headers=self.headers)
                else:
                    res = client.get(self.endpoint, params=self.params, headers=self.headers)

                if res.is_success:
                    return {"data": res.json(), "error": None}
                return {"data": [], "error": res.text}
        except Exception as exc:
            return {"data": [], "error": str(exc)}


def get_supabase_client() -> Optional[SupabaseRestClient]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key or "replace-with" in key or "your_secret_key" in key:
        return None

    return SupabaseRestClient(url, key)


def get_database_url() -> Optional[str]:
    database_url = os.getenv("DATABASE_URL")
    if not database_url or "[YOUR-PASSWORD]" in database_url or "YOUR-PASSWORD" in database_url:
        return None
    return database_url


def get_postgres_connection():
    database_url = get_database_url()
    if not database_url:
        return None

    try:
        import psycopg2
    except ImportError as exc:
        raise RuntimeError("psycopg2 is not installed. Run: pip install -r requirements.txt") from exc

    return psycopg2.connect(database_url)


def check_postgres_connection() -> dict[str, Any]:
    database_url = get_database_url()
    if not database_url:
        return {
            "connected": False,
            "configured": False,
            "detail": "DATABASE_URL is not set. Add it to .env or .env.local.",
        }

    try:
        connection = get_postgres_connection()
        if connection is None:
            return {"connected": False, "configured": True, "detail": "Connection was not created."}
        try:
            with connection.cursor() as cursor:
                cursor.execute("select current_database(), current_user, version();")
                database_name, database_user, version = cursor.fetchone()
        finally:
            connection.close()

        return {
            "connected": True,
            "configured": True,
            "database": database_name,
            "user": database_user,
            "version": version,
        }
    except Exception as exc:
        return {
            "connected": False,
            "configured": True,
            "detail": str(exc),
        }
