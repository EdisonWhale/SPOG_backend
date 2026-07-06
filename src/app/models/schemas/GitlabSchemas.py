from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from app.enum import GitlabSyncRequestedStatusEnum

class GitLabSyncResponse(BaseModel):

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "pending",
                "project_id": "abc-123-uuid",
                "gitlab_sync_requested_at": "2026-06-25T14:30:00+00:00",
            }
        }
    )

    status: GitlabSyncRequestedStatusEnum = Field(..., description="Current sync status")
    project_id: str = Field(..., description="ID of the synced project")
    gitlab_sync_requested_at: datetime = Field(..., description="Timestamp of the sync request")
