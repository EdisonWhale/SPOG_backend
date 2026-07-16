"""
Use Case Service

Business logic layer for AI Governance use cases.

Use cases are created and updated internally by the system (no API routes).
A use case may only be created for an existing *published* project; the service
enforces this by verifying the project exists before persisting the use case.

Flow: (internal caller) -> Service -> Repository -> AsyncDocumentRepository
"""

import logging
from fastapi import HTTPException
from typing import List, Optional, Dict, Any
from google.cloud.firestore import AsyncClient
from app.models.usecase.UseCase import UseCase
from app.models.project.Project import Project
from app.models.agent.PrimaryInputChannels import PrimaryInputChannels
from app.models.agent.Agent import Agent
from app.models.usecase.UseCaseUpdate import UseCaseUpdate
from app.models.snow.AIGovernanceFormVariables import AIGovernanceFormVariables
from app.repositories.UseCaseRepository import UseCaseRepository
from app.repositories.ProjectRepository import ProjectRepository
from app.repositories.AgentRepository import AgentRepository
from app.models.schemas.UseCaseSchemas import UseCaseResponse
from app.enum import EnvironmentEnum, UseCaseStatusEnum
from app.utils.helpers.common_helpers import assert_owner

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
        self.agent_repo = AgentRepository(db)

    async def create_use_case(self, project_id: str, author: str) -> UseCaseResponse:
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
            project: Project = await self.project_repo.get(project_id)
            if not project:
                raise ValueError(
                    f"Cannot create use case: project {project_id} "
                    "does not exist or is not published"
                )
            all_agents:List[Agent] = await self.agent_repo.get_by_project(project.id)
            if not all_agents:
                raise ValueError(
                    "To create an use case at least one agent in the project."
                )
            # Check if this is the first use case for the project
            existing_use_cases = await self.use_case_repo.get_by_project(project_id)

            is_first_use_case = len(existing_use_cases) == 0

            if is_first_use_case:
                non_staging = [
                    str(a.id)
                    for a in all_agents
                    if getattr(a, "environment", None) != EnvironmentEnum.STAGING.value
                ]
                if non_staging:
                    raise ValueError(
                        f"To create an use case requires all agents to be in Staging environment. "
                        f"Non-staging agent(s): {', '.join(non_staging)}"
                    )
            else:
                if not (project.active and project.locked):
                    raise ValueError(
                        "Project must be active and locked to create additional use cases."
                    )

            updated_use_case = UseCase(
                author=author, 
                status=UseCaseStatusEnum.PENDING,
                is_first=len(existing_use_cases) == 0,
                project_id=project_id
            )

            created = await self.use_case_repo.create(updated_use_case)
            if created:
                project.locked = True
                project.is_use_case_pending = True
                await self.project_repo.update(project)

            ai_governance_url = UseCaseService.generate_ai_governance_url(project, all_agents)

            logger.info(
                f"Use case {created.id} created for project {project_id} "
                f"| is_first={created.is_first}"
            )
            return UseCaseResponse(
                use_case=created,
                governance_form_url=ai_governance_url
            )
        except Exception as e:
            logger.exception(f"Error creating use case for project id :{project_id} {str(e)}")
            raise

    @staticmethod
    def summarize_agents_input_channel(agents: List[Agent]) -> str:
        channel_levels: dict[str, list[str]] = {}
        for agent in agents:
            for field_name in PrimaryInputChannels.model_fields:
                value = getattr(agent.primary_input_channels, field_name)
                if value is not None:
                    label = field_name.replace("_", " ").title()
                    data_level = value.data_level.value if value.data_level else "Unknown"
                    details = value.details if value.details else "No details"
                    entry = f"Level: {data_level} | Details: {details}"
                    channel_levels.setdefault(label, [])
                    if entry not in channel_levels[label]:
                        channel_levels[label].append(entry)

        lines = []
        for channel, levels in channel_levels.items():
            lines.append(f"• {channel}:")
            for level in levels:
                lines.append(f"    - {level}")
        return "\n".join(lines)



    
    @staticmethod
    def generate_ai_governance_url(project:Project, agents: List[Agent]) -> str:

        agents_input_channel_summary = UseCaseService.summarize_agents_input_channel(agents)
        form_variables = AIGovernanceFormVariables(
            request_title=project.name,
            what_data_does_the_system_have_access_to=agents_input_channel_summary,
            spog_project_id_leave_blank_if_this_box_is_empty=project.id
        )
        return form_variables.generate_ai_governance_url()

    async def get_ai_governance_url(self, use_case_id:str, author:str) -> str:
        try:
            use_case:UseCase = await self.get_use_case(use_case_id)

            if not use_case:
                raise HTTPException(
                    status_code=404,
                    detail=f"Use case {use_case_id} not found",
                )

            project: Project = await self.project_repo.get(use_case.project_id)
            if not project:
                raise ValueError(
                    f"Cannot create use case: project {project.id} "
                    "does not exist or is not published"
                )

            assert_owner(project.author, author, "project", project.id)
        
            all_agents:List[Agent] = await self.agent_repo.get_by_project(project.id)
            if not all_agents:
                raise ValueError(
                    "To create an use case at least one agent in the project."
                )
            ai_governance_url = UseCaseService.generate_ai_governance_url(project, all_agents)
            return ai_governance_url
        except Exception as e:
            logger.exception(f"Error generating AI governance link {use_case_id}: {str(e)}")
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
