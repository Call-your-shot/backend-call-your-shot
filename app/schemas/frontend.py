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
