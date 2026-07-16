"""
Draft Project Router

Handles all endpoints for *draft* project and agent intake management.
Draft projects can be saved with incomplete information, updated later, and
eventually published into production projects.

Mounted under the ``/projects/draft`` prefix, so paths here are relative to it.

Flow: Router -> Service -> Repository -> AsyncDocumentRepository
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import ValidationError

from app.models.project.DraftProject import DraftProject
from app.models.project.DraftProjectCreate import DraftProjectCreate, DraftAgentCreate
from app.models.project.DraftProjectUpdate import DraftProjectUpdate, DraftAgentUpdate
from app.models.agent.DraftAgent import DraftAgent
from app.models.schemas.CommonSchemas import (
    CommonErrorResponse,
    DeleteResponse,
    CountResponse,
    COMMON_ERROR_RESPONSES,
    COMMON_OWNED_ERROR_RESPONSES,
)
from app.models.schemas.ProjectIntakeSchemas import (
    ProjectWithAgentsResponse,
    DraftProjectWithAgentsResponse,
)
from app.services.ProjectIntakeService import ProjectIntakeService
from app.models.schemas.CommonSchemas import (
    NotAuthorizedError,
    DuplicateProjectNameError,
    DuplicateAgentNameError,
)
from app.routers.project_intake_router import get_project_intake_service
from app.core.auth import get_current_author

logger = logging.getLogger(__name__)

DRAFT_PROJECT_ROUTER = APIRouter(tags=["Draft Project Intake"])


@DRAFT_PROJECT_ROUTER.post(
    "",
    response_model=DraftProjectWithAgentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new draft project intake",
    description="Creates a draft project with optional agents. Fields can be partially filled.",
    responses={
        **COMMON_ERROR_RESPONSES,
        400: {"model": CommonErrorResponse, "description": "Validation error"},
        409: {"model": CommonErrorResponse, "description": "Duplicate draft name for author"},
    },
)
async def create_draft_project(
    project: DraftProjectCreate,
    agents: Optional[List[DraftAgentCreate]] = None,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> DraftProjectWithAgentsResponse:
    """
    Create a new draft project intake.

    The request body should not include ``author`` or ``id`` (both are
    server-controlled); if sent, they are ignored. Only ``name`` is mandatory on
    a draft project. The ``author`` is taken from the Entra access token; ``id``
    is system-generated.

    Returns the created draft project together with its draft agents.
    """
    try:
        project_data = project.model_dump(exclude_none=True)
        project_data.pop("author", None)
        project_data.pop("id", None)
        full_project = DraftProject(author=author, **project_data)

        full_agents = []
        for a in agents or []:
            agent_data = a.model_dump(exclude_none=True)
            agent_data.pop("author", None)
            agent_data.pop("id", None)
            full_agents.append(DraftAgent(author=author, **agent_data))

        result = await service.create_draft_project(full_project, full_agents)
        logger.info(f"Draft project created successfully: {result['project'].id}")
        return result
    except (DuplicateProjectNameError, DuplicateAgentNameError) as e:
        logger.warning(f"Duplicate name on draft create: {str(e)}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error creating draft project: {e.errors()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Error creating draft project: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create draft project",
        )


@DRAFT_PROJECT_ROUTER.get(
    "",
    response_model=List[dict],
    summary="Get the current author's draft projects with agents",
    description=(
        "Retrieves all draft projects created by the authenticated author, "
        "each with its associated draft agents. Drafts are author-oriented: an "
        "author can only access their own drafts."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
    },
)
async def get_my_draft_projects(
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> List[dict]:
    """
    Get all draft projects owned by the authenticated author.

    Each item contains the draft project and its associated draft agents.
    Only the author's own drafts are returned.
    """
    try:
        drafts = await service.get_draft_projects_by_author(author)
        logger.info(f"Retrieved {len(drafts)} draft projects for author {author}")
        return drafts
    except Exception as e:
        logger.exception(f"Error retrieving draft projects for author {author}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve draft projects",
        )


@DRAFT_PROJECT_ROUTER.get(
    "/count",
    response_model=CountResponse,
    summary="Count the current author's draft projects",
    description=(
        "Returns the number of draft projects created by the authenticated "
        "author. Drafts are author-oriented: only the author's own drafts are "
        "counted."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
    },
)
async def count_my_draft_projects(
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> CountResponse:
    """
    Count all draft projects owned by the authenticated author.

    Only the author's own drafts are counted.
    """
    try:
        count = await service.count_draft_projects_by_author(author)
        logger.info(f"Counted {count} draft projects for author {author}")
        return CountResponse(count=count)
    except Exception as e:
        logger.exception(f"Error counting draft projects for author {author}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to count draft projects",
        )


@DRAFT_PROJECT_ROUTER.get(
    "/{draft_project_id}",
    response_model=dict,
    summary="Get a draft project with associated draft agents",
    description="Retrieves a draft project and all its associated draft agents.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Draft project not found"},
    },
)
async def get_draft_project(
    draft_project_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> dict:
    """
    Get a draft project with all its associated draft agents.

    Only the author who created the draft may access it.

    Returns:
    - Draft project details
    - List of associated draft agents
    """
    try:
        project_data = await service.get_draft_project_with_agents(
            str(draft_project_id), author=author
        )
        if not project_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft project {draft_project_id} not found",
            )
        logger.info(f"Retrieved draft project: {draft_project_id}")
        return project_data
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(f"Unauthorized read of draft project {draft_project_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception(f"Error retrieving draft project {draft_project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve draft project",
        )


@DRAFT_PROJECT_ROUTER.get(
    "/{draft_project_id}/agents/{agent_id}",
    response_model=dict,
    summary="Get a single draft agent for a draft project",
    description="Retrieves a specific draft agent that belongs to a draft project.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Draft project or agent not found"},
    },
)
async def get_draft_project_agent(
    draft_project_id: UUID,
    agent_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> dict:
    """
    Get a specific draft agent that belongs to a draft project.

    Only the author who created the draft may access it. Returns a 404 if the
    draft agent does not exist or is not mapped to the draft project.
    """
    try:
        agent = await service.get_draft_agent(
            str(draft_project_id), str(agent_id), author=author
        )
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft agent {agent_id} not found in draft project {draft_project_id}",
            )
        logger.info(f"Retrieved draft agent {agent_id} for draft project {draft_project_id}")
        return agent
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(
            f"Unauthorized read of draft agent {agent_id} in draft project {draft_project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception(
            f"Error retrieving draft agent {agent_id} for draft project {draft_project_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve draft agent",
        )


@DRAFT_PROJECT_ROUTER.post(
    "/{draft_project_id}/publish",
    response_model=ProjectWithAgentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a draft project as non-draft",
    description="Converts a draft project to a production project, keeping IDs consistent. No payload required.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Draft project not found"},
        400: {"model": CommonErrorResponse, "description": "Validation error"},
        409: {"model": CommonErrorResponse, "description": "Duplicate published project name"},
    },
)
async def publish_draft_project(
    draft_project_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> ProjectWithAgentsResponse:
    """
    Publish a draft project as a non-draft (production) project.

    No request body is required. The production project is built from the
    stored draft data, so the draft must already contain all fields required
    by the ``Project`` model (an incomplete draft results in a 400).

    This operation:
    - Moves the draft project to the Projects collection
    - Moves all associated draft agents to the Agents collection
    - Keeps the project_id and agent_ids consistent
    - Deletes the draft versions

    Returns the published project together with its agents.
    """
    try:
        result = await service.publish_draft_project(
            str(draft_project_id), author=author
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft project {draft_project_id} not found",
            )
        logger.info(f"Draft project published successfully: {draft_project_id}")
        return result
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(
            f"Unauthorized publish of draft project {draft_project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DuplicateProjectNameError, DuplicateAgentNameError) as e:
        logger.warning(
            f"Duplicate name on publish {draft_project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error publishing draft project: {e.errors()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Error publishing draft project {draft_project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to publish draft project",
        )


@DRAFT_PROJECT_ROUTER.put(
    "/{draft_project_id}",
    response_model=DraftProjectWithAgentsResponse,
    summary="Update a draft project",
    description="Updates an existing draft project and its associated draft agents.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Draft project not found"},
        400: {"model": CommonErrorResponse, "description": "Validation error"},
        409: {"model": CommonErrorResponse, "description": "Duplicate draft name for author"},
    },
)
async def update_draft_project(
    draft_project_id: UUID,
    project: DraftProjectUpdate,
    agents: Optional[List[DraftAgentUpdate]] = None,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> DraftProjectWithAgentsResponse:
    """
    Partially update an existing draft project and upsert its draft agents.

    - Only the draft project fields included in the payload are updated.
    - Each draft agent with an ``id`` is partially merged; agents without an
      ``id`` are created. Agents not included are left untouched.
    - The ``author`` is taken from the Entra access token and stamped onto the
      draft project and any provided agents.

    Returns the updated draft project together with its current draft agents.
    """
    try:
        result = await service.update_draft_project(
            str(draft_project_id), project, agents or [], author=author
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft project {draft_project_id} not found",
            )
        logger.info(f"Draft project updated successfully: {draft_project_id}")
        return result
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(
            f"Unauthorized update of draft project {draft_project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DuplicateProjectNameError, DuplicateAgentNameError) as e:
        logger.warning(
            f"Duplicate name on draft update {draft_project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error updating draft project: {e.errors()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Error updating draft project {draft_project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update draft project",
        )


@DRAFT_PROJECT_ROUTER.delete(
    "/{draft_project_id}",
    response_model=DeleteResponse,
    summary="Delete a draft project",
    description="Deletes a draft project and all its associated draft agents.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Draft project not found"},
    },
)
async def delete_draft_project(
    draft_project_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> DeleteResponse:
    """
    Delete a draft project and all its associated draft agents.

    This operation is irreversible.
    """
    try:
        deleted = await service.delete_draft_project(
            str(draft_project_id), author=author
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft project {draft_project_id} not found",
            )
        logger.info(f"Draft project deleted successfully: {draft_project_id}")
        return DeleteResponse(
            message=f"Draft project {draft_project_id} deleted successfully"
        )
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(
            f"Unauthorized delete of draft project {draft_project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception(f"Error deleting draft project {draft_project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete draft project",
        )


@DRAFT_PROJECT_ROUTER.delete(
    "/{draft_project_id}/agents/{agent_id}",
    response_model=DeleteResponse,
    summary="Delete a draft agent from a draft project",
    description="Removes a draft agent from a draft project.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Draft project or agent not found"},
    },
)
async def delete_draft_agent(
    draft_project_id: UUID,
    agent_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> DeleteResponse:
    """
    Delete a specific draft agent from a draft project.

    The draft project itself remains intact.
    """
    try:
        deleted = await service.delete_draft_agent(
            str(draft_project_id), str(agent_id), author=author
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Draft agent {agent_id} not found in draft project {draft_project_id}",
            )
        logger.info(f"Draft agent {agent_id} deleted from draft project {draft_project_id}")
        return DeleteResponse(
            message=f"Draft agent {agent_id} deleted from draft project {draft_project_id}"
        )
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(
            f"Unauthorized delete of draft agent {agent_id} in draft project {draft_project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception(
            f"Error deleting draft agent {agent_id} from draft project {draft_project_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete draft agent",
        )
