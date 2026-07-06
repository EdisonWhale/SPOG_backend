"""
Draft Agent Repository

Data access layer for DraftAgent entities.

Draft agents are stored as a Firestore **subcollection** named ``Agents`` under
their parent draft project::

    DraftProjects/{draft_project_id}/Agents/{draft_agent_id}

The parent draft project is implied by the document path, so ``project_id`` is
**not** persisted on the draft agent document. It is re-derived and stamped onto
the model when reading: from the scoped ``project_id`` for single-project reads,
and from the document's parent path for cross-project collection-group reads.
"""

import logging
from typing import Any, ClassVar, Dict, List, Optional

from google.cloud.firestore import AsyncClient

from app.models.agent.DraftAgent import DraftAgent
from app.models.project.DraftProject import DraftProject
from app.repositories.AsyncDocumentRepository import AsyncDocumentRepository

logger = logging.getLogger(__name__)


class DraftAgentRepository(AsyncDocumentRepository[DraftAgent]):
    """
    Repository for DraftAgent entities stored under
    ``DraftProjects/{draft_project_id}/Agents``.

    The subcollection is named ``Agents`` (same as published agents). Because a
    collection-group query on ``Agents`` would also match published agents,
    cross-project reads filter to documents parented under ``DraftProjects``.
    """

    # Draft agents share the ``Agents`` subcollection name with published agents.
    DRAFT_AGENTS_SUBCOLLECTION = DraftAgent.COLLECTION_NAME

    # ``project_id`` is implied by the document path and is never persisted.
    FIRESTORE_EXCLUDES: ClassVar[Dict[str, bool]] = {"project_id": True}

    def __init__(self, db: AsyncClient, project_id: Optional[str] = None):
        """Initialize DraftAgentRepository, optionally bound to a draft project."""
        super().__init__(db, DraftAgent)
        self._project_id = str(project_id) if project_id is not None else None

    def _subcollection(self, project_id: Optional[str] = None):
        """Return the ``Agents`` subcollection reference for the draft ``project_id``."""
        pid = str(project_id) if project_id is not None else self._project_id
        if not pid:
            raise ValueError("project_id is required for draft agent subcollection access")
        return (
            self.db.collection(DraftProject.COLLECTION_NAME)
            .document(pid)
            .collection(self.DRAFT_AGENTS_SUBCOLLECTION)
        )

    def for_project(self, project_id: str) -> "DraftAgentRepository":
        """Return a repository instance scoped to ``project_id``."""
        return DraftAgentRepository(self.db, project_id=project_id)

    def _from_firestore_document(self, doc_id: str, doc_data: Dict[str, Any]) -> DraftAgent:
        """Deserialize a draft agent, stamping the scoped ``project_id`` (path-derived)."""
        data = {k: v for k, v in (doc_data or {}).items() if k != "project_id"}
        agent = self.model_type(id=doc_id, **data)
        if self._project_id is not None:
            agent.project_id = self._project_id
        return agent

    async def _results_from_group_query(self, group_query) -> List[DraftAgent]:
        """Stream a collection-group query, deriving ``project_id`` from the path.

        Draft and published agents share the ``Agents`` subcollection name, so a
        collection-group query matches both. This keeps only the documents whose
        top-level collection is ``DraftProjects``.
        """
        results: List[DraftAgent] = []
        async for doc in group_query.stream():
            parent_doc = doc.reference.parent.parent
            if parent_doc is None or parent_doc.parent.id != DraftProject.COLLECTION_NAME:
                continue
            data = {k: v for k, v in (doc.to_dict() or {}).items() if k != "project_id"}
            agent = self.model_type(id=doc.id, **data)
            agent.project_id = parent_doc.id
            results.append(agent)
        return results

    # ------------------------------------------------------------------
    # Project-scoped CRUD (override base to target the subcollection)
    # ------------------------------------------------------------------
    async def create(self, model: DraftAgent, project_id: Optional[str] = None, excludes=None) -> DraftAgent:
        pid = (
            str(project_id)
            if project_id is not None
            else str(model.project_id) if model.project_id else self._project_id
        )
        if not pid:
            raise ValueError("project_id is required to create a draft agent")
        model.project_id = pid
        self._project_id = pid
        self.collection_ref = self._subcollection(pid)
        created = await super().create(model, excludes=excludes or {})
        created.project_id = pid
        return created

    async def get(self, agent_id: str, project_id: Optional[str] = None) -> Optional[DraftAgent]:
        pid = str(project_id) if project_id is not None else self._project_id
        self._project_id = pid
        self.collection_ref = self._subcollection(pid)
        return await super().get(agent_id)

    async def update(self, model: DraftAgent, project_id: Optional[str] = None, excludes=None) -> DraftAgent:
        pid = (
            str(project_id)
            if project_id is not None
            else str(model.project_id) if model.project_id else self._project_id
        )
        model.project_id = pid
        self._project_id = pid
        self.collection_ref = self._subcollection(pid)
        updated = await super().update(model, excludes=excludes or {})
        updated.project_id = pid
        return updated

    async def delete(self, agent_id: str, project_id: Optional[str] = None) -> bool:
        self.collection_ref = self._subcollection(project_id)
        return await super().delete(agent_id)

    async def get_by_project(self, project_id: str) -> List[DraftAgent]:
        """
        Get all draft agents stored under a specific draft project's subcollection.

        Args:
            project_id: UUID of the draft project

        Returns:
            List of DraftAgent instances for the draft project (``project_id`` stamped in).
        """
        try:
            self._project_id = str(project_id)
            self.collection_ref = self._subcollection(project_id)
            agents = await self.get_all()
            logger.info(
                f"Retrieved {len(agents)} draft agents for draft project {project_id}"
            )
            return agents
        except Exception as e:
            logger.exception(
                f"Error retrieving draft agents for draft project {project_id}: {str(e)}"
            )
            raise

    async def get_all_agents(self) -> List[DraftAgent]:
        """Get every draft agent across all draft projects via collection-group."""
        try:
            group_query = self.db.collection_group(self.DRAFT_AGENTS_SUBCOLLECTION)
            agents = await self._results_from_group_query(group_query)
            logger.info(f"Retrieved {len(agents)} draft agents across all draft projects")
            return agents
        except Exception as e:
            logger.exception(
                f"Error retrieving draft agents across all draft projects: {str(e)}"
            )
            raise

    async def get_by_platform(self, platform: str) -> List[DraftAgent]:
        """
        Get all draft agents for a specific platform (across all draft projects).

        Args:
            platform: Platform name (e.g., 'GCP')

        Returns:
            List of DraftAgent instances on the specified platform.
        """
        try:
            group_query = self.db.collection_group(
                self.DRAFT_AGENTS_SUBCOLLECTION
            ).where("platform", "==", platform)
            agents = await self._results_from_group_query(group_query)
            logger.info(f"Retrieved {len(agents)} draft agents on platform {platform}")
            return agents
        except Exception as e:
            logger.exception(
                f"Error retrieving draft agents on platform {platform}: {str(e)}"
            )
            raise
