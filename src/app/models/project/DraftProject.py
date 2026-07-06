import uuid
from typing import ClassVar, Optional
from pydantic import Field, field_validator
from app.models.base.SpogBaseModel import SpogBaseModel

class DraftProject(SpogBaseModel):
    """
    Draft project model for partial project creation.
    Only id and name are mandatory; all other fields are optional.
    """

    COLLECTION_NAME: ClassVar[str] = "DraftProjects"

    # Core identification - MANDATORY
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
    # Project details - OPTIONAL
    purpose: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Project purpose"
    )

    # Business stakeholders - OPTIONAL
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

    # Product stakeholders - OPTIONAL
    product_owner: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Product owner name"
    )
    product_owner_email: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Product owner email"
    )

    # Technical stakeholders - OPTIONAL
    technical_owner: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Technical owner name"
    )
    technical_owner_email: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=100,
        description="Technical owner email"
    )

    # Executive sponsor - OPTIONAL
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

    @field_validator("business_owner_email", "product_owner_email", "technical_owner_email", "vp_sponsor_email")
    @classmethod
    def validate_email_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate email format. Optional fields may be omitted (None)."""
        if v is None:
            return v
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Invalid email format")
        return v
