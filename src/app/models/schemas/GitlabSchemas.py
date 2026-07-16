
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from app.enum import GitlabSyncRequestedStatusEnum

class GitLabSyncResponse(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "Completed",
                "project_id": "abc-123-uuid",
                "promoted": True,
                "gitlab_sync_requested_at": "2026-06-25T14:30:00+00:00",
            }
        }
    )

    status: GitlabSyncRequestedStatusEnum = Field(..., description="Current sync status")
    project_id: str = Field(..., description="ID of the synced project")
    promoted: str = Field(..., description="All agent systems are moved to production")
    gitlab_sync_requested_at: datetime = Field(..., description="Timestamp of the sync request")


class GitLabSyncSchedulerResponse(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "processing",
                "projects_queued": 2,
                "agents_queued": 10,
            }
        }
    )

    status: GitlabSyncRequestedStatusEnum = Field(..., description="Current sync status for scheduler")
    projects_queued: int = Field(..., description="Number of projects queued")
    agents_queued: int = Field(..., description="Number of agents queued")
