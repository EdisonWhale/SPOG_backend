"""
Partial update request models for draft project intake.

Generated from the full ``DraftProject`` / ``DraftAgent`` models via
``partial_model`` so every field is optional, keeping a single source of truth.
``author`` is included among the optional fields because it is server-controlled
(set from the access token) and is never required in the request body.
"""

from app.models.project.DraftProject import DraftProject
from app.models.agent.DraftAgent import DraftAgent
from typing import TYPE_CHECKING

from app.models.utils.partial_model import partial_model


if TYPE_CHECKING:
    # Static-typing-only declarations (see ProjectCreate for rationale).
    class DraftAgentUpdate(DraftAgent): ...

    class DraftProjectUpdate(DraftProject): ...


DraftAgentUpdate = partial_model(
    DraftAgent,
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
    "tags",
    "deprecated",
    name="DraftAgentUpdate",
)


DraftProjectUpdate = partial_model(
    DraftProject,
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
    name="DraftProjectUpdate",
)
