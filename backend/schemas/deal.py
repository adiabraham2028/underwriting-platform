import uuid
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class DealCreate(BaseModel):
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    total_units: Optional[int] = None
    template_id: uuid.UUID


class DealUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    total_units: Optional[int] = None
    status: Optional[str] = None
    active_template_id: Optional[uuid.UUID] = None
    template_outdated: Optional[bool] = None


class DealOut(BaseModel):
    id: uuid.UUID
    name: str
    address: str
    city: str
    state: str
    zip_code: str
    lat: Optional[float] = None
    lng: Optional[float] = None
    total_units: Optional[int] = None
    status: str
    active_template_id: Optional[uuid.UUID] = None
    template_outdated: bool
    created_at: datetime
    created_by: uuid.UUID
    last_updated: datetime
    flag_count: Optional[int] = None

    model_config = {"from_attributes": True}
