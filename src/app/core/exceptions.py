"""
Shared exception hierarchy for service layer.

These exceptions are raised by service classes and caught by routers
to be converted into appropriate HTTP responses with CommonErrorResponse.
"""

class ServiceException(Exception):
    """Base exception for service layer errors"""
    def __init__(self, error_code: str, error_type: str, error_message: str):
        self.error_code = error_code
        self.error_type = error_type
        self.error_message = error_message
        super().__init__(self.error_message)


class ValidationException(ServiceException):
    """Exception for validation errors - maps to HTTP 400"""
    def __init__(self, error_message: str):
        super().__init__(
            error_code="ValidationError",
            error_type="Validation",
            error_message=error_message
        )


class NotFoundException(ServiceException):
    """Exception for resource not found errors - maps to HTTP 404"""
    def __init__(self, resource_type: str, resource_id: str):
        error_message = f"{resource_type} with ID '{resource_id}' not found."
        super().__init__(
            error_code="NotFound",
            error_type="NotFound",
            error_message=error_message
        )

class ConflictException(ServiceException):
    """Exception for resource conflict errors - maps to HTTP 409"""
    def __init__(self, error_message: str):
        super().__init__(
            error_code="Conflict",
            error_type="Conflict",
            error_message=error_message
        )
        
class SystemException(ServiceException):
    """Exception for system/database errors - maps to HTTP 500"""
    def __init__(self, error_message: str, original_error: Exception = None):
        full_message = error_message
        if original_error:
            full_message = f"{error_message}: {str(original_error)}"
        super().__init__(
            error_code="Internal Server Error",
            error_type="System",
            error_message=full_message
        )
