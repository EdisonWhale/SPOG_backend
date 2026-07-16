import requests
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional
from app.config.config import load_gitlab_config
from google.cloud.firestore import AsyncClient
from app.models.agent.Agent import Agent
from app.models.job.GitLabSyncJob import GitLabSyncJob, JobMetric
from app.repositories.AgentRepository import AgentRepository
from app.repositories.UseCaseRepository import UseCaseRepository
from app.repositories.ProjectRepository import ProjectRepository
from app.repositories.JobRepository import JobRepository
from app.utils.helpers.common_helpers import chunk_list
from app.models.schemas.GitlabSchemas import GitLabSyncResponse, GitLabSyncSchedulerResponse
from app.utils.helpers.common_helpers import assert_owner
from app.enum import (
    EnvironmentEnum,
    GitlabSyncRequestedStatusEnum,
    UseCaseStatusEnum,
    JobStatusEnum
)


logger = logging.getLogger(__name__)

class GitLabService:

    PROXY_HOST = "inetgate.highmark.com"
    PROXY_PORT = "9121"
    proxy_url: str = f"http://{PROXY_HOST}:{PROXY_PORT}"
    proxies: dict[str, str] = {"http": proxy_url, "https": proxy_url}
    ssl_verification: bool = True

    def __init__(self, db: AsyncClient):
        config = load_gitlab_config()

        if not config.gitlab_token:
            raise ValueError("GitLab token is not configured.")

        self.gitlab_url = config.url
        self.headers = {
            "PRIVATE-TOKEN": config.gitlab_token,
            "Accept": "application/json"
        }
        self.db = db
        self.project_repo = ProjectRepository(db)
        self.agent_repo = AgentRepository(db)
        self.use_case_repo = UseCaseRepository(db)
        self.job_repo = JobRepository(db)
 

    # ── Private Helpers ───────────────────────────────────────────────────────
    def _get(self, url: str, params: Optional[dict] = None) -> dict | list:
        """Base GET request with JSON validation."""
        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            proxies=GitLabService.proxies,
            verify=GitLabService.ssl_verification
        )
        response.raise_for_status()
        if not response.headers.get("Content-Type", "").startswith("application/json"):
            raise RuntimeError(f"{response.status_code}: {response.text[:2000]}")
        return response.json()

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse GitLab ISO 8601 datetime string to datetime object."""
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _get_latest_release(self, gitlab_project_id: str) -> Optional[dict]:
        """Fetch latest release for a project."""
        releases = self._get(
            f"{self.gitlab_url}/api/v4/projects/{gitlab_project_id}/releases",
            params={"per_page": 1, "order_by": "released_at", "sort": "desc"}
        )
        return releases[0] if releases else None

    def _get_latest_tag(self, gitlab_project_id: str) -> Optional[dict]:
        """Fallback: fetch latest tag if no release found."""
        tags = self._get(
            f"{self.gitlab_url}/api/v4/projects/{gitlab_project_id}/repository/tags",
            params={"per_page": 1}
        )
        return tags[0] if tags else None

    # ── Public Methods ────────────────────────────────────────────────────────
    def verify_token(self) -> dict:
        """Verify GitLab PAT and return user info."""
        return self._get(f"{self.gitlab_url}/api/v4/user")

    def resolve_project_id(self, repo_url: str) -> tuple[str, dict]:
        """Resolve numeric project ID from GitLab repo URL."""
        import re
        repo_url = repo_url.rstrip("/")
        repo_url = re.sub(r"\.git$", "", repo_url)
        match = re.search(r"https?://[^/]+/(.+)", repo_url)
        if not match:
            raise ValueError(f"Invalid GitLab URL: {repo_url}")

        namespace_path = match.group(1)
        encoded_path = requests.utils.quote(namespace_path, safe="")
        project = self._get(f"{self.gitlab_url}/api/v4/projects/{encoded_path}")
        return str(project["id"]), project

    def get_commits(
        self,
        gitlab_project_id: str,
        branch: str = "main",
        page: int = 1,
        per_page: int = 20
    ) -> tuple[list, int]:
        """Fetch paginated commits and total pages."""
        response = requests.get(
            f"{self.gitlab_url}/api/v4/projects/{gitlab_project_id}/repository/commits",
            headers=self.headers,
            params={"ref_name": branch, "per_page": per_page, "page": page},
        )
        response.raise_for_status()
        total_pages = int(response.headers.get("X-Total-Pages", 1))
        return response.json(), total_pages

    def get_branch_tags(self, gitlab_project_id: str, commit_shas: set) -> list:
        """Get tag names pointing to given commit SHAs."""
        tags = self._get(
            f"{self.gitlab_url}/api/v4/projects/{gitlab_project_id}/repository/tags"
        )
        return [t["name"] for t in tags if t["target"] in commit_shas]

    def get_code_version_and_release_date(self, gitlab_project_id: str) -> dict:
        """
        Fetch latest code version and release date on main branch.
        Falls back to latest tag if no release found.
        """
        try:
            release = self._get_latest_release(gitlab_project_id)
            if release:
                return {
                    "code_version": release["tag_name"],
                    "release_date": self._parse_datetime(release.get("released_at"))
                }

            tag = self._get_latest_tag(gitlab_project_id)
            if tag:
                return {
                    "code_version": tag["name"],
                    "release_date": self._parse_datetime(
                        tag.get("commit", {}).get("created_at")
                    )
                }

            return {"code_version": None, "release_date": None}

        except Exception as e:
            raise RuntimeError(
                f"GitLab fetch failed for project {gitlab_project_id}: {e}"
            )

    async def trigger_gitlab_sync(
        self, project_id: str, author: Optional[str] = None
    ) -> GitLabSyncResponse:
        """
        Trigger and execute GitLab sync for a specific project.

        Conditions required:
        - Author must be the project owner
        - active=False AND locked=True
        - All agents must be in Staging environment
        - gitlab_sync_requested_status is None or COMPLETED (allows re-trigger)

        Raises:
            ValueError: If project conditions not met
            NotAuthorizedError: If author does not own the project
        """
        use_case = await self.use_case_repo.get_approved_first_use_case(project_id)
        if not use_case:
            raise ValueError(
                "No first approved use case found for this project. "
                "May be use case is not created or still in pending state"
            )

        project = await self.project_repo.get(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found.")

        # ── Only the creator may trigger the sync ────────────────────────────
        assert_owner(project.author, author, "project", project_id)

        # ── Condition: inactive and locked ───────────────────────────────────
        if project.active is True:
            raise ValueError("GitLab sync requires project to be inactive (active=False).")
        if project.locked is False:
            raise ValueError("GitLab sync requires project to be locked (locked=True).")

        # ── Condition: all agents must be in Staging ──────────────────────────
        all_agents = await self.agent_repo.get_by_project(project_id)
        if not all_agents:
            raise ValueError("GitLab sync requires at least one agent in the project.")

        non_staging = [
            str(a.id)
            for a in all_agents
            if getattr(a, "environment", None) not in (
                EnvironmentEnum.STAGING.value,
                EnvironmentEnum.PRODUCTION.value,
            )
        ]
        if non_staging:
            raise ValueError(
                f"GitLab sync requires all agents to be in Staging environment. "
                f"Non-staging agent(s): {', '.join(non_staging)}"
            )

        # ── Condition: no sync already in progress ────────────────────────────
        sync_status = project.gitlab_sync_requested_status
        blocked_statuses = {
            GitlabSyncRequestedStatusEnum.PENDING,
            GitlabSyncRequestedStatusEnum.RUNNING,
        }
        if sync_status in blocked_statuses:
            raise ValueError(
                f"GitLab sync is already in progress (status={sync_status.value}). "
                "Please wait until the current sync completes before re-triggering."
            )

        # ── Set status → RUNNING and execute sync ────────────────────────────
        project.gitlab_sync_requested_at = datetime.now(timezone.utc)
        project.gitlab_sync_requested_status = GitlabSyncRequestedStatusEnum.RUNNING
        await self.project_repo.update(project)
        logger.info(f"🔄 GitLab sync RUNNING for project {project_id} by '{author}'")

        try:
            staging_agents = [
                a for a in all_agents
                if getattr(a, "environment", None) == EnvironmentEnum.STAGING.value
            ]
            if not staging_agents:
                logger.warning(f"⚠️ No staging agents found for project {project_id}.")
                project.gitlab_sync_requested_status = GitlabSyncRequestedStatusEnum.COMPLETED
                await self.project_repo.update(project)
                return GitLabSyncResponse(
                    status=GitlabSyncRequestedStatusEnum.COMPLETED,
                    project_id=project_id,
                    gitlab_sync_requested_at=project.gitlab_sync_requested_at,
                )

            # ── Process each agent ────────────────────────────────────────────
            promoted, skipped, failed = [], [], []

            for agent in staging_agents:
                gitlab_project_id = getattr(agent, "gitlab_project_id", None)

                if not gitlab_project_id:
                    logger.warning(f"⚠️ Agent {agent.id} has no gitlab_project_id, skipping.")
                    skipped.append(str(agent.id))
                    continue

                try:
                    result = self.get_code_version_and_release_date(str(gitlab_project_id))
                    code_version = result.get("code_version")
                    release_date = result.get("release_date")

                    if not code_version:
                        logger.info(f"⚠️ Agent {agent.id} has no release yet, skipping.")
                        skipped.append(str(agent.id))
                        continue

                    agent.production_latest_code_version = code_version
                    agent.production_latest_release_date = release_date
                    agent.environment = EnvironmentEnum.PRODUCTION

                    await self.agent_repo.update(agent, project_id=project_id)
                    promoted.append(str(agent.id))
                    logger.info(f"✅ Agent {agent.id} promoted → {code_version} | {release_date}")

                except Exception as e:
                    logger.error(f"❌ Failed for agent {agent.id}: {e}")
                    failed.append(str(agent.id))

            # ── Update project → COMPLETED ────────────────────────────────────
            project.gitlab_sync_requested_status = GitlabSyncRequestedStatusEnum.COMPLETED
            if promoted and not failed and not skipped:
                project.active = True
                logger.info(f"🏁 Project {project_id} marked active=True")

            await self.project_repo.update(project)
            logger.info(
                f"✅ GitLab sync COMPLETED for project {project_id} by '{author}' | "
                f"promoted={len(promoted)} skipped={len(skipped)} failed={len(failed)}"
            )

            return GitLabSyncResponse(
                status=GitlabSyncRequestedStatusEnum.COMPLETED,
                project_id=project_id,
                promoted=project.active,
                gitlab_sync_requested_at=project.gitlab_sync_requested_at,
            )

        except Exception as e:
            logger.exception(f"❌ GitLab sync failed for project {project_id}: {e}")
            try:
                project.gitlab_sync_requested_status = GitlabSyncRequestedStatusEnum.FAILED
                await self.project_repo.update(project)
            except Exception:
                pass
            raise
    
    async def resolve_and_patch_gitlab_project_id(
        self, agent_id: str, project_id: str, repo_url: str
    ) -> None:
        """Background task: resolve gitlab_project_id from URL and patch the agent."""
        try:
            loop = asyncio.get_event_loop()
            resolved_id, _ = await loop.run_in_executor(
                None, lambda: self.resolve_project_id(repo_url)
            )
            agent_repo = self.agent_repo
            agent = await agent_repo.get(agent_id, project_id=project_id)
            if agent:
                agent.gitlab_project_id = int(resolved_id)
                await agent_repo.update(agent, project_id=project_id)
                logger.info(
                    f"✅ Background resolved gitlab_project_id={resolved_id} "
                    f"for agent {agent_id}"
                )
        except Exception as e:
            logger.warning(
                f"⚠️ Background GitLab ID resolution failed for agent {agent_id} "
                f"url='{repo_url}': {e}"
            )


    async def gitlab_auto_sync(self):
        # Step 1: Approved use cases → project IDs
        gitlab_job = GitLabSyncJob(
            status=JobStatusEnum.PENDING
        )
        job_created = await self.job_repo.create(gitlab_job)
        project_ids = await self.get_approved_project_ids()
        if not project_ids:
            await self.job_repo.update(job_created.model_copy(update={"status": JobStatusEnum.COMPLETED}))
            return
    
        # Step 2: Eligible projects (status=False) → staging agents map
        project_agents_map = await self.get_staging_agents(project_ids)
        if not project_agents_map:
            await self.job_repo.update(job_created.model_copy(update={"status": JobStatusEnum.COMPLETED}))
            return

        response = await self.process_agents(project_agents_map, job=job_created)
        return response


    async def get_approved_project_ids(self) -> list[str]:
        """Fetch unique project IDs from approved use cases."""

        use_cases = await self.use_case_repo.get_by_status(UseCaseStatusEnum.APPROVED)
        project_ids = list({uc.project_id for uc in use_cases if uc.project_id})

        logger.info(f"Found {len(project_ids)} unique projects from approved use cases")
        return project_ids

    async def get_staging_agents(self, project_ids: list[str]) -> dict[str, list[Agent]]:
        """
        Fetch agents with environment=Staging under projects
        where status=False (not yet promoted to production).
        Returns a dict of project_id → list of agents.
        """

        # project_id → agents mapping (to track per-project completion)
        project_agents_map: dict[str, list[Agent]] = {}

        # Filter projects where status=False (pending promotion)
        eligible_project_ids = []
        chunk_size = 10
        for chunk in chunk_list(project_ids, chunk_size):
            for project_id in chunk:
                try:
                    project = await self.project_repo.get(project_id)
                    if project and project.active is False:
                        eligible_project_ids.append(project_id)
                except Exception as e:
                    logger.error(f"Error fetching project {project_id}: {e}")

        if not eligible_project_ids:
            logger.info("No eligible projects found (all already promoted).")
            return {}

        logger.info(f"Found {len(eligible_project_ids)} eligible projects (active=False)")

        # Fetch staging agents under eligible projects
        for chunk in chunk_list(eligible_project_ids, chunk_size):
            try:
                group_query = (
                    self.db.collection_group(AgentRepository.AGENTS_SUBCOLLECTION)
                    .where("environment", "==", EnvironmentEnum.STAGING)
                    .where("project_id", "in", chunk)
                )
                agents = await self.agent_repo._results_from_group_query(group_query)
                for agent in agents:
                    project_agents_map.setdefault(agent.project_id, []).append(agent)
            except Exception as e:
                logger.error(f"Error fetching agents for chunk {chunk}: {e}")

        total = sum(len(v) for v in project_agents_map.values())
        logger.info(f"Found {total} staging agents across {len(project_agents_map)} projects")
        return project_agents_map

    async def process_agents(self, project_agents_map: dict[str, list[Agent]], job:GitLabSyncJob) -> None:
        """
        For each project:
        1. Process all staging agents → fetch GitLab info → mark as Production
        2. If ALL agents in project are promoted → set project.status = True
        """

        total_agents =  sum(len(v) for v in project_agents_map.values())
        job.status = JobStatusEnum.PROCESSING
        job.metric = JobMetric(
            total_projects=len(project_agents_map),
            total_agents = total_agents
        )
        job.updated_utc = datetime.now(timezone.utc)
        await self.job_repo.update(job)
        
        for project_id, agents in project_agents_map.items():
            all_promoted = True

            for agent in agents:
                gitlab_project_id = getattr(agent, "gitlab_project_id", None)

                if not gitlab_project_id:
                    logger.warning(f"⚠️ Agent {agent.id} has no gitlab_project_id, skipping.")
                    job.metric.failed_agents += 1
                    job.failed_agents_id.append(agent.id)
                    all_promoted = False
                    continue

                try:
                    result = self.get_code_version_and_release_date(
                        str(gitlab_project_id)
                    )
                    code_version = result.get("code_version")
                    release_date = result.get("release_date")

                    if not code_version:
                        logger.info(f"⚠️ Agent {agent.id} has no release yet, skipping.")
                        job.metric.failed_agents += 1
                        job.failed_agents_id.append(agent.id)
                        all_promoted = False
                        continue

                    # Update agent → Production
                    agent.production_latest_code_version = code_version
                    agent.production_latest_release_date = release_date
                    agent.environment = EnvironmentEnum.PRODUCTION

                    await self.agent_repo.update(
                        agent,
                        project_id=project_id
                    )

                    logger.info(
                        f"✅ Agent {agent.id} (project={project_id}) "
                        f"updated → {code_version} | {release_date}"
                    )

                except Exception as e:
                    logger.error(f"❌ Failed for agent {agent.id}: {e}")
                    job.metric.failed_agents += 1
                    job.failed_agents_id.append(agent.id)
                    all_promoted = False

            # Mark project status=True only if ALL agents promoted successfully
            if all_promoted:
                try:
                    project = await self.project_repo.get(project_id)
                    if project:
                        project.active = True
                        await self.project_repo.update(project)
                        logger.info(f"🏁 Project {project_id} marked as active=True")
                except Exception as e:
                    logger.error(f"❌ Failed to update project {project_id} status: {e}")
            else:
                logger.warning(
                    f"⚠️ Project {project_id} NOT fully promoted — active remains False"
                )

        try:
            job.status = JobStatusEnum.COMPLETED
            job.updated_utc = datetime.now(timezone.utc)
            await self.job_repo.update(job)
            logger.info(
                f"🏁 Job {job.id} → {job.status} | "
                f"promoted={job.metric.promoted_agents} | "
                f"failed={job.metric.failed_agents}"
            )
        except Exception as e:
            logger.error(f"❌ Failed to finalize job {job.id} status: {e}")
