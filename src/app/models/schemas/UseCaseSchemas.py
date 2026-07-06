"""
Response schemas for use case operations.

Wraps a use case together with the project it is mapped to, serialized in
camelCase to match the rest of the API.
"""

from typing import Any, Dict, List, Optional

from app.models.base.CustomBaseModel import CustomBaseModel
from app.models.project.Project import Project
from app.models.usecase.UseCase import UseCase


class UseCaseWithProjectResponse(CustomBaseModel):
    """A use case together with its mapped (published) project."""

    use_case: UseCase
    project: Project


class PaginatedUseCasesResponse(CustomBaseModel):
    """A page of use cases with encrypted cursors for navigation.

    Each item is a camelCase use case dict. ``total`` is the count of all use
    cases matching the applied filters (the whole result set, not just the
    current page).
    """

    items: List[Dict[str, Any]] = []
    total: int = 0
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None


class UseCaseListResponse(CustomBaseModel):
    """A non-paginated list of use cases.

    Used by the project-scoped endpoint, which returns *all* use cases mapped
    to a project. Each item is a camelCase use case dict and ``total`` is the
    full count of returned items.
    """

    items: List[Dict[str, Any]] = []
    total: int = 0
