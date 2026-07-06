## Project Intake Router Implementation

This document describes the complete implementation of the project intake system for the SPOG Dashboard Backend.

### Architecture Overview

The implementation follows a layered architecture:

```
Router Layer (HTTP Endpoints)
    ↓
Service Layer (Business Logic)
    ↓
Repository Layer (Data Access)
    ↓
AsyncDocumentRepository (Base Firestore Operations)
```

### Components

#### 1. Router: `src/app/routers/project_intake_router.py`

Handles all HTTP endpoints for project and agent intake management.

**Non-Draft Project Endpoints:**
- `POST /projects` - Create a new project with agents
- `GET /projects/{project_id}` - Get project with associated agents
- `PUT /projects/{project_id}` - Update project and agents
- `DELETE /projects/{project_id}` - Delete project and all agents
- `DELETE /projects/{project_id}/agents/{agent_id}` - Delete specific agent

**Draft Project Endpoints:**
- `POST /projects/draft` - Create draft project with optional agents
- `POST /projects/draft/{draft_project_id}/publish` - Publish draft as non-draft
- `PUT /projects/draft/{draft_project_id}` - Update draft project and agents
- `DELETE /projects/draft/{draft_project_id}` - Delete draft project and agents
- `DELETE /projects/draft/{draft_project_id}/agents/{agent_id}` - Delete draft agent

#### 2. Service: `src/app/services/ProjectIntakeService.py`

Orchestrates business logic and coordinates between repositories.

**Key Responsibilities:**
- Project creation with agent association
- Project updates with agent replacement
- Project deletion with cascading agent deletion
- Draft project management
- Draft-to-production conversion (publish)
- Validation and error handling

**Methods:**
- `create_project()` - Create project with agents
- `get_project_with_agents()` - Retrieve project and agents
- `update_project()` - Update project and replace agents
- `delete_project()` - Delete project and agents
- `delete_agent()` - Delete specific agent
- `create_draft_project()` - Create draft project
- `update_draft_project()` - Update draft project
- `delete_draft_project()` - Delete draft project
- `delete_draft_agent()` - Delete draft agent
- `publish_draft_project()` - Convert draft to production

#### 3. Repositories

**ProjectRepository** (`src/app/repositories/ProjectRepository.py`)
- Extends `AsyncDocumentRepository[Project]`
- Provides Project-specific queries
- Methods: `get_by_status()`, `get_by_business_owner()`, `get_by_technical_owner()`

**AgentRepository** (`src/app/repositories/AgentRepository.py`)
- Extends `AsyncDocumentRepository[Agent]`
- Provides Agent-specific queries
- Methods: `get_by_project()`, `get_by_platform()`, `get_by_status()`, `get_by_observability_tier()`

**DraftProjectRepository** (`src/app/repositories/DraftProjectRepository.py`)
- Extends `AsyncDocumentRepository[DraftProject]`
- Provides DraftProject-specific queries
- Methods: `get_by_business_owner()`, `get_by_technical_owner()`

**DraftAgentRepository** (`src/app/repositories/DraftAgentRepository.py`)
- Extends `AsyncDocumentRepository[DraftAgent]`
- Provides DraftAgent-specific queries
- Methods: `get_by_project()`, `get_by_platform()`

### Data Models

#### Project (Non-Draft)
- **Required Fields:** id, name, purpose, all stakeholder info (business, product, technical, VP)
- **Optional Fields:** status, AI governance fields
- **Collection:** `Projects`

#### DraftProject
- **Required Fields:** id, name
- **Optional Fields:** All other Project fields
- **Collection:** `DraftProjects`

#### Agent
- **Required Fields:** id, project_id, platform, name, purpose, input/output channels
- **Optional Fields:** gitlab_repo_url, endpoint, observability dashboards, status, version info
- **Collection:** `Agents`

#### DraftAgent
- **Required Fields:** id, project_id, platform, name, purpose, input/output channels
- **Optional Fields:** gitlab_repo_url, endpoint, observability dashboards
- **Collection:** `DraftAgents`

### Key Features

#### 1. Draft Mode Support
- Create incomplete projects and agents
- Save progress without full validation
- Update drafts incrementally
- Publish to production when ready

#### 2. Cascading Operations
- Deleting a project automatically deletes all associated agents
- Deleting a draft project automatically deletes all draft agents
- Publishing a draft project moves both project and agents to production

#### 3. ID Consistency
- Draft and production versions maintain the same IDs
- Enables seamless conversion from draft to production
- Simplifies client-side tracking

#### 4. Error Handling
- Comprehensive validation at router level
- Detailed error messages with field-level information
- Proper HTTP status codes (400, 404, 500)
- Structured error responses using `CommonErrorResponse`

#### 5. Logging
- All operations logged at appropriate levels
- Includes operation details for debugging
- Exception logging with full context

### Usage Examples

#### Create a Project with Agents
```python
POST /v1/projects
{
  "project": {
    "id": "uuid",
    "name": "My Project",
    "purpose": "AI integration",
    "business_owner": "John Doe",
    "business_owner_email": "john@example.com",
    ...
  },
  "agents": [
    {
      "id": "uuid",
      "project_id": "uuid",
      "platform": "GCP",
      "name": "Agent 1",
      "purpose": "Data processing",
      ...
    }
  ]
}
```

#### Create a Draft Project
```python
POST /v1/projects/draft
{
  "project": {
    "id": "uuid",
    "name": "Draft Project"
  },
  "agents": []
}
```

#### Publish Draft to Production
```python
POST /v1/projects/draft/{draft_project_id}/publish
{
  "id": "same-uuid",
  "name": "My Project",
  "purpose": "AI integration",
  ...all required fields...
}
```

### Integration with Main App

The router is registered in `src/main.py`:
```python
from app.routers.project_intake_router import PROJECT_INTAKE_ROUTER

app.include_router(router=PROJECT_INTAKE_ROUTER, prefix="/projects")
```

All endpoints are available under `/v1/projects/` (due to `root_path="/v1"` in FastAPI config).

### Testing Considerations

When writing tests:
1. Mock the Firestore client
2. Test each repository method independently
3. Test service orchestration logic
4. Test router error handling and validation
5. Test cascading delete operations
6. Test draft-to-production conversion

### Future Enhancements

1. **Pagination:** Add cursor-based pagination for listing projects/agents
2. **Filtering:** Add query parameters for filtering by status, owner, etc.
3. **Partial Updates:** Use `partial_model()` utility for PATCH endpoints
4. **Batch Operations:** Support bulk create/update/delete
5. **Audit Trail:** Track changes to projects and agents
6. **Approval Workflow:** Implement approval process for publishing drafts
