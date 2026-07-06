"""
Draft Project Repository

Data access layer for DraftProject entities.
Extends AsyncDocumentRepository with DraftProject-specific operations.
"""

import logging
from typing import List, Optional

from google.cloud.firestore import AsyncClient

from app.models.project.DraftProject import DraftProject
from app.repositories.AsyncDocumentRepository import AsyncDocumentRepository

logger = logging.getLogger(__name__)


class DraftProjectRepository(AsyncDocumentRepository[DraftProject]):
    """
    Repository for DraftProject entities.
    Handles all database operations for draft projects.
    """

    def __init__(self, db: AsyncClient):
        """Initialize DraftProjectRepository with Firestore client."""
        super().__init__(db, DraftProject)

    async def name_exists_for_author(
        self, name: str, author: str, exclude_id: Optional[str] = None
    ) -> bool:
        """Check whether ``author`` already has a draft project with ``name``.

        Draft project names are unique *per author*: the same author cannot
        keep two drafts with the same name, but different authors may. The
        comparison is case-insensitive and whitespace-trimmed; only the
        author's own drafts are queried from Firestore, then compared in Python.

        Args:
            name: Candidate draft project name.
            author: The owning author to scope the check to.
            exclude_id: A draft id to ignore (used on update so a draft does not
                collide with its own current name).

        Returns:
            True if the author already has another draft with an equivalent name.
        """
        normalized = (name or "").strip().lower()
        if not normalized or not author:
            return False

        drafts = await self.get_by_field("author", "==", author)
        for draft in drafts:
            if exclude_id is not None and str(draft.id) == str(exclude_id):
                continue
            if (draft.name or "").strip().lower() == normalized:
                return True
        return False

    async def get_by_business_owner(self, owner_email: str) -> List[DraftProject]:
        """
        Get all draft projects owned by a specific business owner.

        Args:
            owner_email: Business owner email

        Returns:
            List of DraftProject instances owned by the specified owner
        """
        try:
            projects = await self.get_by_field("business_owner_email", "==", owner_email)
            logger.info(f"Retrieved {len(projects)} draft projects for business owner {owner_email}")
            return projects
        except Exception as e:
            logger.exception(
                f"Error retrieving draft projects for business owner {owner_email}: {str(e)}"
            )
            raise

    async def get_by_technical_owner(self, owner_email: str) -> List[DraftProject]:
        """
        Get all draft projects owned by a specific technical owner.

        Args:
            owner_email: Technical owner email

        Returns:
            List of DraftProject instances owned by the specified owner
        """
        try:
            projects = await self.get_by_field("technical_owner_email", "==", owner_email)
            logger.info(f"Retrieved {len(projects)} draft projects for technical owner {owner_email}")
            return projects
        except Exception as e:
            logger.exception(
                f"Error retrieving draft projects for technical owner {owner_email}: {str(e)}"
            )
            raise
