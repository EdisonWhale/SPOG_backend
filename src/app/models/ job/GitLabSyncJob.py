import uuid
from typing import ClassVar, Optional, List
from app.enum import (
    JobTriggerEnum,
    JobStatusEnum
)
from pydantic import Field
from app.models.base.CustomBaseModel import (
    CustomBaseModel,
    TimestampedModel
)


class JobMetric(CustomBaseModel):
    total_projects: int = 0
    total_agents: int = 0
    promoted_agents: int = 0
    failed_agents: int = 0


class GitLabSyncJob(CustomBaseModel, TimestampedModel):

    COLLECTION_NAME: ClassVar[str] = "Jobs"

    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="System-generated ID of the project. Must not be supplied by the client.",
    )
    trigger: Optional[JobTriggerEnum] = Field(
        default=JobTriggerEnum.AUTO,
        description="Auto or manual trigger",
    )
    trigger_by: Optional[str] = Field(
        default=None,
        description="Need trigger_by for manual trigger",
    )
    status: Optional[JobStatusEnum] = Field(
        default=JobStatusEnum.PENDING,
        description="Gitlab current job status.",
    )
    metric: JobMetric = Field(default_factory=JobMetric)
    failed_agents_id: List[str] = Field(default_factory=list)

