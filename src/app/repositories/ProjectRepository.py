"""
Project Repository

Data access layer for Project entities.
Extends AsyncDocumentRepository with Project-specific operations.
"""

import logging
from typing import List, Optional

from google.cloud.firestore import AsyncClient
from google.cloud.firestore_v1.field_path import FieldPath

from app.models.project.Project import Project
from app.repositories.AsyncDocumentRepository import AsyncDocumentRepository

logger = logging.getLogger(__name__)

# Firestore allows at most 30 values in an ``in`` / ``document id in`` filter.
FIRESTORE_IN_LIMIT = 30
# High code point used as the upper bound for "starts-with" prefix range queries.
PREFIX_RANGE_END = "\uf8ff"


def _chunk(values, size=FIRESTORE_IN_LIMIT):
    """Yield ``values`` in lists of at most ``size`` items."""
    for start in range(0, len(values), size):
        yield values[start:start + size]


class ProjectRepository(AsyncDocumentRepository[Project]):
    """
    Repository for Project entities.
    Handles all database operations for projects.
    """

    def __init__(self, db: AsyncClient):
        """Initialize ProjectRepository with Firestore client."""
        super().__init__(db, Project)

    async def name_exists(
        self, name: str, exclude_id: Optional[str] = None
    ) -> bool:
        """Check whether a published project with ``name`` already exists.

        Published project names are unique across the whole collection. The
        comparison is case-insensitive and whitespace-trimmed: Firestore cannot
        match case-insensitively server-side, so candidates are fetched and
        compared in Python.

        Args:
            name: Candidate project name.
            exclude_id: A project id to ignore (used on update so a project does
                not collide with its own current name).

        Returns:
            True if another published project already uses an equivalent name.
        """
        normalized = (name or "").strip().lower()
        if not normalized:
            return False

        projects = await self.get_all()
        for project in projects:
            if exclude_id is not None and str(project.id) == str(exclude_id):
                continue
            if (project.name or "").strip().lower() == normalized:
                return True
        return False

    async def get_by_status(self, status: str) -> List[Project]:
        """
        Get all projects with a specific status.

        Args:
            status: Project status to filter by

        Returns:
            List of Project instances matching the status
        """
        try:
            projects = await self.get_by_field("status", "==", status)
            logger.info(f"Retrieved {len(projects)} projects with status {status}")
            return projects
        except Exception as e:
            logger.exception(f"Error retrieving projects by status {status}: {str(e)}")
            raise

    async def get_by_business_owner(self, owner_email: str) -> List[Project]:
        """
        Get all projects owned by a specific business owner.

        Args:
            owner_email: Business owner email

        Returns:
            List of Project instances owned by the specified owner
        """
        try:
            projects = await self.get_by_field("business_owner_email", "==", owner_email)
            logger.info(f"Retrieved {len(projects)} projects for business owner {owner_email}")
            return projects
        except Exception as e:
            logger.exception(
                f"Error retrieving projects for business owner {owner_email}: {str(e)}"
            )
            raise

    async def get_by_technical_owner(self, owner_email: str) -> List[Project]:
        """
        Get all projects owned by a specific technical owner.

        Args:
            owner_email: Technical owner email

        Returns:
            List of Project instances owned by the specified owner
        """
        try:
            projects = await self.get_by_field("technical_owner_email", "==", owner_email)
            logger.info(f"Retrieved {len(projects)} projects for technical owner {owner_email}")
            return projects
        except Exception as e:
            logger.exception(
                f"Error retrieving projects for technical owner {owner_email}: {str(e)}"
            )
            raise

