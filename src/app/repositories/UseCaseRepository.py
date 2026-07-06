"""
Use Case Repository

Data access layer for UseCase entities.
Extends AsyncDocumentRepository with UseCase-specific operations.
"""

import logging
from typing import List

from google.cloud.firestore import AsyncClient

from app.models.usecase.UseCase import UseCase
from app.repositories.AsyncDocumentRepository import AsyncDocumentRepository

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
