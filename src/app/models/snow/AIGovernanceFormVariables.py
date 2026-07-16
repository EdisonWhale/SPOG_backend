import json
import urllib.parse
from typing import List
from pydantic import BaseModel, Field

class AIGovernanceFormVariables(BaseModel):
    model_config = {"populate_by_name": True}

    ai_use_intake_form_reference_number: str = Field("<intake_form_number>", alias="ai_use_intake_form_reference_number")
    request_title: str = Field(alias="request_title")
    type_of_ai_request_review: str = Field("internally_developed_generative_ai", alias="type_of_ai_request_review")
    deployment_platform: str = Field("GCP", alias="deployment_platform")
    what_data_does_the_system_have_access_to: str = Field(alias="what_data_does_the_system_have_access_to")
    spog_project_id_leave_blank_if_this_box_is_empty: str | None = Field(None, alias="spog_project_id_leave_blank_if_this_box_is_empty")
    is_there_an_ai_agent_in_scope: str = Field("Yes", alias="is_there_an_ai_agent_in_scope")

    def generate_ai_governance_url(self) -> str:
        form_id = "sc_cat_item"
        sys_id = "71a0092633afa210f735bfb32d5c7b9d"
        table = "sc_cat_item"

        json_params = json.dumps(self.model_dump(by_alias=True))
        encoded_params = urllib.parse.quote(json_params)

        return f"https://highmark.service-now.com/esc?id={form_id}&sys_id={sys_id}&table={table}&sysparm_variable_values={encoded_params}"
