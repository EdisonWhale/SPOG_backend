title = "SPoG"
version = "v1.0"
summary = "Centralized registry and governance platform for AI agents"
description = """
Highmark's **Single Pane of Glass (SPoG)** initiative aims to establish enterprise accountability, visibility, and governance for all AI agents in use. SPOG is being built to provide a centralized, high-level view of agents running across the organization, starting with a minimal setup and evolving in phases.

As agentic AI adoption accelerates, there is currently no single, authoritative system to:

- Register agents
- Track ownership
- Understand purpose and criticality
- Surface operational metadata such as versions, integrations, and release status

This project introduces **Agent Registry**, **Agent Profile**, **Agent Structure V1**, and a **Project-Multi Agent** driven intake experience, enabling standardized registration, discoverability, and governance of agents across the Google ADK platform.

The solution will act as the source of truth for agent metadata while integrating with:

- **ServiceNow** (CMDB)
- **GitLab SaaS**
- Future observability tooling
"""

# Global tags so every operation's tag is declared (operation-tag-defined).
# tags_metadata = [
#     {"name": "Project Intake", "description": "Manage production projects and their agents."},
#     {"name": "Draft Project Intake", "description": "Manage draft projects and draft agents."},
#     {"name": "Use Cases", "description": "Read AI Governance use cases."},
#     {"name": "Auth", "description": "Information about the authenticated user."},
# ]

# Servers must expose the API major version as a lowercase 'v' node
# (engen:server-url-version), e.g. /v1.
# servers = [
#     {"url": "/v1", "description": "Current major version (v1)."},
# ]

# Bearer (Microsoft Entra access token) security scheme applied globally
# (engen:api-must-have-security).
# SECURITY_SCHEME_NAME = "bearerAuth"
# security_schemes = {
#     SECURITY_SCHEME_NAME: {
#         "type": "http",
#         "scheme": "bearer",
#         "bearerFormat": "JWT",
#         "description": "Microsoft Entra access token passed as 'Authorization: Bearer <token>'.",
#     }
# }

# Contact object for the Info block (info-contact).
# contact = {
#     "name": "Highmark SPOG Team",
#     "email": "spog-team@highmark.com",
# }

metadata = dict(
    title=title,
    version=version,
    description=description,
    summary=summary,
    # contact=contact,
    root_path="/v1",
    openapi_version="3.0.1",
    # openapi_tags=tags_metadata,
    # servers=servers,
)
