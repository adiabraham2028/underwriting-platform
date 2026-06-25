import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Any, Dict


class ExtractionOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    deal_id: uuid.UUID
    document_type: str
    extracted_data: Dict[str, Any]
    confidence_scores: Dict[str, Any]
    claude_model_used: str
    created_at: datetime

    model_config = {"from_attributes": True}
