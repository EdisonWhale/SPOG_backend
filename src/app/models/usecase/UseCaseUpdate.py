"""
Partial update model for UseCase entities.

Every field is optional so the system can update only the fields that change.
The use case ``id`` is path/key controlled and is never set through this model.
"""

from typing import Optional
from datetime import date

from pydantic import Field

from app.models.base.CustomBaseModel import CustomBaseModel
from app.enum import UseCaseStatus


class UseCaseUpdate(CustomBaseModel):
    """Partial update fields for a use case. All fields optional."""

    usecase_id: Optional[str] = Field(..., min_length=1, description="Use case ID (#SCTASK id). Supplied by the system as a string (not a UUID).")
    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Use case name")
    status: Optional[UseCaseStatus] = Field(default=None, description="AI Governance status")
    ai_governance_intake_form_number: Optional[str] = Field(
        default=None, description="AI Governance intake form number"
    )
    ai_governance_request_date: Optional[date] = Field(
        default=None, description="AI Governance request date"
    )
    ai_governance_approval_date: Optional[date] = Field(
        default=None, description="AI Governance approval date"
    )
