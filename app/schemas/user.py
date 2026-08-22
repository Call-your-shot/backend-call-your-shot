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
    created_at: str = Field(..., description="Timestamp when the user was created")
    status: str = Field(default="active", description="User status")

