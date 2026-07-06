"""
UseCase model definition for SPOG Dashboard Backend.

A UseCase captures the AI Governance intake details for a *published* project.
Use cases are created and updated internally by the system (no API routes) and
are mapped to a project via ``project_id``.

Unlike most entities, the ``id`` is NOT a generated UUID; it is an externally
supplied identifier string (for example, an AI Governance reference).
"""

import uuid
from typing import ClassVar, Optional
from datetime import date

from pydantic import Field

from app.models.base.CustomBaseModel import CustomBaseModel, TimestampedModel
from app.enum import UseCaseStatus


class UseCase(CustomBaseModel, TimestampedModel):
    """AI Governance use case mapped to a published project.

    Composed from ``CustomBaseModel`` (serialization/config) and
    ``TimestampedModel`` (created/updated timestamps) only. It intentionally
    does NOT include ``AuthorizableModel``, so there is no ``author`` field.
    """

    COLLECTION_NAME: ClassVar[str] = "UseCases"

    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="System-generated ID of the use case. Must not be supplied by the client.",
    )
    usecase_id: Optional[str] = Field(
        ...,
        min_length=1,
        description="Use case ID (#SCTASK id). Supplied by the system as a string (not a UUID).",
    )
    name: Optional[str] = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Use case name",
    )
    status: UseCaseStatus = Field(
        default=UseCaseStatus.PENDING,
        description="AI Governance status of the use case",
    )
    project_id: str = Field(
        ...,
        description="ID of the published project this use case is mapped to",
    )
    ai_governance_request_date: Optional[date] = Field(
        default=None,
        description="Date the AI Governance request was submitted",
    )
    ai_governance_approval_date: Optional[date] = Field(
        default=None,
        description="Date the AI Governance request was approved",
    )
    is_first: Optional[bool] = Field(
        default=False,
        description="Is the first use case created for a project",
    )
