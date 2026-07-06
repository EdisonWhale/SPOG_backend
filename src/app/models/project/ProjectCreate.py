"""
Request models for creating projects and agents.

Generated from the full ``Project`` / ``Agent`` models via ``partial_model``,
keeping a single source of truth for field definitions and validators.

``author`` and ``id`` are server-controlled, so they are **excluded** from the
request bodies entirely (a client cannot set a field the model does not have):

- ``author``: set from the authenticated Entra access token.
- ``id``: system-generated.

Other auto-managed fields (``project_id`` on agents, observability/system
fields, ``tags``, ``deprecated``) are made optional so clients don't have to
send them while the required business fields (name, purpose, owners, etc.) stay
required. The router maps these into the full ``Project`` / ``Agent`` models
(stamping the authenticated author) before persisting.
"""

from app.models.project.Project import Project
from app.models.agent.Agent import Agent
from typing import TYPE_CHECKING

from app.models.utils.partial_model import partial_model


if TYPE_CHECKING:
    # Static-typing-only declarations. ``partial_model`` builds these
    # models at runtime via ``pydantic.create_model``, which type
    # checkers see only as a value (``type[BaseModel]``) and therefore
    # reject in type-expression positions (FastAPI router annotations).
    # Declaring concrete subclasses here lets Pyright/Pylance treat them
    # as real types; the runtime assignments below remain the single
    # source of truth.
    class AgentCreate(Agent): ...

    class ProjectCreate(Project): ...


AgentCreate = partial_model(
    Agent,
    "project_id",
    "production_code_version",
    "latest_version_release_date",
    "tags",
    "deprecated",
    exclude_fields=("id", "author"),
    name="AgentCreate",
)


ProjectCreate = partial_model(
    Project,
    "tags",
    "deprecated",
    exclude_fields=("id", "author"),
    name="ProjectCreate",
)
