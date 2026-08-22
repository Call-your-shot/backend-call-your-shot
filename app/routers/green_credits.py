"""Authenticated green-credit wallet and curated-project API."""

from __future__ import annotations

import hmac
import os
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..demo_green_credit_repository import create_demo_repository
from ..green_credit_models import (
    AccrualRequest,
    AccrualResponse,
    AllocationPageResponse,
    AllocationRequest,
    AllocationResponse,
    GreenProjectResponse,
    LedgerPageResponse,
    ProjectPageResponse,
    WalletResponse,
)
from ..green_credit_repository import (
    GreenCreditRepository,
    GreenCreditRepositoryError,
    create_service_repository,
    create_user_repository,
)
from ..green_credit_service import (
    accrue_period,
    allocate_to_project,
    build_allocation_page,
    build_ledger_page,
    build_project,
    build_project_page,
    build_wallet,
)
from ..green_credits import credits_to_microcredits

router = APIRouter(tags=["green credits"])
bearer = HTTPBearer(auto_error=False)


def _demo_email_auth_enabled() -> bool:
    configured = os.getenv("GREEN_CREDIT_DEMO_AUTH")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return os.getenv("APP_ENV", "development").strip().lower() not in {
        "production",
        "prod",
    }


def _http_error(error: GreenCreditRepositoryError) -> HTTPException:
    return HTTPException(
        status_code=error.status_code,
        detail={"code": error.code, "message": error.message},
    )


def get_user_green_credit_repository(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    email: Annotated[
        str | None,
        Query(
            min_length=3,
            max_length=254,
            pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            description=(
                "Email-only identity for the local/demo frontend. Production "
                "clients should send a Supabase bearer token instead."
            ),
        ),
    ] = None,
) -> GreenCreditRepository:
    if credentials is not None:
        if credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": "AUTHENTICATION_ERROR",
                    "message": "A valid Supabase bearer token is required.",
                },
            )
        try:
            return create_user_repository(credentials.credentials)
        except GreenCreditRepositoryError as error:
            raise _http_error(error) from error

    if email is not None and _demo_email_auth_enabled():
        return create_demo_repository(email)

    message = "A Supabase bearer token is required."
    if _demo_email_auth_enabled():
        message = "A Supabase bearer token or demo email query parameter is required."
    elif email is not None:
        message = "Email-only demo authentication is disabled in this environment."
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "AUTHENTICATION_ERROR",
            "message": message,
        },
    )


def get_service_green_credit_repository(
    x_internal_api_key: Annotated[
        str | None, Header(alias="X-Internal-API-Key")
    ] = None,
) -> GreenCreditRepository:
    configured_key = os.getenv("GREEN_CREDIT_INTERNAL_KEY")
    if (
        not configured_key
        or not x_internal_api_key
        or not hmac.compare_digest(configured_key, x_internal_api_key)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "INTERNAL_AUTHORIZATION_ERROR",
                "message": "A valid internal API key is required.",
            },
        )
    try:
        return create_service_repository()
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error


UserRepository = Annotated[
    GreenCreditRepository, Depends(get_user_green_credit_repository)
]
ServiceRepository = Annotated[
    GreenCreditRepository, Depends(get_service_green_credit_repository)
]


@router.get(
    "/api/v1/green-credits/wallet",
    response_model=WalletResponse,
    summary="Get the caller's green-credit wallet",
)
def wallet(repository: UserRepository) -> WalletResponse:
    try:
        return build_wallet(repository)
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error


@router.get(
    "/api/v1/green-credits/ledger",
    response_model=LedgerPageResponse,
    summary="List immutable green-credit transactions",
)
def ledger(
    repository: UserRepository,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: datetime | None = None,
) -> LedgerPageResponse:
    try:
        return build_ledger_page(repository, limit, cursor)
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error


@router.get(
    "/api/v1/green-credits/allocations",
    response_model=AllocationPageResponse,
    summary="List the caller's green-project allocations",
)
def allocations(
    repository: UserRepository,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: datetime | None = None,
) -> AllocationPageResponse:
    try:
        return build_allocation_page(repository, limit, cursor)
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error


@router.get(
    "/api/v1/green-projects",
    response_model=ProjectPageResponse,
    summary="Browse the curated green-project catalog",
)
def projects(
    repository: UserRepository,
    project_status: Annotated[
        Literal["open", "funded", "active", "completed", "cancelled"] | None,
        Query(alias="status"),
    ] = "open",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: datetime | None = None,
) -> ProjectPageResponse:
    try:
        return build_project_page(repository, project_status, limit, cursor)
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error


@router.get(
    "/api/v1/green-projects/{project_id}",
    response_model=GreenProjectResponse,
    summary="Get one curated green project",
)
def project(project_id: UUID, repository: UserRepository) -> GreenProjectResponse:
    try:
        result = build_project(repository, str(project_id))
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Green project not found."},
        )
    return result


@router.post(
    "/api/v1/green-projects/{project_id}/allocations",
    response_model=AllocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Permanently allocate green credits to a project",
)
def allocate(
    project_id: UUID,
    request: AllocationRequest,
    repository: UserRepository,
) -> AllocationResponse:
    try:
        return allocate_to_project(
            repository,
            str(project_id),
            credits_to_microcredits(request.requested_credits),
            request.idempotency_key,
        )
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error


@router.post(
    "/api/v1/internal/green-credits/accrue",
    response_model=AccrualResponse,
    summary="Accrue credits from finalized normalized readings",
)
def accrue(request: AccrualRequest, repository: ServiceRepository) -> AccrualResponse:
    try:
        return accrue_period(
            repository,
            str(request.property_id),
            request.period_start,
            request.period_end,
        )
    except GreenCreditRepositoryError as error:
        raise _http_error(error) from error
