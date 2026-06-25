import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ClientTemplateOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    version: int
    cell_mapping: dict
    mapping_confirmed: bool
    is_active: bool
    tab_names: list
    created_at: datetime
    created_by: uuid.UUID

    model_config = {"from_attributes": True}


class UpdateCellMappingRequest(BaseModel):
    cell_mapping: dict
    mapping_confirmed: Optional[bool] = None
