from enum import Enum

class JobTriggerEnum(str, Enum):
    AUTO = "Auto"
    MANUAL = "Manual"


class JobStatusEnum(str, Enum):
    PENDING = "Pending"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"

