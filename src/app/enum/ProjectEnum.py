from enum import Enum

class GitlabSyncRequestedStatusEnum(str, Enum):
    """Primary input channels for agent data ingestion."""

    PENDING = "Pending"
    RUNNING = "Running"
    COMPLETED = "Completed"
