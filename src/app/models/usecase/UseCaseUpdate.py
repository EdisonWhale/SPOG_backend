"""
Partial update model for UseCase entities.

Every field is optional so the system can update only the fields that change.
The use case ``id`` is path/key controlled and is never set through this model.
"""

from typing import Optional
from datetime import date

from pydantic import Field

from app.models.base.CustomBaseModel import CustomBaseModel
from app.enum import UseCaseStatusEnum


class UseCaseUpdate(CustomBaseModel):
    """Partial update fields for a use case. All fields optional."""

    usecase_id: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Use case ID (#SCTASK id). Supplied by the system as a string (not a UUID)."
    )
    name: Optional[str] = Field(
        default=None, 
        min_length=1, 
        max_length=255, 
        description="Use case name"
    )
    status: Optional[UseCaseStatusEnum] = Field(
        default=None,
        description="AI Governance status"
    )
    ai_governance_request_date: Optional[date] = Field(
        default=None, 
        description="AI Governance request date"
    )
    ai_governance_approval_date: Optional[date] = Field(
        default=None, 
        description="AI Governance approval date"
    )
    business_owner: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Business owner name"
    )
    business_owner_email: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Business owner email"
    )
    vp_sponsor: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="VP sponsor name"
    )
    vp_sponsor_email: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="VP sponsor email"
    )
