from enum import Enum

class UseCaseStatusEnum(str, Enum):
    """Use case approval status."""
    PENDING = "Pending"
    SUBMITTED = "Submitted"
    ASSIGNED = "Assigned"
    IN_PROGRESS = "In Progress"
    APPROVED = "Approved"
