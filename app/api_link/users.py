from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from ..data import USERS
from ..schemas.user import CreateUserInput, UserResponse

router = APIRouter(tags=["users"])


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
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "active",
    }
    USERS.append(new_user)
    return UserResponse(**new_user)
