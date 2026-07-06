"""
GitLab Sync Router

Scheduled endpoint triggered by GitLab Pipeline Scheduler to sync
staging agents to production by fetching code version and release
date from GitLab.
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from app.core.firestore_client import FirestoreClient
from app.models.agent.Agent import Agent
from app.repositories.AgentRepository import AgentRepository
from app.repositories.UseCaseRepository import UseCaseRepository
from app.repositories.ProjectRepository import ProjectRepository

from app.services.GitlabService import gitlab_service
import os

logger = logging.getLogger(__name__)

GITLAB_SYNC_ROUTER = APIRouter(tags=["gitlab"])

SCHEDULER_SECRET = os.getenv("SCHEDULER_SECRET", "your-secret-token")
CHUNK_SIZE = 10


# ── Auth Guard ────────────────────────────────────────────────────────────────
def verify_scheduler(authorization: Optional[str]) -> None:
    if authorization != f"Bearer {SCHEDULER_SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")


# ── Helpers ───────────────────────────────────────────────────────────────────
def chunk_list(lst: list, size: int):
    """Yield list in chunks of given size."""
    for i in range(0, len(lst), size):
        yield lst[i:i + size]


async def get_approved_project_ids() -> list[str]:
    """Fetch unique project IDs from approved use cases."""
    db = FirestoreClient.InstanceClient()
    use_case_repo = UseCaseRepository(db)

    use_cases = await use_case_repo.get_by_status("approved")
    project_ids = list({uc.project_id for uc in use_cases if uc.project_id})

    logger.info(f"Found {len(project_ids)} unique projects from approved use cases")
    return project_ids


async def get_staging_agents(project_ids: list[str]) -> dict[str, list[Agent]]:
    """
    Fetch agents with environment=Staging under projects
    where status=False (not yet promoted to production).
    Returns a dict of project_id → list of agents.
    """
    db = FirestoreClient.InstanceClient()
    agent_repo = AgentRepository(db)
    project_repo = ProjectRepository(db)

    # project_id → agents mapping (to track per-project completion)
    project_agents_map: dict[str, list[Agent]] = {}

    # Filter projects where status=False (pending promotion)
    eligible_project_ids = []
    for chunk in chunk_list(project_ids, CHUNK_SIZE):
        for project_id in chunk:
            try:
                project = await project_repo.get(project_id)
                if project and project.status is False:
                    eligible_project_ids.append(project_id)
            except Exception as e:
                logger.error(f"Error fetching project {project_id}: {e}")

    if not eligible_project_ids:
        logger.info("No eligible projects found (all already promoted).")
        return {}

    logger.info(f"Found {len(eligible_project_ids)} eligible projects (status=False)")

    # Fetch staging agents under eligible projects
    for chunk in chunk_list(eligible_project_ids, CHUNK_SIZE):
        try:
            group_query = (
                db.collection_group(AgentRepository.AGENTS_SUBCOLLECTION)
                .where("environment", "==", "Staging")
                .where("project_id", "in", chunk)
            )
            agents = await agent_repo._results_from_group_query(group_query)
            for agent in agents:
                project_agents_map.setdefault(agent.project_id, []).append(agent)
        except Exception as e:
            logger.error(f"Error fetching agents for chunk {chunk}: {e}")

    total = sum(len(v) for v in project_agents_map.values())
    logger.info(f"Found {total} staging agents across {len(project_agents_map)} projects")
    return project_agents_map



async def process_agents(project_agents_map: dict[str, list[Agent]]) -> None:
    """
    For each project:
    1. Process all staging agents → fetch GitLab info → mark as Production
    2. If ALL agents in project are promoted → set project.status = True
    """
    db = FirestoreClient.InstanceClient()
    agent_repo = AgentRepository(db)
    project_repo = ProjectRepository(db)

    for project_id, agents in project_agents_map.items():
        all_promoted = True

        for agent in agents:
            gitlab_project_id = getattr(agent, "gitlab_project_id", None)

            if not gitlab_project_id:
                logger.warning(f"⚠️ Agent {agent.id} has no gitlab_project_id, skipping.")
                all_promoted = False
                continue

            try:
                result = gitlab_service.get_code_version_and_release_date(
                    str(gitlab_project_id)
                )
                code_version = result.get("code_version")
                release_date = result.get("release_date")

                if not code_version:
                    logger.info(f"⚠️ Agent {agent.id} has no release yet, skipping.")
                    all_promoted = False
                    continue

                # Update agent → Production
                agent.code_version = code_version
                agent.release_date = release_date
                agent.environment = "Production"

                await agent_repo.update(
                    agent,
                    project_id=project_id,
                    excludes={"project_id": True}
                )

                logger.info(
                    f"✅ Agent {agent.id} (project={project_id}) "
                    f"updated → {code_version} | {release_date}"
                )

            except Exception as e:
                logger.error(f"❌ Failed for agent {agent.id}: {e}")
                all_promoted = False

        # Mark project status=True only if ALL agents promoted successfully
        if all_promoted:
            try:
                project = await project_repo.get(project_id)
                if project:
                    project.status = True
                    await project_repo.update(project)
                    logger.info(f"🏁 Project {project_id} marked as status=True")
            except Exception as e:
                logger.error(f"❌ Failed to update project {project_id} status: {e}")
        else:
            logger.warning(
                f"⚠️ Project {project_id} NOT fully promoted — status remains False"
            )


# ── Router ────────────────────────────────────────────────────────────────────
@GITLAB_SYNC_ROUTER.post("/sync-staging-to-production")
async def sync_staging_to_production(
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
    x_cloudscheduler_jobname: Optional[str] = Header(None),
):
    verify_scheduler(authorization)
    logger.info(f"🚀 Triggered by: {x_cloudscheduler_jobname or 'manual'}")

    # Step 1: Approved use cases → project IDs
    project_ids = await get_approved_project_ids()
    if not project_ids:
        return {"status": "no_approved_projects", "count": 0}

    # Step 2: Eligible projects (status=False) → staging agents map
    project_agents_map = await get_staging_agents(project_ids)
    if not project_agents_map:
        return {"status": "no_staging_agents", "count": 0}

    total_agents = sum(len(v) for v in project_agents_map.values())

    # Step 3: Process in background
    background_tasks.add_task(process_agents, project_agents_map)

    return {
        "status": "processing",
        "projects_queued": len(project_agents_map),
        "agents_queued": total_agents,
    }

