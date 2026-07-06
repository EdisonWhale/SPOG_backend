from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Literal

class CursorData(BaseModel):
    """Pydantic model for cursor-based pagination data."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "page": 0,
                "start_doc_id": "doc_123",
                "end_doc_id": "doc_456",
                "direction": "next"
            }
        }
    )

    page: int = Field(..., ge=0, description="Current page number, starts from 0")
    start_doc_id: Optional[str] = Field(None, description="Document ID at the start of the page")
    end_doc_id: Optional[str] = Field(None, description="Document ID at the end of the page")
    direction: Literal["next", "prev"] = Field(..., description="Pagination direction: 'next' or 'prev'")
