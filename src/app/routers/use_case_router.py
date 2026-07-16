"""
Use Case Router

Read-only endpoints for AI Governance use cases.

Use cases are created and updated internally by the system (no create/update/
delete routes). These endpoints only expose fetching use cases.

Flow: Router -> Service -> Repository -> AsyncDocumentRepository
"""

import logging
from uuid import UUID
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.models.schemas.CommonSchemas import (
    CommonErrorResponse,
    COMMON_ERROR_RESPONSES,
)
from app.models.schemas.UseCaseSchemas import (
    PaginatedUseCasesResponse,
    UseCaseListResponse,
    UseCaseResponse,
    UseCaseGovernanceResponse
)
from app.services.UseCaseService import UseCaseService
from app.core.firestore_client import FirestoreClient
from app.core.auth import get_current_author

logger = logging.getLogger(__name__)

USE_CASE_ROUTER = APIRouter(tags=["Use Cases"])


def get_use_case_service() -> UseCaseService:
    """Dependency injection for UseCaseService."""
    db = FirestoreClient.InstanceClient()
    return UseCaseService(db)


@USE_CASE_ROUTER.get(
    "",
    response_model=PaginatedUseCasesResponse,
    summary="List use cases (paginated)",
    description=(
        "Lists AI Governance use cases using cursor pagination. Optionally "
        "filter by project_id."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
        400: {"model": CommonErrorResponse, "description": "Invalid pagination cursor"},
    },
)
async def list_use_cases(
    page_size: int = Query(
        20, ge=1, le=100, description="Maximum number of use cases per page."
    ),
    cursor: Optional[str] = Query(
        None, description="Encrypted pagination cursor from a previous response."
    ),
    project_id: Optional[str] = Query(
        None, description="Filter use cases mapped to this project."
    ),
    service: UseCaseService = Depends(get_use_case_service),
    author: str = Depends(get_current_author),
) -> PaginatedUseCasesResponse:
    """
    List use cases with cursor pagination.

    - Optionally filter by ``project_id``.
    - Use the returned ``nextCursor`` / ``prevCursor`` to navigate pages.
    - ``total`` reflects the full filtered result set, not just the page.
    """
    try:
        filters = {"project_id": project_id} if project_id else None
        result = await service.list_use_cases_paginated(
            page_size=page_size,
            cursor=cursor,
            filters=filters,
        )
        logger.info(f"Listed {len(result['items'])} use cases")
        return result
    except ValueError as e:
        # Raised by the repository for an invalid/tampered cursor.
        logger.warning(f"Invalid pagination cursor: {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Error listing use cases: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list use cases",
        )


@USE_CASE_ROUTER.get(
    "/project/{project_id}",
    response_model=UseCaseListResponse,
    summary="List use cases for a project",
    description=(
        "Lists all use cases mapped to a specific project. This endpoint is "
        "not paginated and returns the complete set of use cases for the project."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
    },
)
async def list_use_cases_by_project(
    project_id: str,
    service: UseCaseService = Depends(get_use_case_service),
    author: str = Depends(get_current_author),
) -> UseCaseListResponse:
    """
    List all use cases mapped to ``project_id`` (non-paginated).

    Returns the complete set of use cases for the project. ``total`` is the
    count of returned items.
    """
    try:
        use_cases = await service.get_use_cases_by_project(project_id)
        items = [
            uc.to_dict(
                to_camel=True,
                date_format_iso=True,
                include_document_id=True,
            )
            for uc in use_cases
        ]
        logger.info(
            f"Listed {len(items)} use cases for project {project_id}"
        )
        return {"items": items, "total": len(items)}
    except Exception as e:
        logger.exception(
            f"Error listing use cases for project {project_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list use cases",
        )

@USE_CASE_ROUTER.post(
    "/project/{project_id}",
    response_model=UseCaseResponse,
    summary="Create an use case for a project",
    description=(
        "Creates a new use case for the project identified by ``project_id``. "
        "Returns the created use case along with its AI governance URL."
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
    },
)
async def create_use_case(
    project_id: UUID,
    service: UseCaseService = Depends(get_use_case_service),
    author: str = Depends(get_current_author),
) -> UseCaseResponse:
    try:
        use_case_with_link = await service.create_use_case(str(project_id), author=author)
        logger.info(f"Use case created successfully for project: {project_id}")
        return use_case_with_link
    except ValueError as e:
        logger.warning(f"Validation error creating use case for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.exception(f"Error creating use case for project {project_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create use case",
        )


@USE_CASE_ROUTER.get(
    "/{use_case_id}/link",
    response_model=UseCaseGovernanceResponse,
    summary="Get the link for the AI governance form",
    description=(
        "This endpoint to generate the read only link for the AI governance form"
    ),
    responses={
        **COMMON_ERROR_RESPONSES,
        404: {"model": CommonErrorResponse, "description": "Use case not found"},
    },
)
async def generate_use_case_governance_link(
    use_case_id: str,
    service: UseCaseService = Depends(get_use_case_service),
    author: str = Depends(get_current_author),
) -> UseCaseGovernanceResponse:
    """
    Generate a read-only AI governance form link for the given use case.

    Builds and returns a pre-populated ServiceNow AI governance URL
    for the use case identified by ``use_case_id``.

    Returns a response containing the generated ``link``.
    """
    try:
        governance_form_url = await service.get_ai_governance_url(use_case_id, author)
        logger.info(
            f"Generated AI governance link for use case {use_case_id}"
        )
        return UseCaseGovernanceResponse(governance_form_url=governance_form_url)
    except ValueError as e:
        logger.warning(f"Validation error while generating AI governance form url for use_case id: {use_case_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException as e:
        logger.warning(f"Use case not found for id: {use_case_id}: {str(e.detail)}")
        raise
    except Exception as e:
        logger.exception(
            f"Error while generating the link for the use case {use_case_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate AI governance form link",
        )

