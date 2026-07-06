from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Any

from app.models import CommonErrorResponse
from app.core.exceptions import (
    ServiceException,
    ValidationException,
    NotFoundException,
    ConflictException
)
from app.models import AuthorizableModel

def get_authorizable_exclusions() -> dict:
    """Get exclusion dict for AuthorizableModel fields."""
    return {field: True for field in AuthorizableModel.model_fields.keys()}

def handle_service_exception(exc: ServiceException):
    """
    Convert service layer exceptions to FastAPI JSONResponse

    Parameters:
    ----------
    exc : ServiceException
        The service exception to convert

    Returns
    ------
    JSONResponse
        CommonErrorResponse format with error details
    """
    error_response = CommonErrorResponse(
        error=exc.error_code,
        errorType=exc.error_type,
        errorMessage=exc.error_message
    )

    if isinstance(exc, ValidationException):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_response.model_dump()
        )
    elif isinstance(exc, NotFoundException):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response.model_dump()
        )
    elif isinstance(exc, ConflictException):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=error_response.model_dump()
        )
    else:   #SystemException
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump()
        )

def create_error_response(
        status_code: int,
        description: str,
        examples: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Helper function to create standardized error response configuration

    Args:
        status_code: HTTP status code
        description: Description of the error type
        examples: Dictionary of example responses

    Returns:
        Response configuration dict for FastAPI
    """
    return {
        "model": CommonErrorResponse,
        "description": description,
        "content": {
            "application/json": {
                "examples": examples
            }
        }
    }


# Predefined error response examples --- used ONLY for API SPECS
ERROR_RESPONSES = {
    400: create_error_response(
        status_code=400,
        description="Bad Request - Invalid input",
        examples={
            "validation_error": {
                "summary": "Validation Error",
                "value": {
                    "error": "Bad Request",
                    "errorType": "Validation",
                    "errorMessage": "Field 'call_duration_seconds' must be valid positive integer"
                }
            }
        }
    ),
    401: create_error_response(
        status_code=401,
        description="Unauthorized - Authentication required",
        examples={
            "missing_token": {
                "summary": "Missing Token",
                "value": {
                    "error": "Unauthorized",
                    "errorType": "Authentication",
                    "errorMessage": "Authentication token is required"
                }
            },
            "invalid_token": {
                "summary": "Invalid Token",
                "value": {
                    "error": "Unauthorized",
                    "errorType": "Authentication",
                    "errorMessage": "Invalid or expired authentication token"
                }
            }
        }
    ),
    403: create_error_response(
        status_code=403,
        description="Forbidden - Insufficient permissions",
        examples={
            "insufficient_permissions": {
                "summary": "Insufficient Permissions",
                "value": {
                    "error": "Forbidden",
                    "errorType": "Forbidden",
                    "errorMessage": "API endpoint valid but not accessible by requesting consumer"
                }
            }
        }
    ),
    404: create_error_response(
        status_code=404,
        description="Not Found - Resource doesn't exist",
        examples={
            "resource_not_found": {
                "summary": "Resource Not Found",
                "value": {
                    "error": "NotFound",
                    "errorType": "NotFound",
                    "errorMessage": "The requested resource does not exist"
                }
            }
        }
    ),
    409: create_error_response(
        status_code=409,
        description="Conflict - Resource already exists or is in use",
        examples={
            "resource_conflict": {
                "summary": "Resource Conflict",
                "value": {
                    "error": "Conflict",
                    "errorType": "Conflict",
                    "errorMessage": "Resource already exists or is in use"
                }
            }
        }
    ),
    500: create_error_response(
        status_code=500,
        description="Internal Server Error",
        examples={
            "unexpected_error": {
                "summary": "Unexpected Error",
                "value": {
                    "error": "Internal Server Error",
                    "errorType": "System",
                    "errorMessage": "An unexpected error occurred. Please contact support."
                }
            }
        }
    )
}
