from typing import ClassVar, Optional
from app.models.base.CustomBaseModel import (
    CustomBaseModel,
    TimestampedModel,
    AuthorizableModel,
    DeprecatableModel,
    TaggableModel
)

class EntityBaseModel(
    AuthorizableModel,
    DeprecatableModel,
    TaggableModel,
    TimestampedModel,
):
    id: Optional[str] = None

class SpogBaseModel(
    CustomBaseModel,
    EntityBaseModel
):
    COLLECTION_NAME: ClassVar[str] = "SpogBaseModels"
