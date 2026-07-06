from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CommonErrorResponse(BaseModel):
    """
    Standardized error response schema used across all endpoints.
    Follows RFC 7807 Problem Details format.
    """
    error: str = Field(
        ...,
        description="A general error code or title (e.g., 'ValidationError', 'NotFound', 'Unauthorized')"
    )
    errorType: str = Field(
        ...,
        description="The type of error (e.g., 'Validation', 'Authentication', 'Authorization', 'System', 'NotFound')"
    )
    errorMessage: str = Field(
        ...,
        description="A detailed message describing the error and how to resolve it"
    )


# ---------------------------------------------------------------------------
# Reusable OpenAPI ``responses`` building blocks.
#
# Every API method documents a standard set of error responses so the generated
# OpenAPI contract is consistent and API-management/gateway tooling can rely on
# them:
#   - 400 Bad Request           (malformed request / validation)
#   - 401 Unauthorized          (missing or invalid bearer token)
#   - 403 Forbidden             (authenticated but not the owner) -- only on
#                                endpoints whose backend actually enforces
#                                ownership (write / owner-scoped operations)
#   - 429 Too Many Requests     (rate limit for commercialized API products)
#
# Spread these into a route's ``responses={...}`` with ``**COMMON_ERROR_RESPONSES``
# (reads) or ``**COMMON_OWNED_ERROR_RESPONSES`` (writes / owner-scoped) and then
# add the endpoint-specific entries (404, 409, ...).
# ---------------------------------------------------------------------------

ERROR_400 = {"model": CommonErrorResponse, "description": "Bad request"}
ERROR_401 = {"model": CommonErrorResponse, "description": "Missing or invalid token"}
ERROR_403 = {"model": CommonErrorResponse, "description": "Forbidden (not the owner)"}
ERROR_429 = {
    "model": CommonErrorResponse,
    "description": "Too many requests (rate limit exceeded)",
}
ERROR_500 = {"model": CommonErrorResponse, "description": "Server error"}

# For read / non-owner-scoped endpoints (no 403, since the backend does not
# enforce ownership on these).
COMMON_ERROR_RESPONSES = {
    400: ERROR_400,
    401: ERROR_401,
    429: ERROR_429,
    500: ERROR_500,
}

# For write / owner-scoped endpoints, which can additionally return 403.
COMMON_OWNED_ERROR_RESPONSES = {
    400: ERROR_400,
    401: ERROR_401,
    403: ERROR_403,
    429: ERROR_429,
    500: ERROR_500,
}


class SuccessResponse(BaseModel):
    """Generic success response wrapper"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Operation completed successfully"
            }
        }
    )

    message: str = Field(..., description="Success message")


class CountResponse(BaseModel):
    """Response for count operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "count": 3
            }
        }
    )

    count: int = Field(..., ge=0, description="The number of matching resources")


class DeleteResponse(BaseModel):
    """Response for delete operations"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Resource deleted successfully"
            }
        }
    )

    deleted: Optional[bool] = True
    message: str = Field(..., description="Deletion confirmation message")
