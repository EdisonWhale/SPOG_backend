"""
Use Case Service

Business logic layer for AI Governance use cases.

Use cases are created and updated internally by the system (no API routes).
A use case may only be created for an existing *published* project; the service
enforces this by verifying the project exists before persisting the use case.

Flow: (internal caller) -> Service -> Repository -> AsyncDocumentRepository
"""

import logging
from typing import List, Optional, Dict, Any

from google.cloud.firestore import AsyncClient

from app.models.usecase.UseCase import UseCase
from app.models.usecase.UseCaseUpdate import UseCaseUpdate
from app.repositories.UseCaseRepository import UseCaseRepository
from app.repositories.ProjectRepository import ProjectRepository

logger = logging.getLogger(__name__)


class UseCaseService:
    """
    Service layer for use case management.

    Use cases are tied to published projects only. All mutating operations
    verify the target project exists before persisting.
    """

    def __init__(self, db: AsyncClient):
        """Initialize service with Firestore client and repositories."""
        self.db = db
        self.use_case_repo = UseCaseRepository(db)
        self.project_repo = ProjectRepository(db)

    async def create_use_case(self, use_case: UseCase) -> UseCase:
        """
        Create a use case for an existing published project.
        If this is the first use case for the project, marks is_first=True.

        Args:
            use_case: UseCase instance to persist

        Returns:
            The created UseCase.

        Raises:
            ValueError: If the mapped project does not exist (not published).
        """
        try:
            project = await self.project_repo.get(use_case.project_id)
            if not project:
                raise ValueError(
                    f"Cannot create use case: project {use_case.project_id} "
                    "does not exist or is not published"
                )

            # Check if this is the first use case for the project
            existing_use_cases = await self.use_case_repo.get_by_project(use_case.project_id)
            use_case.is_first = len(existing_use_cases) == 0

            created = await self.use_case_repo.create(use_case)
            logger.info(
                f"Use case {created.id} created for project {use_case.project_id} "
                f"| is_first={created.is_first}"
            )
            return created
        except Exception as e:
            logger.exception(f"Error creating use case {use_case.id}: {str(e)}")
            raise

    async def get_use_case(self, use_case_id: str) -> Optional[UseCase]:
        """
        Retrieve a single use case by its ID.

        Args:
            use_case_id: ID of the use case

        Returns:
            The UseCase, or None if not found.
        """
        try:
            return await self.use_case_repo.get(use_case_id)
        except Exception as e:
            logger.exception(f"Error retrieving use case {use_case_id}: {str(e)}")
            raise

    async def get_all_use_cases(self) -> List[UseCase]:
        """
        Retrieve all use cases.

        Returns:
            List of all UseCase instances. Empty if none exist.
        """
        try:
            return await self.use_case_repo.get_all()
        except Exception as e:
            logger.exception(f"Error retrieving all use cases: {str(e)}")
            raise

    async def list_use_cases_paginated(
        self,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
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
            use_cases, next_cursor, prev_cursor = await self.use_case_repo.get_all_paginated(
                page_size=page_size,
                cursor=cursor,
                filters=filters,
            )
            total = await self.use_case_repo.count_all(filters=filters)

            items = [
                uc.to_dict(
                    to_camel=True,
                    date_format_iso=True,
                    include_document_id=True,
                )
                for uc in use_cases
            ]

            logger.info(f"Listed {len(items)} of {total} use cases")
            return {
                "items": items,
                "total": total,
                "next_cursor": next_cursor,
                "prev_cursor": prev_cursor,
            }
        except Exception as e:
            logger.exception(f"Error listing use cases: {str(e)}")
            raise

    async def get_use_cases_by_project(self, project_id: str) -> List[UseCase]:
        """
        Retrieve all use cases mapped to a project.

        Args:
            project_id: ID of the project

        Returns:
            List of UseCase instances mapped to the project. Empty if none.
        """
        try:
            return await self.use_case_repo.get_by_project(project_id)
        except Exception as e:
            logger.exception(
                f"Error retrieving use cases for project {project_id}: {str(e)}"
            )
            raise

    async def update_use_case(
        self, use_case_id: str, update: UseCaseUpdate
    ) -> Optional[UseCase]:
        """
        Partially update an existing use case.

        Only the fields explicitly provided on ``update`` are changed; all
        other fields are left untouched. The use case ``id`` is never changed.

        Args:
            use_case_id: ID of the use case to update
            update: Partial fields to merge

        Returns:
            The updated UseCase, or None if it does not exist.
        """
        try:
            existing = await self.use_case_repo.get(use_case_id)
            if not existing:
                return None

            changed: Dict[str, Any] = update.model_dump(
                exclude_unset=True, exclude_none=True
            )
            changed.pop("id", None)  # id is key-controlled, never client-set
            merged = existing.model_copy(update=changed)
            merged.id = use_case_id
            updated = await self.use_case_repo.update(merged)
            logger.info(
                f"Use case {use_case_id} updated with fields: {list(changed.keys())}"
            )
            return updated
        except Exception as e:
            logger.exception(f"Error updating use case {use_case_id}: {str(e)}")
            raise

    async def delete_use_case(self, use_case_id: str) -> bool:
        """
        Delete a use case by its ID.

        Args:
            use_case_id: ID of the use case

        Returns:
            True if deleted, False if not found.
        """
        try:
            deleted = await self.use_case_repo.delete(use_case_id)
            logger.info(f"Use case {use_case_id} deleted: {deleted}")
            return deleted
        except Exception as e:
            logger.exception(f"Error deleting use case {use_case_id}: {str(e)}")
            raise
