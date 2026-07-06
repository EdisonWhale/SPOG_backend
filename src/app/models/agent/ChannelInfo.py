# ChannelInfo.py
from typing import Optional
from app.models.base.CustomBaseModel import CustomBaseModel
from app.enum import (
    DataLevel
)

class ChannelInfo(CustomBaseModel):
    details: Optional[str] = None
    data_level: Optional[DataLevel] = None
