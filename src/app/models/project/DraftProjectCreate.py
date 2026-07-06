"""
Request models for creating draft projects and draft agents.

Generated from the full ``DraftProject`` / ``DraftAgent`` models via
``partial_model``, keeping a single source of truth. ``author`` and ``id`` are
server-controlled, so they are **excluded** from the request bodies entirely.

Drafts can be saved with incomplete information, so every business field is made
optional here. On a draft only ``name`` remains mandatory (it is required on
``DraftProject``/``DraftAgent`` and is the minimum needed to identify a draft);
all other fields can be filled in later before publishing.
"""

from app.models.project.DraftProject import DraftProject
from app.models.agent.DraftAgent import DraftAgent
from typing import TYPE_CHECKING

from app.models.utils.partial_model import partial_model


if TYPE_CHECKING:
    # Static-typing-only declarations (see ProjectCreate for rationale).
    class DraftAgentCreate(DraftAgent): ...

    class DraftProjectCreate(DraftProject): ...


DraftAgentCreate = partial_model(
    DraftAgent,
    "project_id",
    "platform",
    "purpose",
    "gitlab_repo_url",
    "endpoint",
    "primary_input_channels",
    "primary_output_channels",
    "observability_dashboard_for_traces",
    "observability_dashboard_logs_metrics",
    "tags",
    "deprecated",
    exclude_fields=("id", "author"),
    name="DraftAgentCreate",
)


DraftProjectCreate = partial_model(
    DraftProject,
    "tags",
    "deprecated",
    exclude_fields=("id", "author"),
    name="DraftProjectCreate",
)
