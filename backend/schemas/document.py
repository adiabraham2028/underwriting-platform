import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class DocumentOut(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    document_type: str
    file_name: str
    file_format: str
    extraction_status: str
    extraction_error: Optional[str] = None
    uploaded_at: datetime
    uploaded_by: uuid.UUID
    is_latest: bool

    model_config = {"from_attributes": True}


class DocumentStatusOut(BaseModel):
    id: uuid.UUID
    status: str
    error: Optional[str] = None
