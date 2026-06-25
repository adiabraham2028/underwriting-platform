import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey, LargeBinary
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(
        SAEnum("rent_roll", "t12", "om", "other", name="document_type"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String, nullable=False)
    file_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    file_format: Mapped[str] = mapped_column(
        SAEnum("pdf_digital", "pdf_scanned", "excel", "docx", name="file_format"), nullable=False
    )
    extraction_status: Mapped[str] = mapped_column(
        SAEnum("pending", "processing", "complete", "failed", name="extraction_status"),
        nullable=False,
        default="pending",
    )
    extraction_error: Mapped[str | None] = mapped_column(String, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
