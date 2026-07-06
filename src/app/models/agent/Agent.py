"""
Agent model and schema definitions for SPOG Dashboard Backend.

Defines the data structure for AI agents integrated with the SPOG platform,
including their configuration, capabilities, and observability settings.
"""
import uuid
from typing import ClassVar, Optional
from datetime import date
from pydantic import Field
from app.models.base.SpogBaseModel import SpogBaseModel
from app.enum import (
    PlatformEnum,
    EnvironmentEnum
)
from app.models.agent.PrimaryInputChannels import PrimaryInputChannels
from app.models.agent.PrimaryOutputChannels import PrimaryOutputChannels

class Agent(SpogBaseModel):
    """Base schema for agent data with common fields."""

    COLLECTION_NAME: ClassVar[str] = "Agents"

    id: Optional[str] = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="System-generated ID of the agent. Must not be supplied by the client.",
    )
    project_id: Optional[str] = Field(default=None, description="ID of the project this agent belongs to (assigned by the service)")
    platform: PlatformEnum = Field(..., description="Deployment platform (GCP only for now)")
    name: str = Field(..., min_length=1, max_length=255, description="Agent name")
    purpose: str = Field(..., min_length=1, max_length=1000, description="Agent purpose and description")
    gitlab_repo_url: str = Field(
        ..., description="GitLab repository URL for agent source code"
    )
    gitlab_project_id: Optional[int] = Field(
        None, description="GitLab project id for agent source code"
    )
    endpoint: Optional[str] = Field(None, description="Agent API endpoint URL")
    primary_input_channels: PrimaryInputChannels = Field(
        ..., description="Primary input channels for the agent"
    )
    primary_output_channels: PrimaryOutputChannels = Field(
        ..., description="Primary output channel for agent results"
    )
    observability_dashboard_for_traces: Optional[str] = Field(
        None, description="Dashboard URL for trace observability"
    )
    observability_dashboard_logs_metrics: str = Field(
        ..., description="Dashboard URL for logs and metrics observability"
    )
    # system generated fields
    production_code_version: Optional[str] = Field(
        None, description="Production code version (semantic versioning)"
    )
    latest_version_release_date: Optional[date] = Field(
        None, description="Date of latest version release"
    )
    environment: EnvironmentEnum = Field(
        default=EnvironmentEnum.DEV, description="Agent environment"
    )
