from enum import Enum

class UseCaseStatus(str, Enum):
    """Use case approval status."""
    PENDING = "Pending"
    APPROVED = "Approved"
