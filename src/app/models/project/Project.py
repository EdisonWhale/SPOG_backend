import uuid
from datetime import date
from typing import ClassVar, Optional
from pydantic import Field, field_validator
from app.models.base.SpogBaseModel import SpogBaseModel
from app.enum import GitlabSyncRequestedStatusEnum

class Project(SpogBaseModel):

    COLLECTION_NAME: ClassVar[str] = "Projects"

    # Core identification
    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="System-generated ID of the project. Must not be supplied by the client.",
    )
    name: str = Field(
        ...,
        min_length=4,
        max_length=50,
        description="Project name"
    )
    purpose: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Project purpose"
    )

    # Business stakeholders
    business_owner: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Business owner name"
    )
    business_owner_email: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Business owner email"
    )

    # Product stakeholders
    product_owner: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Product owner name"
    )
    product_owner_email: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Product owner email"
    )

    # Technical stakeholders
    technical_owner: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Technical owner name"
    )
    technical_owner_email: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Technical owner email"
    )

    # Executive sponsor
    vp_sponsor: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="VP sponsor name"
    )
    vp_sponsor_email: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="VP sponsor email"
    )
    active: Optional[bool] = Field(
        default=False,
        description="Is the project active?",
    )
    locked: Optional[bool] = Field(
        default=False,
        description="After an use case get submitted then project becomes locked",
    )
    gitlab_sync_requested_status: Optional[GitlabSyncRequestedStatusEnum] = Field(
        default=None,
        description="Status of the last GitLab sync request.",
    )
    gitlab_sync_requested_at: Optional[date] = Field(
        default=None,
        description="Timestamp when the user last requested an on-demand GitLab sync.",
    )

    @field_validator("business_owner_email", "product_owner_email", "technical_owner_email", "vp_sponsor_email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        """Validate email format."""
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v
