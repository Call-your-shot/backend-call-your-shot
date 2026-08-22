"""Supabase persistence adapter for green credits.

The database RPCs own all balance-changing transactions. This adapter only
maps authenticated FastAPI calls to RLS-protected reads and atomic RPCs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol


@dataclass
class GreenCreditRepositoryError(Exception):
    message: str
    status_code: int = 500
    code: str = "GREEN_CREDIT_STORAGE_ERROR"

    def __str__(self) -> str:
        return self.message


class GreenCreditRepository(Protocol):
    def get_wallet(self) -> dict[str, Any] | None: ...

    def list_ledger(
        self, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]: ...

    def list_allocations(
        self, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]: ...

    def list_projects(
        self, status: str | None, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]: ...

    def get_project(self, project_id: str) -> dict[str, Any] | None: ...

    def allocate(
        self, project_id: str, requested_microcredits: int, idempotency_key: str
    ) -> dict[str, Any]: ...

    def accrue(
        self, property_id: str, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]: ...


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise GreenCreditRepositoryError(
            f"Missing required environment variable: {name}",
            status_code=503,
            code="GREEN_CREDIT_NOT_CONFIGURED",
        )
    return value


def _map_storage_error(exc: Exception) -> GreenCreditRepositoryError:
    message = getattr(exc, "message", None) or str(exc)
    code = str(getattr(exc, "code", "") or "")
    lowered = message.lower()
    if "not found" in lowered or code == "P0002":
        return GreenCreditRepositoryError(message, 404, "NOT_FOUND")
    if "insufficient" in lowered:
        return GreenCreditRepositoryError(message, 409, "INSUFFICIENT_BALANCE")
    if "not open" in lowered or "fully funded" in lowered:
        return GreenCreditRepositoryError(message, 409, "PROJECT_NOT_OPEN")
    if "idempotency" in lowered or code == "23505":
        return GreenCreditRepositoryError(message, 409, "IDEMPOTENCY_CONFLICT")
    if "minimum" in lowered or code == "22023":
        return GreenCreditRepositoryError(message, 422, "VALIDATION_ERROR")
    if "authentication" in lowered or code == "28000":
        return GreenCreditRepositoryError(message, 401, "AUTHENTICATION_ERROR")
    return GreenCreditRepositoryError(message)


class SupabaseGreenCreditRepository:
    def __init__(self, client: Any, user_id: str | None = None) -> None:
        self.client = client
        self.user_id = user_id

    @staticmethod
    def _data(response: Any) -> Any:
        return getattr(response, "data", None)

    def get_wallet(self) -> dict[str, Any] | None:
        if not self.user_id:
            raise GreenCreditRepositoryError(
                "Authenticated user id is unavailable", 401, "AUTHENTICATION_ERROR"
            )
        try:
            response = (
                self.client.table("green_credit_wallets")
                .select("*")
                .eq("user_id", self.user_id)
                .limit(1)
                .execute()
            )
            rows = self._data(response) or []
            return rows[0] if rows else None
        except Exception as exc:  # pragma: no cover - exercised via fake adapter
            raise _map_storage_error(exc) from exc

    def list_ledger(self, limit: int, cursor: datetime | None) -> list[dict[str, Any]]:
        wallet = self.get_wallet()
        if wallet is None:
            return []
        try:
            query = (
                self.client.table("green_credit_ledger_entries")
                .select("*")
                .eq("account_id", wallet["account_id"])
                .order("created_at", desc=True)
                .order("id", desc=True)
                .limit(limit)
            )
            if cursor is not None:
                query = query.lt("created_at", cursor.isoformat())
            return self._data(query.execute()) or []
        except Exception as exc:  # pragma: no cover
            raise _map_storage_error(exc) from exc

    def list_allocations(
        self, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]:
        if not self.user_id:
            raise GreenCreditRepositoryError(
                "Authenticated user id is unavailable", 401, "AUTHENTICATION_ERROR"
            )
        try:
            query = (
                self.client.table("green_project_allocations")
                .select("*")
                .eq("user_id", self.user_id)
                .order("allocated_at", desc=True)
                .order("id", desc=True)
                .limit(limit)
            )
            if cursor is not None:
                query = query.lt("allocated_at", cursor.isoformat())
            return self._data(query.execute()) or []
        except Exception as exc:  # pragma: no cover
            raise _map_storage_error(exc) from exc

    def list_projects(
        self, status: str | None, limit: int, cursor: datetime | None
    ) -> list[dict[str, Any]]:
        try:
            query = (
                self.client.table("green_project_funding")
                .select("*")
                .neq("status", "draft")
                .order("created_at", desc=True)
                .order("id", desc=True)
                .limit(limit)
            )
            if status is not None:
                query = query.eq("status", status)
            if cursor is not None:
                query = query.lt("created_at", cursor.isoformat())
            return self._data(query.execute()) or []
        except Exception as exc:  # pragma: no cover
            raise _map_storage_error(exc) from exc

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        try:
            response = (
                self.client.table("green_project_funding")
                .select("*")
                .eq("id", project_id)
                .neq("status", "draft")
                .limit(1)
                .execute()
            )
            rows = self._data(response) or []
            return rows[0] if rows else None
        except Exception as exc:  # pragma: no cover
            raise _map_storage_error(exc) from exc

    def allocate(
        self, project_id: str, requested_microcredits: int, idempotency_key: str
    ) -> dict[str, Any]:
        try:
            response = self.client.rpc(
                "allocate_green_credits",
                {
                    "target_project_id": project_id,
                    "requested_microcredits": requested_microcredits,
                    "request_idempotency_key": idempotency_key,
                },
            ).execute()
            return self._data(response) or {}
        except Exception as exc:  # pragma: no cover
            raise _map_storage_error(exc) from exc

    def accrue(
        self, property_id: str, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        try:
            response = self.client.rpc(
                "accrue_green_credits",
                {
                    "target_property_id": property_id,
                    "period_start": period_start.isoformat(),
                    "period_end": period_end.isoformat(),
                },
            ).execute()
            return self._data(response) or {}
        except Exception as exc:  # pragma: no cover
            raise _map_storage_error(exc) from exc


def create_user_repository(access_token: str) -> SupabaseGreenCreditRepository:
    try:
        from supabase import create_client

        client = create_client(
            _required_env("SUPABASE_URL"),
            _required_env("SUPABASE_PUBLISHABLE_KEY"),
        )
        user_response = client.auth.get_user(access_token)
        user = getattr(user_response, "user", None)
        if user is None:
            raise GreenCreditRepositoryError(
                "Invalid or expired bearer token", 401, "AUTHENTICATION_ERROR"
            )
        client.postgrest.auth(access_token)
        return SupabaseGreenCreditRepository(client, str(user.id))
    except GreenCreditRepositoryError:
        raise
    except Exception as exc:
        raise GreenCreditRepositoryError(
            "Invalid or expired bearer token", 401, "AUTHENTICATION_ERROR"
        ) from exc


def create_service_repository() -> SupabaseGreenCreditRepository:
    try:
        from supabase import create_client

        client = create_client(
            _required_env("SUPABASE_URL"), _required_env("SUPABASE_SECRET_KEY")
        )
        return SupabaseGreenCreditRepository(client)
    except GreenCreditRepositoryError:
        raise
    except Exception as exc:
        raise GreenCreditRepositoryError(
            "Unable to initialize Supabase service client",
            503,
            "GREEN_CREDIT_NOT_CONFIGURED",
        ) from exc
