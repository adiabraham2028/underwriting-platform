import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Float, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class ExpenseComp(Base):
    __tablename__ = "expense_comps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    property_name: Mapped[str] = mapped_column(String, nullable=False)
    yardi_mri_code: Mapped[str | None] = mapped_column(String, nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_sf: Mapped[float | None] = mapped_column(Float, nullable=True)
    city: Mapped[str | None] = mapped_column(String, nullable=True)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    financial_stmt_year: Mapped[str] = mapped_column(String, nullable=False)
    financial_stmt_type: Mapped[str] = mapped_column(String, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics_per_unit_yr: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    metrics_per_unit_mo: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(
        SAEnum("import", "deal", name="comp_source"), nullable=False, default="import"
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
