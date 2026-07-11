from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.infrastructure.database.models import DocumentStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    original_filename: str
    stored_filename: str
    mime_type: str
    size_bytes: int
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
