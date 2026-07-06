from typing import Set, Optional
from datetime import datetime, timezone
from typing_extensions import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from pydantic.alias_generators import to_camel

class CustomBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True
    )

    def to_dict(self, date_format_iso=True, include_document_id=False, to_camel=False, to_exclude={}):
        mode = 'json' if date_format_iso else 'python'
        exclude = { **to_exclude }
        if not include_document_id:
            exclude['id'] = True

        return self.model_dump(mode=mode, exclude=exclude, by_alias=to_camel, exclude_none=True)
    
    def to_response_dict(self):
        return self.to_dict(
            date_format_iso=True,
            include_document_id=True,
            to_camel=True
        )

class TimestampedModel(BaseModel):
    created_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="createdUtc")
    updated_utc: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="updatedUtc")
    
class TaggableModel(BaseModel):
    tags: Set[str] = Field(default_factory=set)

class UpdateTaggableModel(BaseModel):
    added_tags: Optional[Set[str]] = None
    removed_tags: Optional[Set[str]] = None

class AuthorizableModel(BaseModel):
    author: Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True)]

    @field_validator("author")
    @classmethod
    def validate_author_email(cls, v: str) -> str:
        """Validate that the author is a valid email address."""
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("author must be a valid email address")
        return v

    def to_dict(self, date_format_iso=True, include_document_id=False, to_camel=False, to_exclude={}):
        mode = 'json' if date_format_iso else 'python'
        exclude = { **to_exclude }
        if not include_document_id:
            exclude['id'] = True

        return self.model_dump(mode=mode, exclude=exclude, by_alias=to_camel)

class DeprecatableModel(BaseModel):
    deprecated: bool = Field(default=False)


class FileModel(BaseModel):
    name: Annotated[
        str,
        StringConstraints(
            strict=True, strip_whitespace=True, min_length=1, max_length=255
        ),
    ]

    file_size_bytes: Annotated[int, Field(strict=True, ge=0, default=0)]
    mime_type: str
