import re

from pydantic import Field, field_validator

from .common import ApiModel

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class CreateUserInput(ApiModel):
    email: str = Field(..., description="User email address")

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        if not EMAIL_REGEX.match(value):
            raise ValueError("invalid email format")
        return value


class UserResponse(ApiModel):
    id: str = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    full_name: str | None = Field(default=None, description="User display name")
    created_at: str = Field(..., description="Timestamp when the user was created")
    status: str = Field(default="active", description="User status")


class UpdateUserProfileInput(ApiModel):
    email: str
    full_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


class UserProfileResponse(UserResponse):
    phone: str | None = None
    avatar_initials: str
