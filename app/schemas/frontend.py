from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import Field

from .common import ApiModel


class PlanLeaveRequestInput(ApiModel):
    email: str = Field(min_length=3)
    move_out_date: date = Field(alias="moveOutDate")
    reason: str = Field(min_length=1, max_length=500)
    note: Optional[str] = Field(default=None, max_length=1000)


class OwnerEmailInput(ApiModel):
    email: str = Field(min_length=3)


class PropertyInviteInput(ApiModel):
    email: str = Field(min_length=3)
    invite_email: str = Field(min_length=3, alias="inviteEmail")


class InviteAcceptInput(ApiModel):
    email: str = Field(min_length=3)


class CreateFrontendPropertyInput(ApiModel):
    email: str = Field(min_length=3)
    address: str = Field(min_length=3, max_length=500)
    invite_email: Optional[str] = Field(default=None, alias="inviteEmail")
    solar_system: Optional[dict] = Field(default=None, alias="solarSystem")


class UserPreferencesInput(ApiModel):
    email: str = Field(min_length=3)
    notifications: dict[str, bool] = Field(default_factory=dict)
    language: str = "en-AU"
    large_text: bool = Field(default=False, alias="largeText")
    reduce_motion: bool = Field(default=False, alias="reduceMotion")


class SupportReportInput(ApiModel):
    email: str = Field(min_length=3)
    property_id: Optional[str] = Field(default=None, alias="propertyId")
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=4000)
    contact_preference: str = Field(default="email", alias="contactPreference")
    attachment_name: Optional[str] = Field(default=None, alias="attachmentName")
