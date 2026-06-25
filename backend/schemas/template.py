import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Any, Dict


class TemplateOut(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    is_default: bool
    cell_mapping: Dict[str, Any]
    created_at: datetime
    created_by: uuid.UUID
    is_active: bool

    model_config = {"from_attributes": True}


class TemplateMappingUpdate(BaseModel):
    cell_mapping: Dict[str, Any]
