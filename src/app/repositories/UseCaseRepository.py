"""
Use Case Repository

Data access layer for UseCase entities.
Extends AsyncDocumentRepository with UseCase-specific operations.
"""

import logging
from typing import List, Optional

from google.cloud.firestore import AsyncClient
from google.cloud.firestore_v1.base_query import FieldFilter, Or
from app.models.usecase.UseCase import UseCase
from app.repositories.AsyncDocumentRepository import AsyncDocumentRepository
from app.enum import UseCaseStatusEnum
from app.models.schemas.UseCaseSchemas import PaginatedUseCasesResponse

logger = logging.getLogger(__name__)


class UseCaseRepository(AsyncDocumentRepository[UseCase]):
    """
    Repository for UseCase entities.
    Handles all database operations for use cases.
    """

    def __init__(self, db: AsyncClient):
        """Initialize UseCaseRepository with Firestore client."""
        super().__init__(db, UseCase)

    async def get_by_project(self, project_id: str) -> List[UseCase]:
        """
        Get all use cases mapped to a specific (published) project.

        Args:
            project_id: ID of the project

        Returns:
            List of UseCase instances mapped to the project
        """
        try:
            use_cases = await self.get_by_field("project_id", "==", project_id)
            logger.info(f"Retrieved {len(use_cases)} use cases for project {project_id}")
            return use_cases
        except Exception as e:
            logger.exception(
                f"Error retrieving use cases for project {project_id}: {str(e)}"
            )
            raise

    async def get_by_status(self, status: str) -> List[UseCase]:
        """
        Get all use cases with a specific AI Governance status.

        Args:
            status: Use case status to filter by

        Returns:
            List of UseCase instances matching the status
        """
        try:
            use_cases = await self.get_by_field("status", "==", status)
            logger.info(f"Retrieved {len(use_cases)} use cases with status {status}")
            return use_cases
        except Exception as e:
            logger.exception(f"Error retrieving use cases by status {status}: {str(e)}")
            raise


    async def get_approved_first_use_case(self, project_id: str) -> UseCase:
        try:
            use_cases = await self.get_by_filters(
                filters=[
                    ("project_id", "==", project_id),
                    ("status", "==", UseCaseStatusEnum.APPROVED),
                    ("is_first", "==", True)
                ],
                limit=1
            )
            logger.info(f"Retrieved {len(use_cases)} use cases with project_id {project_id}")
            if use_cases:
                return use_cases[0]
            return None
        except Exception as e:
            logger.exception(f"Error retrieving use cases by project id {project_id}: {str(e)}")
            raise

    async def get_all_use_cases_paginated(
        self,
        project_id: Optional[str] = None,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> PaginatedUseCasesResponse:
        """
        List use cases using cursor pagination.

        ``total`` is the count of all use cases matching ``filters`` (the whole
        result set, not just the current page). The exact same ``filters`` are
        passed to both the page query and the count so the two always agree.

        Args:
            page_size: Maximum number of use cases per page.
            cursor: Encrypted pagination cursor from a previous response.
            filters: Optional ``{field: value}`` filters applied identically to
                the page query and the total count (e.g. ``{"project_id": ...}``).

        Returns:
            Dict with ``items`` (camelCase use case dicts), ``total``,
            ``next_cursor`` and ``prev_cursor``.
        """
        try:
            # Same filters drive both the page and the total count.
            filters = None
            if project_id:
                filters = [("project_id", "==", project_id)]

            use_cases, next_cursor, prev_cursor = await self.get_all_paginated(
                page_size=page_size,
                cursor=cursor,
                filters=filters,
            )
            total = await self.count_all(filters=filters)

            logger.info(f"Listed {len(use_cases)} of {total} use cases")
            return PaginatedUseCasesResponse(
                items=use_cases,
                total=total,
                next_cursor=next_cursor,
                prev_cursor=prev_cursor
            )
        except Exception as e:
            logger.exception(f"Error listing use cases: {str(e)}")
            raise
