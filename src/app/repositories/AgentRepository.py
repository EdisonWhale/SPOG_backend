"""
Agent Repository

Data access layer for Agent entities.

Agents are stored as a Firestore **subcollection** under their parent project::

    Projects/{project_id}/Agents/{agent_id}

The parent project is implied by the document path, so ``project_id`` is **not**
persisted on the agent document. It is re-derived and stamped onto the model
when reading: from the scoped ``project_id`` for single-project reads, and from
the document's parent path for cross-project collection-group reads.

Cross-project reads use a Firestore collection-group query over every ``Agents``
subcollection.
"""

import logging
from typing import Any, ClassVar, Dict, List, Optional

from google.cloud.firestore import AsyncClient

from app.models.agent.Agent import Agent
from app.models.project.Project import Project
from app.repositories.AsyncDocumentRepository import AsyncDocumentRepository

logger = logging.getLogger(__name__)


class AgentRepository(AsyncDocumentRepository[Agent]):
    """
    Repository for Agent entities stored under ``Projects/{project_id}/Agents``.

    Pass ``project_id`` to scope an instance to a single project's subcollection.
    Methods also accept a per-call ``project_id`` so a single instance can serve
    multiple projects. Cross-project listing uses a collection-group query.
    """

    AGENTS_SUBCOLLECTION = Agent.COLLECTION_NAME

    def __init__(self, db: AsyncClient, project_id: Optional[str] = None):
        """Initialize AgentRepository, optionally bound to a project."""
        super().__init__(db, Agent)
        self._project_id = str(project_id) if project_id is not None else None

    def _subcollection(self, project_id: Optional[str] = None):
        """Return the ``Agents`` subcollection reference for ``project_id``."""
        pid = str(project_id) if project_id is not None else self._project_id
        if not pid:
            raise ValueError("project_id is required for agent subcollection access")
        return (
            self.db.collection(Project.COLLECTION_NAME)
            .document(pid)
            .collection(self.AGENTS_SUBCOLLECTION)
        )

    def for_project(self, project_id: str) -> "AgentRepository":
        """Return a repository instance scoped to ``project_id``."""
        return AgentRepository(self.db, project_id=project_id)

    def _from_firestore_document(self, doc_id: str, doc_data: Dict[str, Any]) -> Agent:
        """Deserialize an agent, stamping the scoped ``project_id`` (path-derived)."""
        data = {k: v for k, v in (doc_data or {}).items() if k != "project_id"}
        agent = self.model_type(id=doc_id, **data)
        if self._project_id is not None:
            agent.project_id = self._project_id
        return agent

    async def _results_from_group_query(self, group_query) -> List[Agent]:
        """Stream a collection-group query, deriving ``project_id`` from the path.

        Published agents and draft agents both live in a subcollection named
        ``Agents`` (under ``Projects`` and ``DraftProjects`` respectively), so a
        collection-group query matches both. This filters to only the documents
        whose top-level collection is ``Projects``.

        For a document at ``Projects/{pid}/Agents/{aid}``,
        ``doc.reference.parent.parent`` is the ``{pid}`` project document and
        ``doc.reference.parent.parent.parent.id`` is the top-level collection.
        """
        results: List[Agent] = []
        async for doc in group_query.stream():
            parent_doc = doc.reference.parent.parent
            if parent_doc is None or parent_doc.parent.id != Project.COLLECTION_NAME:
                continue
            data = {k: v for k, v in (doc.to_dict() or {}).items() if k != "project_id"}
            agent = self.model_type(id=doc.id, **data)
            agent.project_id = parent_doc.id
            results.append(agent)
        return results

    # ------------------------------------------------------------------
    # Project-scoped CRUD (override base to target the subcollection)
    # ------------------------------------------------------------------
    async def create(self, model: Agent, project_id: Optional[str] = None, excludes=None) -> Agent:
        pid = (
            str(project_id)
            if project_id is not None
            else str(model.project_id) if model.project_id else self._project_id
        )
        if not pid:
            raise ValueError("project_id is required to create an agent")
        model.project_id = pid
        self._project_id = pid
        self.collection_ref = self._subcollection(pid)
        created = await super().create(model, excludes=excludes or {})
        created.project_id = pid
        return created

    async def get(self, agent_id: str, project_id: Optional[str] = None) -> Optional[Agent]:
        pid = str(project_id) if project_id is not None else self._project_id
        self._project_id = pid
        self.collection_ref = self._subcollection(pid)
        return await super().get(agent_id)

    async def update(self, model: Agent, project_id: Optional[str] = None, excludes=None) -> Agent:
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

    async def get_by_project(self, project_id: str) -> List[Agent]:
        """
        Get all agents stored under a specific project's subcollection.

        Args:
            project_id: UUID of the project

        Returns:
            List of Agent instances for the project (``project_id`` stamped in).
        """
        try:
            self._project_id = str(project_id)
            self.collection_ref = self._subcollection(project_id)
            agents = await self.get_all()
            logger.info(f"Retrieved {len(agents)} agents for project {project_id}")
            return agents
        except Exception as e:
            logger.exception(f"Error retrieving agents for project {project_id}: {str(e)}")
            raise

    async def get_all_agents(self) -> List[Agent]:
        """
        Get every agent across all projects via a collection-group query.

        ``project_id`` is derived from each document's parent path. Used by the
        in-memory project search, which scans the whole catalogue.
        """
        try:
            group_query = self.db.collection_group(self.AGENTS_SUBCOLLECTION)
            agents = await self._results_from_group_query(group_query)
            logger.info(f"Retrieved {len(agents)} agents across all projects")
            return agents
        except Exception as e:
            logger.exception(f"Error retrieving agents across all projects: {str(e)}")
            raise

    async def get_by_platform(self, platform: str) -> List[Agent]:
        """
        Get all agents deployed on a specific platform (across all projects).

        Args:
            platform: Platform name (e.g., 'GCP')

        Returns:
            List of Agent instances on the specified platform.
        """
        try:
            group_query = self.db.collection_group(self.AGENTS_SUBCOLLECTION).where(
                "platform", "==", platform
            )
            agents = await self._results_from_group_query(group_query)
            logger.info(f"Retrieved {len(agents)} agents on platform {platform}")
            return agents
        except Exception as e:
            logger.exception(f"Error retrieving agents on platform {platform}: {str(e)}")
            raise
