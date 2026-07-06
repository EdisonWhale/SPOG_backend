"""
Use Case Router

Read-only endpoints for AI Governance use cases.

Use cases are created and updated internally by the system (no create/update/
delete routes). These endpoints only expose fetching use cases.

Flow: Router -> Service -> Repository -> AsyncDocumentRepository
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from app.models.schemas.CommonSchemas import (
    CommonErrorResponse,
    COMMON_ERROR_RESPONSES,
)
from app.models.schemas.UseCaseSchemas import (
    PaginatedUseCasesResponse,
    UseCaseListResponse,
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
