from typing import Optional
from pydantic import Field
from pydantic import ConfigDict
from app.models.base.CustomBaseModel import CustomBaseModel
from app.models.agent.ChannelInfo import ChannelInfo

class PrimaryInputChannels(CustomBaseModel):

    databases: Optional[ChannelInfo] = Field(
        None, description="database"
    )
    apis: Optional[ChannelInfo] = None
    files_and_documents: Optional[ChannelInfo] = None
    mcp_server: Optional[ChannelInfo] = None
    events_and_messaging: Optional[ChannelInfo] = Field(
        None, description="database"
    )
    other: Optional[ChannelInfo] = None
