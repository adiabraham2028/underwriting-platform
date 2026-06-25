import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ClassificationSessionItemOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    line_item_name: str
    account_code: Optional[str] = None
    monthly_values: dict
    trailing_total: float
    ai_suggested_category: str
    ai_confidence: float
    final_category: str
    match_type: str
    was_corrected: bool
    display_order: int

    model_config = {"from_attributes": True}


class ClassificationSessionOut(BaseModel):
    id: uuid.UUID
    deal_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    tenant_id: uuid.UUID
    status: str
    total_line_items: int
    auto_accepted: int
    needs_review: int
    human_corrected: int
    created_at: datetime
    approved_at: Optional[datetime] = None
    approved_by: Optional[uuid.UUID] = None
    items: list[ClassificationSessionItemOut] = []

    model_config = {"from_attributes": True}


class UpdateItemCategoryRequest(BaseModel):
    final_category: str
    override_reason: Optional[str] = None


class LineItemClassificationOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    original_line_item: str
    normalized_line_item: str
    source_format: str
    account_code: Optional[str] = None
    assigned_category: str
    confidence: float
    classification_source: str
    confirmed_by: Optional[uuid.UUID] = None
    confirmed_at: Optional[datetime] = None
    deal_id: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeBaseStatsOut(BaseModel):
    total: int
    auto_classifiable_pct: float
    corrected_last_30d: int
