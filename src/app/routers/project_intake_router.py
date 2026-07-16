"""
Project Intake Router

Handles all endpoints for *non-draft* (production) project and agent intake
management. Draft project endpoints live in ``draft_project_router``.

Flow: Router -> Service -> Repository -> AsyncDocumentRepository
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import ValidationError

from app.models.project.Project import Project
from app.models.project.ProjectCreate import ProjectCreate, AgentCreate
from app.models.project.ProjectUpdate import ProjectUpdate, AgentUpdate
from app.models.agent.Agent import Agent
from app.models.schemas.CommonSchemas import (
    CommonErrorResponse,
    DeleteResponse,
    COMMON_ERROR_RESPONSES,
    COMMON_OWNED_ERROR_RESPONSES,
)
from app.models.schemas.ProjectIntakeSchemas import (
    ProjectWithAgentsResponse,
    PaginatedProjectsResponse,
)
from app.services.ProjectIntakeService import ProjectIntakeService
from app.models.schemas.CommonSchemas import (
    NotAuthorizedError,
    DuplicateProjectNameError,
    DuplicateAgentNameError,
)
from app.core.firestore_client import FirestoreClient
from app.core.auth import get_current_author

logger = logging.getLogger(__name__)

PROJECT_INTAKE_ROUTER = APIRouter(tags=["Project Intake"])


def get_project_intake_service() -> ProjectIntakeService:
    """Dependency injection for ProjectIntakeService"""
    # Initialize FirestoreClient singleton and get the async client
    db = FirestoreClient.InstanceClient()
    return ProjectIntakeService(db)


# ============================================================================
# NON-DRAFT PROJECT ENDPOINTS
# ============================================================================


@PROJECT_INTAKE_ROUTER.post(
    "",
    response_model=ProjectWithAgentsResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project intake",
    description="Creates a new project with associated agents. All required fields must be provided.",
    responses={
        **COMMON_ERROR_RESPONSES,
        400: {"model": CommonErrorResponse, "description": "Validation error"},
        409: {"model": CommonErrorResponse, "description": "Duplicate project name"},
    },
)
async def create_project(
    project: ProjectCreate,
    agents: Optional[List[AgentCreate]] = None,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> ProjectWithAgentsResponse:
    """
    Create a new project intake with associated agents.

    The request body should not include ``author`` or ``id`` (both are
    server-controlled); if sent, they are ignored. The ``author`` is taken from
    the Microsoft Entra access token; ``id`` is system-generated.

    Returns the created project together with its associated agents.
    """
    try:
        # Build the full entities, stamping the authenticated author from token.
        # Any client-sent author/id is dropped (server-controlled).
        project_data = project.model_dump(exclude_none=True)
        project_data.pop("author", None)
        project_data.pop("id", None)
        full_project = Project(author=author, **project_data)

        full_agents = []
        for a in agents or []:
            agent_data = a.model_dump(exclude_none=True)
            agent_data.pop("author", None)
            agent_data.pop("id", None)
            full_agents.append(Agent(author=author, **agent_data))

        result = await service.create_project(full_project, full_agents)
        logger.info(f"Project created successfully: {result['project'].id}")
        return result
    except (DuplicateProjectNameError, DuplicateAgentNameError) as e:
        logger.warning(f"Duplicate name on create: {str(e)}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error creating project: {e.errors()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Error creating project: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project",
        )


@PROJECT_INTAKE_ROUTER.get(
    "",
    response_model=PaginatedProjectsResponse,
    summary="List or search projects (paginated)",
    description=(
        "Lists published projects using cursor pagination. Agents are not "
        "included by default; set include_agents=true to bundle each project's "
        "agents. Pass 'search' to filter by a single term matched against "
        "project name and owner fields (partial), agent name (partial), "
        "project id (exact) and agent id (exact), matched "
        "case-insensitively; projects matched via an agent are included."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
        400: {"model": CommonErrorResponse, "description": "Invalid pagination cursor"},
    },
)
async def list_projects(
    page_size: int = Query(
        20, ge=1, le=100, description="Maximum number of projects per page."
    ),
    cursor: Optional[str] = Query(
        None, description="Encrypted pagination cursor from a previous response."
    ),
    include_agents: bool = Query(
        False, description="When true, include each project's agents."
    ),
    search: Optional[str] = Query(
        None,
        description=(
            "Optional search term, matched case-insensitively. Project name, "
            "project owner fields (business/product/technical owner and "
            "their emails) and agent name use partial (contains) matching; "
            "project id and agent id must match exactly. A project is "
            "returned even when only one of its agents matches."
        ),
    ),
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> PaginatedProjectsResponse:
    """
    List or search published projects with cursor pagination.

    - Agents are omitted by default for a lighter payload.
    - Pass ``include_agents=true`` to bundle each project's agents.
    - Pass ``search`` to filter by a term across project and agent
      id/name; a project whose agent matches is included in the results.
    - Use the returned ``nextCursor`` / ``prevCursor`` to navigate pages.
    """
    try:
        if search and search.strip():
            result = await service.search_projects_paginated(
                term=search,
                page_size=page_size,
                cursor=cursor,
                include_agents=include_agents,
            )
            logger.info(
                f"Searched projects for '{search}': {len(result['items'])} items"
            )
            return result

        result = await service.list_projects_paginated(
            page_size=page_size,
            cursor=cursor,
            include_agents=include_agents,
        )
        logger.info(f"Listed {len(result['items'])} projects")
        return result
    except ValueError as e:
        # Raised by the repository for an invalid/tampered cursor.
        logger.warning(f"Invalid pagination cursor: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Error listing projects: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list projects",
        )


@PROJECT_INTAKE_ROUTER.get(
    "/{project_id}",
    response_model=dict,
    summary="Get a project with associated agents",
    description="Retrieves a project and all its associated agents.",
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Project not found"},
    },
)
async def get_project(
    project_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> dict:
    """
    Get a project with all its associated agents.

    Returns:
    - Project details
    - List of associated agents
    """
    try:
        project_data = await service.get_project_with_agents(str(project_id))
        if not project_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )
        logger.info(f"Retrieved project: {project_id}")
        return project_data
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve project",
        )


@PROJECT_INTAKE_ROUTER.get(
    "/{project_id}/agents",
    response_model=List[Agent],
    summary="Get agents for a project",
    description="Retrieves all agents associated with a project.",
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Project not found"},
    },
)
async def get_project_agents(
    project_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> List[Agent]:
    """
    Get all agents associated with a project.

    Returns a 404 if the project itself does not exist.
    """
    try:
        project = await service.get_project_with_agents(str(project_id))
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )
        agents = project["agents"]
        logger.info(f"Retrieved {len(agents)} agents for project {project_id}")
        return agents
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving agents for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agents",
        )


@PROJECT_INTAKE_ROUTER.get(
    "/{project_id}/agents/{agent_id}",
    response_model=dict,
    summary="Get a single agent for a project",
    description="Retrieves a specific agent that belongs to a project.",
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Project or agent not found"},
    },
)
async def get_project_agent(
    project_id: UUID,
    agent_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> dict:
    """
    Get a specific agent that belongs to a project.

    Returns a 404 if the agent does not exist or is not mapped to the project.
    """
    try:
        agent = await service.get_agent(str(project_id), str(agent_id))
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found in project {project_id}",
            )
        logger.info(f"Retrieved agent {agent_id} for project {project_id}")
        return agent
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f"Error retrieving agent {agent_id} for project {project_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve agent",
        )


@PROJECT_INTAKE_ROUTER.put(
    "/{project_id}",
    response_model=ProjectWithAgentsResponse,
    summary="Update a project intake",
    description="Updates an existing project and its mapped agents.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Project not found"},
        400: {"model": CommonErrorResponse, "description": "Validation error"},
        409: {"model": CommonErrorResponse, "description": "Duplicate project name"},
    },
)
async def update_project(
    project_id: UUID,
    project: ProjectUpdate,
    agents: Optional[List[AgentUpdate]] = None,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> ProjectWithAgentsResponse:
    """
    Partially update an existing project and upsert its associated agents.

    - Only the project fields included in the payload are updated.
    - Each agent with an ``id`` is partially merged; agents without an ``id``
      are created. Agents not included in the payload are left untouched.
    - The ``author`` is taken from the Entra access token and stamped onto the
      project and any provided agents.

    Returns the updated project together with its current agents.
    """
    try:
        result = await service.update_project(
            str(project_id), project, agents or [], author=author
        )
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )
        logger.info(f"Project updated successfully: {project_id}")
        return result
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(f"Unauthorized update of project {project_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except (DuplicateProjectNameError, DuplicateAgentNameError) as e:
        logger.warning(f"Duplicate name on update {project_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        logger.warning(f"Validation error updating project: {e.errors()}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Error updating project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project",
        )


@PROJECT_INTAKE_ROUTER.delete(
    "/{project_id}",
    response_model=DeleteResponse,
    summary="Delete a project",
    description="Deletes a project and all its associated agents.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Project not found"},
    },
)
async def delete_project(
    project_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> DeleteResponse:
    """
    Delete a project and all its associated agents.

    This operation is irreversible.
    """
    try:
        deleted = await service.delete_project(str(project_id), author=author)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )
        logger.info(f"Project deleted successfully: {project_id}")
        return DeleteResponse(message=f"Project {project_id} deleted successfully")
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(f"Unauthorized delete of project {project_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception(f"Error deleting project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete project",
        )


@PROJECT_INTAKE_ROUTER.delete(
    "/{project_id}/agents/{agent_id}",
    response_model=DeleteResponse,
    summary="Delete a mapped agent from a project",
    description="Removes an agent from a project without deleting the project itself.",
    responses={
        **COMMON_OWNED_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Project or agent not found"},
    },
)
async def delete_project_agent(
    project_id: UUID,
    agent_id: UUID,
    service: ProjectIntakeService = Depends(get_project_intake_service),
    author: str = Depends(get_current_author),
) -> DeleteResponse:
    """
    Delete a specific agent from a project.

    The project itself remains intact.
    """
    try:
        deleted = await service.delete_agent(
            str(project_id), str(agent_id), author=author
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found in project {project_id}",
            )
        logger.info(f"Agent {agent_id} deleted from project {project_id}")
        return DeleteResponse(
            message=f"Agent {agent_id} deleted from project {project_id}"
        )
    except HTTPException:
        raise
    except NotAuthorizedError as e:
        logger.warning(
            f"Unauthorized delete of agent {agent_id} in project {project_id}: {str(e)}"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        logger.exception(
            f"Error deleting agent {agent_id} from project {project_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete agent",
        )
