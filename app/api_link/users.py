from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, status

from ..data import SUPPORT_REPORTS, USER_PREFERENCES, USERS
from ..schemas.frontend import SupportReportInput, UserPreferencesInput
from ..schemas.user import CreateUserInput, UpdateUserProfileInput, UserProfileResponse, UserResponse

router = APIRouter(tags=["users"])


def _display_name(email: str) -> str:
    return email.split("@", 1)[0].replace(".", " ").replace("_", " ").title()


def _profile(user: dict) -> UserProfileResponse:
    name = user.get("full_name") or _display_name(user["email"])
    initials = "".join(part[0] for part in name.split()[:2]).upper()
    return UserProfileResponse(**{**user, "full_name": name, "avatar_initials": initials})


@router.post("/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: CreateUserInput) -> UserResponse:
    email_str = payload.email.lower()
    for existing_user in USERS:
        if existing_user["email"].lower() == email_str:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

    new_user = {
        "id": str(uuid4()),
        "email": payload.email,
        "full_name": _display_name(payload.email),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    USERS.append(new_user)
    return UserResponse(**new_user)


@router.get("/api/v1/users/profile", response_model=UserProfileResponse)
def get_user_profile(email: str = Query(..., min_length=3)) -> UserProfileResponse:
    for user in USERS:
        if user["email"].lower() == email.strip().lower():
            return _profile(user)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.patch("/api/v1/users/profile", response_model=UserProfileResponse)
def update_user_profile(payload: UpdateUserProfileInput) -> UserProfileResponse:
    for user in USERS:
        if user["email"].lower() == payload.email.strip().lower():
            user["full_name"] = payload.full_name.strip()
            user["phone"] = payload.phone
            return _profile(user)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("/api/v1/users/preferences")
def get_user_preferences(email: str = Query(..., min_length=3)) -> dict:
    return USER_PREFERENCES.get(
        email.strip().lower(),
        {
            "notifications": {"statement-ready": True, "output-alerts": True, "plan-changes": True},
            "language": "en-AU",
            "largeText": False,
            "reduceMotion": False,
        },
    )


@router.put("/api/v1/users/preferences")
def update_user_preferences(payload: UserPreferencesInput) -> dict:
    data = payload.model_dump(by_alias=True, exclude={"email"})
    USER_PREFERENCES[payload.email.strip().lower()] = data
    return data


@router.get("/api/v1/support-reports")
def list_support_reports(email: str = Query(..., min_length=3)) -> dict:
    return {
        "data": [
            {key: value for key, value in report.items() if key != "email"}
            for report in SUPPORT_REPORTS
            if report["email"] == email.strip().lower()
        ]
    }


@router.post("/api/v1/support-reports", status_code=status.HTTP_201_CREATED)
def create_support_report(payload: SupportReportInput) -> dict:
    now = datetime.now(timezone.utc)
    report = {
        "id": str(uuid4()),
        "reference": f"SR-{now.year}-{len(SUPPORT_REPORTS) + 1:04d}",
        "email": payload.email.strip().lower(),
        "propertyId": payload.property_id,
        "category": payload.category,
        "description": payload.description,
        "contactPreference": payload.contact_preference,
        "attachmentName": payload.attachment_name,
        "status": "Open",
        "submittedAt": now.date().isoformat(),
    }
    SUPPORT_REPORTS.insert(0, report)
    return {key: value for key, value in report.items() if key != "email"}
