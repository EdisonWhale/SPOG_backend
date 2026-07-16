"""
Response schemas for project intake endpoints.

These wrap a project together with its associated agents so that create/update/
publish responses return both the project and its agents (including their IDs),
serialized in camelCase to match the rest of the API.
"""

from typing import Any, Dict, List, Optional

from app.models.base.CustomBaseModel import CustomBaseModel
from app.models.project.Project import Project
from app.models.project.DraftProject import DraftProject
from app.models.agent.Agent import Agent
from app.models.agent.DraftAgent import DraftAgent


class ProjectWithAgentsResponse(CustomBaseModel):
    """A project together with its associated agents."""

    project: Project
    agents: List[Agent] = []


class PaginatedProjects(CustomBaseModel):
    """A page of projects with encrypted cursors for navigation.

    Each item is a camelCase dict. When ``includeAgents`` is requested, each
    item has the shape ``{"project": {...}, "agents": [...]}``; otherwise each
    item is the project dict itself.
    """

    items: List[Project] = []
    total: int = 0
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None

class PaginatedProjectsWithAgentsResponse(CustomBaseModel):
    """A page of projects with encrypted cursors for navigation.

    Each item is a camelCase dict. When ``includeAgents`` is requested, each
    item has the shape ``{"project": {...}, "agents": [...]}``; otherwise each
    item is the project dict itself.
    """

    items: List[ProjectWithAgentsResponse] = []
    total: int = 0
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None


class DraftProjectWithAgentsResponse(CustomBaseModel):
    """A draft project together with its associated draft agents."""

    project: DraftProject
    agents: List[DraftAgent] = []
