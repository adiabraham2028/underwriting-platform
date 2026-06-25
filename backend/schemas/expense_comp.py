import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class ExpenseCompOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    property_name: str
    yardi_mri_code: Optional[str] = None
    year_built: Optional[int] = None
    num_units: Optional[int] = None
    avg_sf: Optional[float] = None
    city: Optional[str] = None
    state: Optional[str] = None
    financial_stmt_year: str
    financial_stmt_type: str
    metrics: dict
    metrics_per_unit_yr: dict
    metrics_per_unit_mo: dict
    source: str
    deal_id: Optional[uuid.UUID] = None
    created_at: datetime
    uploaded_by: uuid.UUID

    model_config = {"from_attributes": True}


class IncExpVarOut(BaseModel):
    subject: Optional[ExpenseCompOut] = None
    comps: list[ExpenseCompOut] = []


class ComparisonPeriod(BaseModel):
    label: str
    stmt_type: str
    metrics: dict


class SubjectComparison(BaseModel):
    name: str
    num_units: Optional[int] = None
    year_built: Optional[int] = None
    avg_sf: Optional[float] = None
    periods: list[ComparisonPeriod] = []


class CompComparison(BaseModel):
    id: uuid.UUID
    name: str
    num_units: Optional[int] = None
    year_built: Optional[int] = None
    avg_sf: Optional[float] = None
    financial_stmt_year: str
    financial_stmt_type: str
    metrics: dict


class ComparisonOut(BaseModel):
    subject: SubjectComparison
    comps: list[CompComparison] = []
