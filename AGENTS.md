# AI Assistant Development Context

## Project: `spog/dashboard-backend` — SPOG Dashboard Backend API


### 1. Project Goal

The primary objective of this project is to build and maintain a FastAPI backend service for the SPOG dashboard, deployed on GCP Cloud Run. The service provides REST API endpoints with structured logging, OpenTelemetry tracing (Dynatrace/Zipkin), and Cloud Run environment detection. It serves as the backend for the SPOG (Single Pane of Glass) dashboard and is the integration point for AI-powered features surfaced through that interface.


### 2. Core Artifacts

As an AI assistant, your main sources of truth for this project are:

*   **`README.md`:** [./README.md](README.md) Provides a high-level overview of the service, its purpose, and end-user usage instructions.
*   **`docs/requirements.md`:** This is the **most critical document**. It contains the detailed functional and technical specifications for all API features, including endpoint definitions, data contracts, authentication requirements, and integration standards.
*   **`CONTRIBUTING.md`:** [./CONTRIBUTING.md](CONTRIBUTING.md) Outlines the development methodology, including how to set up the environment, run tests, and follow coding standards.
*   **`PLAN.md`:** [./PLAN.md](PLAN.md) This file contains the high-level implementation plan that you should follow.


### 3. Key Instructions

*   **Follow the Plan:** Adhere to the tasks and phases outlined in [./PLAN.md](PLAN.md). **Note:** If `PLAN.md` does not exist or lacks clear content, you should suggest an initial session to create it before proceeding with other tasks.
*   **Session Management:** Read `/ai/instructions/ai_session_management.md` for session management procedures; sessions are used to implement steps in the Plan.
*   **Test-Driven Development (TDD):** The project methodology is TDD. Write failing tests *before* writing implementation code for any new feature. Tests live in `src/tests/`; run them with `pytest src/tests/ -v` from the repo root (with `PYTHONPATH=src`).
*   **Refer to the Spec:** All implemented features must align with the specifications in `docs/requirements.md`. If this file does not exist already, it should be created as part of the initial steps of implementing the plan.
*   **FastAPI patterns:** Follow the modular structure under `src/`:
    - `src/routes/` — API routers (one file per feature area, use `APIRouter`)
    - `src/common/config.py` — centralised config from environment variables
    - `src/utils/` — shared utilities (logging, OTEL, Cloud Run detection, etc.)
    - `src/tests/` — pytest test suite using `fastapi.testclient.TestClient`


### Session Setup Instructions

After reading `/ai/instructions/ai_session_management.md` for session management procedures:

1. **Create session workspace** using provided session ID and short name
2. **Use proper commit watermarking:** `[ai-claude-sessionID-short-name]`
3. **Wait for user direction** - Do not infer work from session short name
4. **Reference previous sessions** in `/ai/sessions/` folder for architectural context when needed or requested.
5. **Work within session isolation** - Write only to your session folder unless otherwise directed. Do not write to other session folders.
6. **Use America/New_York timezone** - Unless user specifies otherwise, assume US Eastern timezone for all date/time references
7. **Resuming Sessions** - User may request for a session to be "resumed" in a new conversation; if so, read the notes/transcript/plan from the existing session for context.

## Session History

For a complete list of all sessions, see [session_index.md](ai/sessions/session_index.md).
