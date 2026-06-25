import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, Integer, Float, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class LineItemClassification(Base):
    __tablename__ = "line_item_classifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    original_line_item: Mapped[str] = mapped_column(String, nullable=False)
    normalized_line_item: Mapped[str] = mapped_column(String, nullable=False)
    source_format: Mapped[str] = mapped_column(
        SAEnum("conam_gl", "conam_ext", "broker", "mri", "unknown", name="source_format"), nullable=False
    )
    account_code: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_category: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    classification_source: Mapped[str] = mapped_column(
        SAEnum("seed", "ai", "human", name="classification_source_type"), nullable=False, default="seed"
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deal_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )


class ClassificationSession(Base):
    __tablename__ = "classification_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("pending_review", "approved", "applied", name="session_status"), nullable=False, default="pending_review"
    )
    total_line_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auto_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    human_corrected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)


class ClassificationSessionItem(Base):
    __tablename__ = "classification_session_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("classification_sessions.id"), nullable=False)
    line_item_name: Mapped[str] = mapped_column(String, nullable=False)
    account_code: Mapped[str | None] = mapped_column(String, nullable=True)
    monthly_values: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trailing_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ai_suggested_category: Mapped[str] = mapped_column(String, nullable=False)
    ai_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_category: Mapped[str] = mapped_column(String, nullable=False)
    match_type: Mapped[str] = mapped_column(
        SAEnum("exact_known", "ai_high", "ai_low", "human_override", name="match_type_enum"), nullable=False, default="ai_low"
    )
    was_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
