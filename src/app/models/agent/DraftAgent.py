"""
Agent model and schema definitions for SPOG Dashboard Backend.

Defines the data structure for AI agents integrated with the SPOG platform,
including their configuration, capabilities, and observability settings.
"""

import uuid
from typing import ClassVar, Optional
from pydantic import Field
from app.enum import (
    PlatformEnum,
    EnvironmentEnum
)
from app.models.base.SpogBaseModel import SpogBaseModel
from app.models.agent.PrimaryInputChannels import PrimaryInputChannels
from app.models.agent.PrimaryOutputChannels import PrimaryOutputChannels

class DraftAgent(SpogBaseModel):
    """Base schema for agent data with common fields."""

    # Draft agents are stored in an ``Agents`` subcollection under their parent
    # DraftProjects/{id} document (path: DraftProjects/{id}/Agents/{id}).
    COLLECTION_NAME: ClassVar[str] = "Agents"

    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="System-generated ID of the agent. Must not be supplied by the client.",
    )
    project_id: Optional[str] = Field(default=None, description="ID of the project this agent belongs to (assigned by the service)")
    # Draft agents can be saved with incomplete information, so every field
    # except ``name`` is optional. Required-ness is enforced later, when the
    # draft is published into a full ``Agent``.
    platform: Optional[PlatformEnum] = Field(default=None, description="Deployment platform (GCP only for now)")
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    purpose: Optional[str] = Field(default=None, min_length=1, max_length=1000, description="Agent purpose and description")
    gitlab_repo_url: Optional[str] = Field(
        None, description="GitLab repository URL for agent source code"
    )
    endpoint: Optional[str] = Field(None, description="Agent API endpoint URL")
    primary_input_channels: Optional[PrimaryInputChannels] = Field(
        None, description="Primary input channels for the agent"
    )
    primary_output_channels: Optional[PrimaryOutputChannels] = Field(
        None, description="Primary output channel for agent results"
    )
    observability_dashboard_for_traces: Optional[str] = Field(
        None, description="Dashboard URL for trace observability"
    )
    observability_dashboard_logs_metrics: Optional[str] = Field(
        None, description="Dashboard URL for logs and metrics observability"
    )
    environment: Optional[EnvironmentEnum] = Field(
        default=EnvironmentEnum.DEV, description="Agent environment"
    )
