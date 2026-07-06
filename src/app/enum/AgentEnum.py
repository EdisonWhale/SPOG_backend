from enum import Enum

class PlatformEnum(str, Enum):
    """Supported deployment platforms for agents."""

    GCP = "GCP"

class DataLevel(str, Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"

class EnvironmentEnum(str, Enum):
    DEV = "Dev"
    STAGING = "Staging"
    PRODUCTION = "Production"
