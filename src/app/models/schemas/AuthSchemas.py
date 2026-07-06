from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


class CurrentUserResponse(BaseModel):
    """
    Response model for the current authenticated user.

    Fields:
        user: stable security identifier of the current user (the token's
            ``oid`` / object ID claim)
        name: display name of the current user (if present in the token)
        email: email address of the current user (if present in the token)

    Example:
        GET /auth/me
        {
            "user": "00000000-0000-0000-0000-000000000000",
            "name": "Test User",
            "email": "test_user@aips.org"
        }

    usage:
        - Returned by GET /auth/me
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": "00000000-0000-0000-0000-000000000000",
                "name": "Test User",
                "email": "test_user@aips.org",
            }
        }
    )

    user: str = Field(
        ...,
        description="Stable security identifier (oid) of the current user.",
        examples=["00000000-0000-0000-0000-000000000000"],
    )

    name: Optional[str] = Field(
        default=None,
        description="Display name of the current user.",
        examples=["Test User"],
    )

    email: Optional[str] = Field(
        default=None,
        description="Email address of the current user.",
        examples=["test_user@aips.org"],
    )
