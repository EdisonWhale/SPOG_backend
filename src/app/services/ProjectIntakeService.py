"""
Project Intake Service

Business logic layer for project and agent intake management.
Handles orchestration between repositories and applies business rules.

Flow: Router -> Service -> Repository -> AsyncDocumentRepository
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any, Tuple
from google.cloud.firestore import AsyncClient
from app.models.project.Project import Project
from app.models.project.DraftProject import DraftProject
from app.models.project.ProjectUpdate import ProjectUpdate, AgentUpdate
from app.models.project.DraftProjectUpdate import DraftProjectUpdate, DraftAgentUpdate
from app.models.agent.Agent import Agent
from app.models.agent.DraftAgent import DraftAgent
from app.repositories.ProjectRepository import ProjectRepository
from app.repositories.AgentRepository import AgentRepository
from app.repositories.DraftProjectRepository import DraftProjectRepository
from app.repositories.DraftAgentRepository import DraftAgentRepository
from app.services.GitlabService import GitLabService
from app.models.schemas.CommonSchemas import DuplicateAgentNameError, DuplicateProjectNameError
from app.utils.helpers.common_helpers import assert_owner
from app.enum import EnvironmentEnum
from app.models.schemas.ProjectIntakeSchemas import PaginatedProjectsWithAgentsResponse, ProjectWithAgentsResponse
from app.utils.cursor_utils import cursor_encoder

logger = logging.getLogger(__name__)


class ProjectIntakeService:
    """
    Service layer for project intake management.
    Orchestrates operations across multiple repositories.
    """

    def __init__(self, db: AsyncClient):
        """Initialize service with Firestore client and repositories."""
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.agent_repo = AgentRepository(db)
        self.draft_project_repo = DraftProjectRepository(db)
        self.draft_agent_repo = DraftAgentRepository(db)


    @staticmethod
    def _assert_unique_agent_names(
        names: "list", existing: "list" = None
    ) -> None:
        """Ensure agent ``names`` are unique within a single project.

        Compares case-insensitively and whitespace-trimmed, both among the
        incoming ``names`` and against any ``existing`` agent names already
        on the project. Blank/None names are ignored (model validation
        handles required-ness).

        Raises:
            DuplicateAgentNameError: On the first duplicate encountered.
        """
        seen = set()
        for raw in (existing or []):
            norm = (raw or "").strip().lower()
            if norm:
                seen.add(norm)
        for raw in names:
            norm = (raw or "").strip().lower()
            if not norm:
                continue
            if norm in seen:
                raise DuplicateAgentNameError(
                    f"An agent named '{raw}' already exists in this project"
                )
            seen.add(norm)

    async def _validate_upsert_agent_names(
        self, repo, project_id: str, agents: list
    ) -> None:
        """Validate agent-name uniqueness for an upsert against a project.

        Computes the project's resulting agent names after applying the
        upsert payloads and ensures they stay unique (case-insensitive,
        whitespace-trimmed). For each payload:
        - update of an existing agent (matching ``id`` under this project):
          its effective name is the payload ``name`` when provided, else the
          agent's current name;
        - create (no ``id``, or an ``id`` not under this project): the payload
          ``name`` is used.
        Existing agents not mentioned in the payload keep their current name.

        Raises:
            DuplicateAgentNameError: If two agents would share a name.
        """
        current = await repo.get_by_project(project_id)
        # Map existing agent id -> current name for quick lookup.
        current_by_id = {str(a.id): (a.name or "") for a in current}
        touched_ids = set()
        effective_names = []

        for agent_update in agents:
            data = agent_update.model_dump(exclude_unset=True, exclude_none=True)
            agent_id = data.get("id")
            name = data.get("name")
            if agent_id and str(agent_id) in current_by_id:
                touched_ids.add(str(agent_id))
                effective_names.append(
                    name if name is not None else current_by_id[str(agent_id)]
                )
            else:
                # New agent (or id not under this project -> treated as new).
                if name is not None:
                    effective_names.append(name)

        # Existing agents left untouched keep their names in the project.
        untouched = [
            nm for aid, nm in current_by_id.items() if aid not in touched_ids
        ]
        self._assert_unique_agent_names(effective_names, existing=untouched)

    # ========================================================================
    # NON-DRAFT PROJECT OPERATIONS
    # ========================================================================

    async def create_project(
        self, project: Project, agents: List[Agent]
    ) -> Dict[str, Any]:
        """
        Create a new project with associated agents.

        Args:
            project: Project instance with all required fields
            agents: List of Agent instances to associate with the project

        Returns:
            Dict with the created ``project`` and its ``agents``.

        Raises:
            DuplicateProjectNameError: If a published project already uses an
                equivalent name (names are unique across the collection).
            ValueError: If project validation fails
            Exception: If database operation fails
        """
        try:
            # Published project names must be unique across the collection.
            if await self.project_repo.name_exists(project.name):
                raise DuplicateProjectNameError(
                    f"A published project named '{project.name}' already exists"
                )

            # Agent names must be unique within the project.
            self._assert_unique_agent_names([a.name for a in (agents or [])])

            # Create the project
            created_project = await self.project_repo.create(project)
            logger.info(f"Project created: {created_project.id}")

            # Create associated agents
            created_agents: List[Agent] = []
            if agents:
                for agent in agents:
                    # Ensure agent has correct project_id and is stored under
                    # Projects/{project_id}/Agents/{agent_id}.
                    agent.project_id = created_project.id
                    created_agent  = await self.agent_repo.create(
                        agent, project_id=created_project.id
                    )
                    created_agents.append(created_agent)
                    if created_agent.gitlab_repo_url:
                        gitlab_service = GitLabService(self.db)
                        asyncio.create_task(
                            gitlab_service.resolve_and_patch_gitlab_project_id(
                                agent_id=created_agent.id,
                                project_id=created_project.id,
                                repo_url=created_agent.gitlab_repo_url,
                            )
                        )
                logger.info(f"Created {len(agents)} agents for project {created_project.id}")
            updated_project = await self._update_project_is_agent_system_staged(created_project.id)
            return {"project": updated_project if updated_project else created_project, "agents": created_agents}
        except Exception as e:
            logger.exception(f"Error creating project: {str(e)}")
            raise


    async def _update_project_is_agent_system_staged(self, project_id: str) -> Optional[Project]:
        """
        Checks if ALL agents under the project have environment=Staging.
        If yes, sets project.is_agent_system_staged = True.
        """
        try:
            project = await self.project_repo.get(project_id)
            agents = await self.agent_repo.get_by_project(project_id)

            if not agents:
                project.is_agent_system_staged = False
            else:
                all_staged = all(
                    agent.environment in (EnvironmentEnum.STAGING, EnvironmentEnum.PRODUCTION)
                    for agent in agents
                )
                project.is_agent_system_staged = all_staged

            await self.project_repo.update(project)
            logger.info(
                f"Project {project_id} → is_agent_system_staged={project.is_agent_system_staged} "
                f"({len(agents)} agents checked)"
            )
            return project
        except Exception as e:
            logger.error(f"❌ Failed to update is_agent_system_staged for project {project_id}: {e}")
            return None

    async def list_projects_paginated(
        self,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
        include_agents: bool = False,
    ) -> PaginatedProjectsWithAgentsResponse:
        """
        List published projects using cursor pagination.

        By default agents are NOT included (one query, lighter payload). When
        ``include_agents`` is true, each project is bundled with its agents
        (one extra query per project).

        ``total`` is the count of all projects matching ``filters`` (the whole
        result set, not just the current page). The exact same ``filters`` are
        passed to both the page query and the count so the two always agree.

        Args:
            page_size: Maximum number of projects per page.
            cursor: Encrypted pagination cursor from a previous response.
            include_agents: When true, include each project's agents.
            filters: Optional ``{field: value}`` filters applied identically to
                the page query and the total count.

        Returns:
            Dict with ``items`` (camelCase project dicts, or
            ``{"project", "agents"}`` dicts when ``include_agents`` is true),
            ``total``, ``next_cursor`` and ``prev_cursor``.
        """
        try:
            # Same filters drive both the page and the total count.
            paginated_projects = await self.project_repo.get_all_projects_paginated(
                page_size=page_size,
                cursor=cursor,
            )

            items: List[ProjectWithAgentsResponse] = []
            for project in paginated_projects.items:
                if include_agents:
                    agents = await self.agent_repo.get_by_project(str(project.id))
                    items.append(
                        ProjectWithAgentsResponse(
                            project=project,
                            agents= agents,
                        )
                    )
                else:
                    items.append(ProjectWithAgentsResponse(project=project))

            logger.info(
                f"Listed {len(items)} of {paginated_projects.total} projects "
                f"(include_agents={include_agents})"
            )
            return PaginatedProjectsWithAgentsResponse(
                items=items,
                total=paginated_projects.total,
                next_cursor=paginated_projects.next_cursor,
                prev_cursor=paginated_projects.prev_cursor,
            )
        except Exception as e:
            logger.exception(f"Error listing projects: {str(e)}")
            raise

    async def search_projects_paginated(
        self,
        term: str,
        page_size: Optional[int] = None,
        cursor: Optional[str] = None,
        include_agents: bool = False,
    ) -> Dict[str, Any]:
        """Search published projects (and their agents) by a single term.

        This is an **in-memory** search: all projects and all agents are loaded
        once and filtered in Python. This keeps matching flexible (case-
        insensitive, partial / "contains" on names) and avoids Firestore index
        and ``__key__`` constraints. It is intended for the published-project
        catalogue, which is small enough to scan; revisit if that grows large.

        The term is matched against:
        - project id (exact, case-insensitive),
        - project name (partial / contains, case-insensitive),
        - project owners and their emails (partial / contains, case-insensitive):
          business_owner, business_owner_email, product_owner,
          product_owner_email, technical_owner, technical_owner_email,
        - agent id (exact, case-insensitive),
        - agent name (partial / contains, case-insensitive).

        A project is included when it matches directly or when any of its agents
        matches (the agent's ``project_id`` pulls the project in).

        Pagination over the matched set is offset-based using the same cursor
        envelope as the list endpoint; ``page`` carries the zero-based index.

        Args:
            term: The search term.
            page_size: Maximum number of projects per page.
            cursor: Pagination cursor from a previous search response.
            include_agents: When true, bundle each project's agents.

        Returns:
            Dict with ``items`` (project dicts, or ``{"project", "agents"}``
            dicts when ``include_agents`` is true), ``total`` (size of the whole
            matched set), ``next_cursor`` and ``prev_cursor``.
        """
        term = (term or "").strip()
        if not term:
            # No term -> behave like a normal (empty-filter) listing.
            return await self.list_projects_paginated(
                page_size=page_size,
                cursor=cursor,
                include_agents=include_agents,
            )

        try:
            needle = term.lower()

            # Load the whole catalogue once and match in memory.
            all_projects = await self.project_repo.get_all()
            all_agents = await self.agent_repo.get_all_agents()

            # Group agents by project for matching and (optional) bundling.
            agents_by_project: Dict[str, List[Any]] = {}
            for agent in all_agents:
                agents_by_project.setdefault(str(agent.project_id), []).append(agent)

            # Project fields searched with partial (contains) matching.
            project_text_fields = (
                "name",
                "business_owner",
                "business_owner_email",
                "product_owner",
                "product_owner_email",
                "technical_owner",
                "technical_owner_email",
            )

            def _matches_project(project) -> bool:
                if str(project.id).lower() == needle:
                    return True
                for field_name in project_text_fields:
                    if needle in (getattr(project, field_name, None) or "").lower():
                        return True
                # Any associated agent matching also surfaces the project.
                for agent in agents_by_project.get(str(project.id), []):
                    if str(agent.id).lower() == needle:
                        return True
                    if needle in (agent.name or "").lower():
                        return True
                return False

            matched = [p for p in all_projects if _matches_project(p)]

            total = len(matched)
            if total == 0:
                return PaginatedProjectsWithAgentsResponse(
                    items=[],
                    total=0,
                    next_cursor=None,
                    prev_cursor=None,
                )

            # Stable ordering: newest first, tie-break by id for determinism.
            matched.sort(
                key=lambda p: (getattr(p, "created_utc", None), str(p.id)),
                reverse=True,
            )

            page = 0
            if cursor:
                try:
                    cursor_data = cursor_encoder.decode_cursor_base64(cursor)
                    page = max(0, cursor_data.page)
                except ValueError:
                    raise
                except Exception as exc:
                    logger.warning(f"Invalid search cursor: {exc}")
                    raise ValueError("Invalid or tampered pagination cursor")

            if page_size:
                start = page * page_size
                end = start + page_size
                page_projects = matched[start:end]
                has_next = end < total
                has_prev = page > 0
            else:
                page_projects = matched
                has_next = False
                has_prev = False

            next_cursor = (
                cursor_encoder.encode_cursor_base64(page=page + 1, direction="next")
                if has_next
                else None
            )
            prev_cursor = (
                cursor_encoder.encode_cursor_base64(page=page - 1, direction="prev")
                if has_prev
                else None
            )

            items: List[ProjectWithAgentsResponse] = []
            for project in page_projects:
                if include_agents:
                    project_agents = agents_by_project.get(str(project.id), [])
                    items.append(
                        ProjectWithAgentsResponse(
                            project=project,
                            agents=project_agents
                        )
                    )
                else:
                    items.append(ProjectWithAgentsResponse(project=project))

            logger.info(
                f"Search '{term}' matched {total} projects; "
                f"returning page {page} ({len(items)} items, "
                f"include_agents={include_agents})"
            )
            return PaginatedProjectsWithAgentsResponse(
                items=items,
                total=total,
                next_cursor=next_cursor,
                prev_cursor=prev_cursor,
            )
        except ValueError:
            raise
        except Exception as e:
            logger.exception(f"Error searching projects for term '{term}': {str(e)}")
            raise

    async def get_project_with_agents(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a project with all its associated agents.

        Args:
            project_id: UUID of the project

        Returns:
            Dictionary containing project and agents, or None if not found
        """
        try:
            project = await self.project_repo.get(project_id)
            if not project:
                return None

            agents = await self.agent_repo.get_by_project(project_id)

            # include_document_id=True so the project and each agent carry their
            # own id, matching the create/list/publish responses.
            return {
                "project": project.to_dict(
                    to_camel=True,
                    date_format_iso=True,
                    include_document_id=True,
                ),
                "agents": [
                    agent.to_dict(
                        to_camel=True,
                        date_format_iso=True,
                        include_document_id=True,
                    )
                    for agent in agents
                ],
            }
        except Exception as e:
            logger.exception(f"Error retrieving project {project_id}: {str(e)}")
            raise

    async def get_agents_by_project(self, project_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all agents associated with a project.

        Args:
            project_id: UUID of the project

        Returns:
            List of agents (camelCase dicts) for the project. Empty if none.
        """
        try:
            agents = await self.agent_repo.get_by_project(project_id)
            return [
                agent.to_dict(
                    to_camel=True,
                    date_format_iso=True,
                    include_document_id=True,
                )
                for agent in agents
            ]
        except Exception as e:
            logger.exception(f"Error retrieving agents for project {project_id}: {str(e)}")
            raise

    async def get_agent(self, project_id: str, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single agent that belongs to a project.

        Args:
            project_id: UUID of the project
            agent_id: UUID of the agent

        Returns:
            The agent (camelCase dict), or None if the agent does not exist
            or does not belong to the given project.
        """
        try:
            agent = await self.agent_repo.get(agent_id, project_id=project_id)
            if not agent or str(agent.project_id) != project_id:
                return None
            return agent.to_dict(
                to_camel=True,
                date_format_iso=True,
                include_document_id=True,
            )
        except Exception as e:
            logger.exception(
                f"Error retrieving agent {agent_id} for project {project_id}: {str(e)}"
            )
            raise

    async def update_project(
        self,
        project_id: str,
        project: ProjectUpdate,
        agents: List[AgentUpdate],
        author: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Partially update an existing project and upsert its associated agents.

        Merge semantics:
        - Only fields explicitly provided on ``project`` are updated; all other
          project fields are left untouched.
        - Each agent in ``agents`` is upserted:
            * if it has an ``id`` that matches an existing agent, only the
              provided fields are merged into that agent;
            * if it has no ``id`` (or an ``id`` that does not match), a new agent
              is created for the project.
        - Agents that are not present in ``agents`` are left untouched (no delete).
        - ``author`` (when provided) is set from the authenticated token onto the
          project and any upserted agents; it is never accepted from the body.

        Args:
            project_id: ID of the project to update
            project: Partial project fields to merge
            agents: Partial agent payloads to upsert
            author: Authenticated author from the access token

        Returns:
            Dict with the updated ``project`` and its current ``agents``,
            or None if the project does not exist.
        """
        try:
            # Verify project exists
            existing_project = await self.project_repo.get(project_id)
            if not existing_project:
                return None

            # Only the creator may edit the project
            assert_owner(existing_project.author, author, "project", project_id)

            # Merge only the fields the client actually sent
            changed = project.model_dump(exclude_unset=True, exclude_none=True)
            changed.pop("id", None)  # id is path-controlled, never client-set
            changed.pop("author", None)  # author is server-controlled

            # If the name is changing, it must stay unique across the collection
            # (excluding this project so an unchanged name never self-collides).
            new_name = changed.get("name")
            if new_name is not None and await self.project_repo.name_exists(
                new_name, exclude_id=project_id
            ):
                raise DuplicateProjectNameError(
                    f"A published project named '{new_name}' already exists"
                )

            merged_project = existing_project.model_copy(update=changed)
            merged_project.id = project_id
            if author:
                merged_project.author = author
            updated_project = await self.project_repo.update(merged_project)
            logger.info(
                f"Project {project_id} updated with fields: {list(changed.keys())}"
            )

            # Upsert agents and return only those updated/created in this request
            affected_agents = await self._upsert_agents(project_id, agents, author=author)

            updated = await self._update_project_is_agent_system_staged(project_id)

            return {"project": updated if updated else updated_project, "agents": affected_agents}
        except Exception as e:
            logger.exception(f"Error updating project {project_id}: {str(e)}")
            raise

    async def _upsert_agents(
        self, project_id: str, agents: List[AgentUpdate], author: Optional[str] = None
    ) -> List[Agent]:
        """Upsert agents for a project (non-destructive).

        Updates agents by id (partial merge) and creates agents without an id.
        Agents not present in the payload are left untouched. ``author`` (when
        provided) is stamped from the token onto every upserted agent.

        Returns:
            The list of agents that were updated or created in this request.
        """
        affected: List[Agent] = []
        if not agents:
            return affected

        await self._validate_upsert_agent_names(
            self.agent_repo, project_id, agents
        )

        for agent_update in agents:
            changed = agent_update.model_dump(exclude_unset=True, exclude_none=True)
            agent_id = changed.pop("id", None)
            changed.pop("author", None)  # author is server-controlled        
            if agent_id:
                existing_agent = await self.agent_repo.get(
                    agent_id, project_id=project_id
                )
                if existing_agent and str(existing_agent.project_id) == project_id:
                    # Only the creator may edit an existing agent
                    assert_owner(
                        existing_agent.author, author, "agent", agent_id
                    )
                    merged_agent = existing_agent.model_copy(update=changed)
                    merged_agent.id = agent_id
                    merged_agent.project_id = project_id
                    if author:
                        merged_agent.author = author
                    if len(changed["gitlab_repo_url"]) <= 0:
                        changed["gitlab_project_id"] = None
                        
                    updated_agent = await self.agent_repo.update(
                        merged_agent, project_id=project_id
                    )
                    affected.append(updated_agent)
                    if "gitlab_repo_url" in changed:
                        gitlab_service = GitLabService(self.db)
                        asyncio.create_task(
                            gitlab_service.resolve_and_patch_gitlab_project_id(
                                agent_id=updated_agent.id,
                                project_id=project_id,
                                repo_url=updated_agent.gitlab_repo_url,
                            )
                        )
                    logger.info(
                        f"Agent {agent_id} updated with fields: {list(changed.keys())}"
                    )
                    continue
                # id provided but not found under this project -> treat as new
                logger.info(
                    f"Agent id {agent_id} not found for project {project_id}; creating new agent"
                )

            # Create a new agent from the provided fields
            changed["project_id"] = project_id
            if author:
                changed["author"] = author
            new_agent = Agent(**changed)
            affected.append(
                await self.agent_repo.create(new_agent, project_id=project_id)
            )
            logger.info(f"Created new agent for project {project_id}")

        return affected

    async def delete_project(
        self, project_id: str, author: Optional[str] = None
    ) -> bool:
        """
        Delete a project and all its associated agents.

        Args:
            project_id: UUID of the project to delete
            author: Authenticated author from the access token; must match the
                project's creator.

        Returns:
            True if deleted, False if not found

        Raises:
            NotAuthorizedError: If ``author`` does not own the project.
        """
        try:
            # Verify project exists
            existing_project = await self.project_repo.get(project_id)
            if not existing_project:
                return False

            # Only the creator may delete the project
            assert_owner(existing_project.author, author, "project", project_id)

            # Delete all associated agents
            agents = await self.agent_repo.get_by_project(project_id)
            for agent in agents:
                await self.agent_repo.delete(str(agent.id), project_id=project_id)
            logger.info(f"Deleted {len(agents)} agents for project {project_id}")

            # Delete the project
            deleted = await self.project_repo.delete(project_id)
            logger.info(f"Project deleted: {project_id}")
            return deleted
        except Exception as e:
            logger.exception(f"Error deleting project {project_id}: {str(e)}")
            raise

    async def delete_agent(
        self, project_id: str, agent_id: str, author: Optional[str] = None
    ) -> bool:
        """
        Delete a specific agent from a project.

        Args:
            project_id: UUID of the project
            agent_id: UUID of the agent to delete
            author: Authenticated author from the access token; must match the
                agent's creator.

        Returns:
            True if deleted, False if not found

        Raises:
            NotAuthorizedError: If ``author`` does not own the agent.
        """
        try:
            agent = await self.agent_repo.get(agent_id, project_id=project_id)
            if not agent or str(agent.project_id) != project_id:
                return False

            # Only the creator may delete the agent
            assert_owner(agent.author, author, "agent", agent_id)

            deleted = await self.agent_repo.delete(agent_id, project_id=project_id)
            logger.info(f"Agent {agent_id} deleted from project {project_id}")
            await self._update_project_is_agent_system_staged(project_id)
            return deleted
        except Exception as e:
            logger.exception(
                f"Error deleting agent {agent_id} from project {project_id}: {str(e)}"
            )
            raise

    # ========================================================================
    # DRAFT PROJECT OPERATIONS
    # ========================================================================

    async def create_draft_project(
        self, project: DraftProject, agents: List[DraftAgent]
    ) -> Dict[str, Any]:
        """
        Create a new draft project with optional draft agents.

        Args:
            project: DraftProject instance (only id and name required)
            agents: List of DraftAgent instances (optional)

        Returns:
            Dict with the created ``project`` and its ``agents``.

        Raises:
            DuplicateProjectNameError: If the author already has a draft with an
                equivalent name (draft names are unique per author).
        """
        try:
            # Draft names are unique per author, not across the whole collection.
            if project.author and await self.draft_project_repo.name_exists_for_author(
                project.name, project.author
            ):
                raise DuplicateProjectNameError(
                    f"You already have a draft project named '{project.name}'"
                )

            # Agent names must be unique within the draft project.
            self._assert_unique_agent_names([a.name for a in (agents or [])])

            # Create the draft project
            created_project = await self.draft_project_repo.create(project)
            logger.info(f"Draft project created: {created_project.id}")

            # Create associated draft agents
            created_agents: List[DraftAgent] = []
            if agents:
                for agent in agents:
                    agent.project_id = created_project.id
                    created_agents.append(
                        await self.draft_agent_repo.create(
                            agent, project_id=created_project.id
                        )
                    )
                logger.info(
                    f"Created {len(agents)} draft agents for draft project {created_project.id}"
                )

            return {"project": created_project, "agents": created_agents}
        except Exception as e:
            logger.exception(f"Error creating draft project: {str(e)}")
            raise

    async def get_draft_projects_by_author(
        self, author: str
    ) -> List[Dict[str, Any]]:
        """
        Retrieve all draft projects created by an author, each with its agents.

        Drafts are author-oriented: only the author who created a draft can see
        it. This returns every draft project whose ``author`` matches, together
        with that draft's associated draft agents.

        Args:
            author: Authenticated author from the access token.

        Returns:
            A list of dicts, each with the draft ``project`` and its ``agents``
            (camelCase). Empty list if the author has no drafts.
        """
        try:
            projects = await self.draft_project_repo.get_by_field(
                "author", "==", author
            )

            results: List[Dict[str, Any]] = []
            for project in projects:
                agents = await self.draft_agent_repo.get_by_project(str(project.id))
                # include_document_id=True so each draft (and agent) carries its
                # id, which the client needs to open/edit a specific draft.
                results.append(
                    {
                        "project": project.to_dict(
                            to_camel=True,
                            date_format_iso=True,
                            include_document_id=True,
                        ),
                        "agents": [
                            agent.to_dict(
                                to_camel=True,
                                date_format_iso=True,
                                include_document_id=True,
                            )
                            for agent in agents
                        ],
                    }
                )
            logger.info(f"Retrieved {len(results)} draft projects for author {author}")
            return results
        except Exception as e:
            logger.exception(f"Error retrieving draft projects for author {author}: {str(e)}")
            raise

    async def count_draft_projects_by_author(self, author: str) -> int:
        """
        Count the draft projects created by a specific author.

        Drafts are author-oriented: this counts only the drafts whose
        ``author`` matches the authenticated author.

        Args:
            author: Authenticated author from the access token.

        Returns:
            The number of draft projects owned by the author.
        """
        try:
            count = await self.draft_project_repo.count_all(
                filters={"author": author}
            )
            logger.info(f"Counted {count} draft projects for author {author}")
            return count
        except Exception as e:
            logger.exception(
                f"Error counting draft projects for author {author}: {str(e)}"
            )
            raise

    async def get_draft_project_with_agents(
        self, draft_project_id: str, author: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a draft project with all its associated draft agents.

        Drafts are author-oriented: when ``author`` is provided, only the
        creating author may read the draft.

        Args:
            draft_project_id: UUID of the draft project
            author: Authenticated author from the access token; must match the
                draft project's creator.

        Returns:
            Dictionary containing the draft project and its draft agents,
            or None if not found.

        Raises:
            NotAuthorizedError: If ``author`` does not own the draft project.
        """
        try:
            project = await self.draft_project_repo.get(draft_project_id)
            if not project:
                return None

            # Only the creator may read the draft project
            assert_owner(project.author, author, "draft project", draft_project_id)

            agents = await self.draft_agent_repo.get_by_project(draft_project_id)

            # include_document_id=True so the draft project and each draft agent
            # carry their own id, matching the list/publish responses.
            return {
                "project": project.to_dict(
                    to_camel=True,
                    date_format_iso=True,
                    include_document_id=True,
                ),
                "agents": [
                    agent.to_dict(
                        to_camel=True,
                        date_format_iso=True,
                        include_document_id=True,
                    )
                    for agent in agents
                ],
            }
        except Exception as e:
            logger.exception(f"Error retrieving draft project {draft_project_id}: {str(e)}")
            raise

    async def get_draft_agent(
        self, draft_project_id: str, agent_id: str, author: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single draft agent that belongs to a draft project.

        Drafts are author-oriented: when ``author`` is provided, only the
        creating author may read the draft agent.

        Args:
            draft_project_id: UUID of the draft project
            agent_id: UUID of the draft agent
            author: Authenticated author from the access token; must match the
                draft agent's creator.

        Returns:
            The draft agent (camelCase dict), or None if it does not exist
            or does not belong to the given draft project.

        Raises:
            NotAuthorizedError: If ``author`` does not own the draft agent.
        """
        try:
            agent = await self.draft_agent_repo.get(
                agent_id, project_id=draft_project_id
            )
            if not agent or str(agent.project_id) != draft_project_id:
                return None

            # Only the creator may read the draft agent
            assert_owner(agent.author, author, "draft agent", agent_id)

            return agent.to_dict(
                to_camel=True,
                date_format_iso=True,
                include_document_id=True,
            )
        except Exception as e:
            logger.exception(
                f"Error retrieving draft agent {agent_id} for draft project {draft_project_id}: {str(e)}"
            )
            raise

    async def update_draft_project(
        self,
        draft_project_id: str,
        project: DraftProjectUpdate,
        agents: List[DraftAgentUpdate],
        author: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Partially update an existing draft project and upsert its draft agents.

        Merge semantics mirror ``update_project``:
        - Only fields explicitly provided on ``project`` are updated.
        - Draft agents are upserted by ``id``; agents without an ``id`` are
          created; agents not present in the payload are left untouched.
        - ``author`` (when provided) is set from the token onto the draft
          project and any upserted draft agents.

        Args:
            draft_project_id: ID of the draft project
            project: Partial draft project fields to merge
            agents: Partial draft agent payloads to upsert
            author: Authenticated author from the access token

        Returns:
            Dict with the updated ``project`` and its current ``agents``,
            or None if the draft project does not exist.
        """
        try:
            # Verify draft project exists
            existing_project = await self.draft_project_repo.get(draft_project_id)
            if not existing_project:
                return None

            # Only the creator may edit the draft project
            assert_owner(
                existing_project.author, author, "draft project", draft_project_id
            )

            # Merge only the fields the client actually sent
            changed = project.model_dump(exclude_unset=True, exclude_none=True)
            changed.pop("id", None)
            changed.pop("author", None)  # author is server-controlled

            # If the name is changing, it must stay unique within this author's
            # drafts (excluding this draft so an unchanged name never collides).
            new_name = changed.get("name")
            scope_author = author or existing_project.author
            if (
                new_name is not None
                and scope_author
                and await self.draft_project_repo.name_exists_for_author(
                    new_name, scope_author, exclude_id=draft_project_id
                )
            ):
                raise DuplicateProjectNameError(
                    f"You already have a draft project named '{new_name}'"
                )

            merged_project = existing_project.model_copy(update=changed)
            merged_project.id = draft_project_id
            if author:
                merged_project.author = author
            updated_project = await self.draft_project_repo.update(merged_project)
            logger.info(
                f"Draft project {draft_project_id} updated with fields: {list(changed.keys())}"
            )

            # Upsert draft agents and return only those updated/created
            affected_agents = await self._upsert_draft_agents(
                draft_project_id, agents, author=author
            )

            return {"project": updated_project, "agents": affected_agents}
        except Exception as e:
            logger.exception(f"Error updating draft project {draft_project_id}: {str(e)}")
            raise

    async def _upsert_draft_agents(
        self,
        draft_project_id: str,
        agents: List[DraftAgentUpdate],
        author: Optional[str] = None,
    ) -> List[DraftAgent]:
        """Upsert draft agents for a draft project (non-destructive).

        ``author`` (when provided) is stamped from the token onto every
        upserted draft agent.

        Returns:
            The list of draft agents updated or created in this request.
        """
        affected: List[DraftAgent] = []
        if not agents:
            return affected

        await self._validate_upsert_agent_names(
            self.draft_agent_repo, draft_project_id, agents
        )

        for agent_update in agents:
            changed = agent_update.model_dump(exclude_unset=True, exclude_none=True)
            agent_id = changed.pop("id", None)
            changed.pop("author", None)  # author is server-controlled

            if agent_id:
                existing_agent = await self.draft_agent_repo.get(
                    agent_id, project_id=draft_project_id
                )
                if existing_agent and str(existing_agent.project_id) == draft_project_id:
                    # Only the creator may edit an existing draft agent
                    assert_owner(
                        existing_agent.author, author, "draft agent", agent_id
                    )
                    merged_agent = existing_agent.model_copy(update=changed)
                    merged_agent.id = agent_id
                    merged_agent.project_id = draft_project_id
                    if author:
                        merged_agent.author = author
                    affected.append(
                        await self.draft_agent_repo.update(
                            merged_agent, project_id=draft_project_id
                        )
                    )
                    logger.info(
                        f"Draft agent {agent_id} updated with fields: {list(changed.keys())}"
                    )
                    continue
                logger.info(
                    f"Draft agent id {agent_id} not found for draft project {draft_project_id}; creating new"
                )

            changed["project_id"] = draft_project_id
            if author:
                changed["author"] = author
            new_agent = DraftAgent(**changed)
            affected.append(
                await self.draft_agent_repo.create(
                    new_agent, project_id=draft_project_id
                )
            )
            logger.info(f"Created new draft agent for draft project {draft_project_id}")

        return affected

    async def delete_draft_project(
        self, draft_project_id: str, author: Optional[str] = None
    ) -> bool:
        """
        Delete a draft project and all its associated draft agents.

        Args:
            draft_project_id: UUID of the draft project
            author: Authenticated author from the access token; must match the
                draft project's creator.

        Returns:
            True if deleted, False if not found

        Raises:
            NotAuthorizedError: If ``author`` does not own the draft project.
        """
        try:
            # Verify draft project exists
            existing_project = await self.draft_project_repo.get(draft_project_id)
            if not existing_project:
                return False

            # Only the creator may delete the draft project
            assert_owner(
                existing_project.author, author, "draft project", draft_project_id
            )

            # Delete all associated draft agents
            agents = await self.draft_agent_repo.get_by_project(draft_project_id)
            for agent in agents:
                await self.draft_agent_repo.delete(
                    str(agent.id), project_id=draft_project_id
                )
            logger.info(f"Deleted {len(agents)} draft agents for draft project {draft_project_id}")

            # Delete the draft project
            deleted = await self.draft_project_repo.delete(draft_project_id)
            logger.info(f"Draft project deleted: {draft_project_id}")
            return deleted
        except Exception as e:
            logger.exception(f"Error deleting draft project {draft_project_id}: {str(e)}")
            raise

    async def delete_draft_agent(
        self, draft_project_id: str, agent_id: str, author: Optional[str] = None
    ) -> bool:
        """
        Delete a specific draft agent from a draft project.

        Args:
            draft_project_id: UUID of the draft project
            agent_id: UUID of the draft agent to delete
            author: Authenticated author from the access token; must match the
                draft agent's creator.

        Returns:
            True if deleted, False if not found

        Raises:
            NotAuthorizedError: If ``author`` does not own the draft agent.
        """
        try:
            agent = await self.draft_agent_repo.get(
                agent_id, project_id=draft_project_id
            )
            if not agent or str(agent.project_id) != draft_project_id:
                return False

            # Only the creator may delete the draft agent
            assert_owner(agent.author, author, "draft agent", agent_id)

            deleted = await self.draft_agent_repo.delete(
                agent_id, project_id=draft_project_id
            )
            logger.info(f"Draft agent {agent_id} deleted from draft project {draft_project_id}")
            return deleted
        except Exception as e:
            logger.exception(
                f"Error deleting draft agent {agent_id} from draft project {draft_project_id}: {str(e)}"
            )
            raise

    # ========================================================================
    # DRAFT TO NON-DRAFT CONVERSION
    # ========================================================================

    async def publish_draft_project(
        self, draft_project_id: str, author: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Publish a draft project as a non-draft (production) project.

        Drafts are author-oriented: when ``author`` is provided, only the
        creating author may publish the draft.

        This operation:
        1. Retrieves the draft project and its draft agents
        2. Builds a Project from the stored draft data (no payload required)
        3. Creates a new project with the same ID
        4. Creates new agents with the same IDs
        5. Deletes the draft project and draft agents

        The draft must already contain all fields required by ``Project``;
        otherwise a ``ValidationError`` is raised.

        Args:
            draft_project_id: UUID of the draft project
            author: Authenticated author from the access token; must match the
                draft project's creator.

        Returns:
            Dict with the published ``project`` and its ``agents``,
            or None if the draft project does not exist.

        Raises:
            NotAuthorizedError: If ``author`` does not own the draft project.
        """
        try:
            # Verify draft project exists
            draft_project = await self.draft_project_repo.get(draft_project_id)
            if not draft_project:
                return None

            # Only the creator may publish the draft project
            assert_owner(
                draft_project.author, author, "draft project", draft_project_id
            )

            # Get all draft agents
            draft_agents = await self.draft_agent_repo.get_by_project(draft_project_id)
            logger.info(f"Found {len(draft_agents)} draft agents for draft project {draft_project_id}")

            # Agent names must be unique within the project being published.
            self._assert_unique_agent_names([a.name for a in draft_agents])

            # Build the production project from the stored draft data.
            # Project enforces the required fields; an incomplete draft raises
            # a ValidationError that the router surfaces as a 400.
            project = Project(
                **draft_project.model_dump(exclude_none=True)
            )

            # Set the project ID to match the draft project
            project.id = draft_project_id

            # Published names are globally unique. Exclude this id so re-publishing
            # never self-collides, then reject if another project owns the name.
            if await self.project_repo.name_exists(
                project.name, exclude_id=draft_project_id
            ):
                raise DuplicateProjectNameError(
                    f"A published project named '{project.name}' already exists"
                )

            # Create the non-draft project
            created_project = await self.project_repo.create(project)
            logger.info(f"Published project created: {created_project.id}")

            # Create non-draft agents from draft agents
            created_agents: List[Agent] = []
            for draft_agent in draft_agents:
                # Convert DraftAgent to Agent
                agent = Agent(
                    id=draft_agent.id,
                    project_id=created_project.id,
                    author=draft_agent.author,
                    platform=draft_agent.platform,
                    name=draft_agent.name,
                    purpose=draft_agent.purpose,
                    gitlab_repo_url=draft_agent.gitlab_repo_url,
                    endpoint=draft_agent.endpoint,
                    primary_input_channels=draft_agent.primary_input_channels,
                    primary_output_channels=draft_agent.primary_output_channels,
                    observability_dashboard_for_traces=draft_agent.observability_dashboard_for_traces,
                    observability_dashboard_logs_metrics=draft_agent.observability_dashboard_logs_metrics,
                )
                created_agents.append(
                    await self.agent_repo.create(
                        agent, project_id=created_project.id
                    )
                )
            logger.info(f"Created {len(draft_agents)} agents for published project {created_project.id}")

            # Delete draft agents
            for draft_agent in draft_agents:
                await self.draft_agent_repo.delete(
                    str(draft_agent.id), project_id=draft_project_id
                )
            logger.info(f"Deleted {len(draft_agents)} draft agents")

            # Delete draft project
            await self.draft_project_repo.delete(draft_project_id)
            logger.info(f"Deleted draft project {draft_project_id}")
            updated_project = await self._update_project_is_agent_system_staged(created_project.id)
            return {"project": updated_project if updated_project else created_project, "agents": created_agents}
        except Exception as e:
            logger.exception(f"Error publishing draft project {draft_project_id}: {str(e)}")
            raise


    

