import requests
from typing import Optional
from app.config.config import load_gitlab_config


class GitLabService:

    def __init__(self):
        config = load_gitlab_config()

        if not config.token:
            raise ValueError("GitLab token is not configured.")

        self.gitlab_url = config.url
        self.headers = {
            "PRIVATE-TOKEN": config.token,
            "Accept": "application/json"
        }

    # ── Private Helpers ───────────────────────────────────────────────────────
    def _get(self, url: str, params: Optional[dict] = None) -> dict | list:
        """Base GET request with JSON validation."""
        response = requests.get(
            url,
            headers=self.headers,
            params=params,
        )
        response.raise_for_status()
        if not response.headers.get("Content-Type", "").startswith("application/json"):
            raise RuntimeError(f"{response.status_code}: {response.text[:2000]}")
        return response.json()

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
                    "release_date": release["released_at"]
                }

            tag = self._get_latest_tag(gitlab_project_id)
            if tag:
                return {
                    "code_version": tag["name"],
                    "release_date": tag.get("commit", {}).get("created_at")
                }

            return {"code_version": None, "release_date": None}

        except Exception as e:
            raise RuntimeError(
                f"GitLab fetch failed for project {gitlab_project_id}: {e}"
            )


# ── Singleton Instance ────────────────────────────────────────────────────────
gitlab_service = GitLabService()
