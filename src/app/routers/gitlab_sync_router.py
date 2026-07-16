"""
GitLab Sync Router

Scheduled endpoint triggered by GitLab Pipeline Scheduler to sync
staging agents to production by fetching code version and release
date from GitLab.
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, Depends, HTTPException, status
from app.services.GitlabService import GitLabService
from app.core.auth import get_current_author
from app.utils.helpers.common_helpers import verify_scheduler
from app.core.firestore_client import FirestoreClient
from app.models.schemas.GitlabSchemas import GitLabSyncResponse
from app.models.schemas.CommonSchemas import (
    CommonErrorResponse,
    COMMON_ERROR_RESPONSES,
)

logger = logging.getLogger(__name__)

GITLAB_SYNC_ROUTER = APIRouter(tags=["gitlab"])

def get_gitlab_service() -> GitLabService:
    """Dependency injection for GitlabService."""
    db = FirestoreClient.InstanceClient()
    return GitLabService(db)

@GITLAB_SYNC_ROUTER.post(
    "/project/{project_id}/sync",
    response_model=GitLabSyncResponse,
    summary="Trigger on-demand GitLab sync for a project",
    description=(
        "Syncs staging agents to production for a specific project. "
        "Project must be locked=True and active=False to proceed. "
        "Returns immediately with status=PENDING; sync runs in background."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Project not found"},
        409: {"model": CommonErrorResponse, "description": "Project conditions not met"},
    },
)
async def trigger_gitlab_sync(
    project_id: str,
    background_tasks: BackgroundTasks,
    service: GitLabService = Depends(get_gitlab_service),
    author: str = Depends(get_current_author),
) -> GitLabSyncResponse:
    try:
        # Returns immediately with PENDING status
        response = await service.trigger_gitlab_sync(str(project_id), author=author)
        if not response:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )

        # Actual sync runs in background
        background_tasks.add_task(service.run_gitlab_sync, str(project_id), author)

        logger.info(f"🕐 GitLab sync queued for project {project_id} by {author}")
        return response

    except ValueError as e:
        logger.warning(f"GitLab sync condition not met for project {project_id}: {e}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error triggering GitLab sync for project {project_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger GitLab sync",
        )

# ── Router ────────────────────────────────────────────────────────────────────
@GITLAB_SYNC_ROUTER.post("/auto-sync", include_in_schema=False)
async def gitlab_auto_sync(
    authorization: Optional[str] = Header(None),
    x_cloudscheduler_jobname: Optional[str] = Header(None),
    service: GitLabService = Depends(get_gitlab_service),
):
    # verify_scheduler(authorization)
    logger.info(f"🚀 Triggered by: {x_cloudscheduler_jobname or 'manual'}")

    await service.gitlab_auto_sync()
    
    return {"status": "success"}