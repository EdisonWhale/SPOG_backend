"""
Partial update request models for project intake.

Generated from the full ``Project`` / ``Agent`` models via ``partial_model`` so
every field is optional (partial / merge update), keeping a single source of
truth for field definitions and validators. ``author`` is included among the
optional fields because it is server-controlled (set from the access token) and
the service overwrites it; it is never required in the request body.
"""

from app.models.project.Project import Project
from app.models.agent.Agent import Agent
from typing import TYPE_CHECKING

from app.models.utils.partial_model import partial_model


if TYPE_CHECKING:
    # Static-typing-only declarations (see ProjectCreate for rationale).
    class AgentUpdate(Agent): ...

    class ProjectUpdate(Project): ...


AgentUpdate = partial_model(
    Agent,
    "id",
    "project_id",
    "author",
    "platform",
    "name",
    "purpose",
    "gitlab_repo_url",
    "endpoint",
    "primary_input_channels",
    "primary_output_channels",
    "observability_dashboard_for_traces",
    "observability_dashboard_logs_metrics",
    "production_code_version",
    "latest_version_release_date",
    "tags",
    "deprecated",
    name="AgentUpdate",
)


ProjectUpdate = partial_model(
    Project,
    "id",
    "author",
    "name",
    "purpose",
    "business_owner",
    "business_owner_email",
    "product_owner",
    "product_owner_email",
    "technical_owner",
    "technical_owner_email",
    "vp_sponsor",
    "vp_sponsor_email",
    "tags",
    "deprecated",
    "locked",
    "gitlab_sync_requested_at",
    name="ProjectUpdate",
)
