from app.models.project.DraftProjectCreate import DraftProjectCreate, DraftAgentCreate
from app.models.project.DraftProject import DraftProject
from app.models.agent.DraftAgent import DraftAgent

author = "user@highmark.com"

# Simulate request body
project = DraftProjectCreate.model_validate({"name": "AI Analytics 3"})
agents = [DraftAgentCreate.model_validate({"name": "Data Processor 2"})]

print("project dump:", project.model_dump(exclude_none=True))
for a in agents:
    print("agent dump:", a.model_dump(exclude_none=True))

# Router logic
project_data = project.model_dump(exclude_none=True)
project_data.pop("author", None)
project_data.pop("id", None)
full_project = DraftProject(author=author, **project_data)
print("full_project OK:", full_project.name)

for a in agents:
    agent_data = a.model_dump(exclude_none=True)
    agent_data.pop("author", None)
    agent_data.pop("id", None)
    full_agent = DraftAgent(author=author, **agent_data)
    print("full_agent OK:", full_agent.name)
