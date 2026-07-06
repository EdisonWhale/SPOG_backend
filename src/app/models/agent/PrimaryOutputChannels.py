# PrimaryOutputChannels.py
from typing import Optional
from app.models.base.CustomBaseModel import CustomBaseModel

class PrimaryOutputChannels(CustomBaseModel):
    conversational_interface: Optional[str] = None
    email_notifications: Optional[str] = None
    team_messaging: Optional[str] = None
    dashboard_application_ui: Optional[str] = None
    file_generation: Optional[str] = None
    downstream_api_trigger: Optional[str] = None
    event_message_publish: Optional[str] = None
    other: Optional[str] = None
