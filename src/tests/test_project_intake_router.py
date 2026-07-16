import asyncio
from uuid import uuid4

from app.routers.project_intake_router import get_project_agents


class ProjectServiceStub:
    def __init__(self, agents: list[dict]) -> None:
        self.agents = agents
        self.project_reads = 0
        self.separate_agent_reads = 0

    async def get_project_with_agents(self, project_id: str) -> dict:
        self.project_reads += 1
        return {"project": {"id": project_id}, "agents": self.agents}

    async def get_agents_by_project(self, project_id: str) -> list[dict]:
        self.separate_agent_reads += 1
        return []


def test_get_project_agents_reuses_agents_loaded_with_project() -> None:
    expected_agents = [{"id": str(uuid4()), "name": "Agent One"}]
    service = ProjectServiceStub(expected_agents)

    result = asyncio.run(
        get_project_agents(uuid4(), service=service, author="test@example.com")
    )

    assert result == expected_agents
    assert service.project_reads == 1
    assert service.separate_agent_reads == 0
