"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Pre-define all PG enum types with create_type=False so op.create_table
# never tries to issue CREATE TYPE (we handle that below via DO blocks).
user_role = PG_ENUM("admin", "analyst", name="user_role", create_type=False)
deal_status = PG_ENUM("active", "archived", "closed", name="deal_status", create_type=False)
document_type = PG_ENUM("rent_roll", "t12", "om", "other", name="document_type", create_type=False)
file_format = PG_ENUM("pdf_digital", "pdf_scanned", "excel", "docx", name="file_format", create_type=False)
extraction_status = PG_ENUM("pending", "processing", "complete", "failed", name="extraction_status", create_type=False)
flag_type = PG_ENUM("missing", "conflict", "unusual", "low_confidence", name="flag_type", create_type=False)
flag_severity = PG_ENUM("critical", "warning", "info", name="flag_severity", create_type=False)


def upgrade() -> None:
    # Create enum types idempotently — DO blocks swallow duplicate_object errors
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM ('admin', 'analyst');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE deal_status AS ENUM ('active', 'archived', 'closed');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE document_type AS ENUM ('rent_roll', 't12', 'om', 'other');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE file_format AS ENUM ('pdf_digital', 'pdf_scanned', 'excel', 'docx');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE extraction_status AS ENUM ('pending', 'processing', 'complete', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE flag_type AS ENUM ('missing', 'conflict', 'unusual', 'low_confidence');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE flag_severity AS ENUM ('critical', 'warning', 'info');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(), nullable=False, unique=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("cell_mapping", JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )

    op.create_table(
        "deals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("address", sa.String(), nullable=False),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column("zip_code", sa.String(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("total_units", sa.Integer(), nullable=True),
        sa.Column("status", deal_status, nullable=False, server_default="active"),
        sa.Column("active_template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id"), nullable=True),
        sa.Column("template_outdated", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("document_type", document_type, nullable=False),
        sa.Column("file_name", sa.String(), nullable=False),
        sa.Column("file_data", sa.LargeBinary(), nullable=False),
        sa.Column("file_format", file_format, nullable=False),
        sa.Column("extraction_status", extraction_status, nullable=False, server_default="pending"),
        sa.Column("extraction_error", sa.String(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_documents_deal_id", "documents", ["deal_id"])

    op.create_table(
        "extractions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("document_type", sa.String(), nullable=False),
        sa.Column("extracted_data", JSONB(), nullable=False, server_default="{}"),
        sa.Column("confidence_scores", JSONB(), nullable=False, server_default="{}"),
        sa.Column("claude_model_used", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_extractions_document_id", "extractions", ["document_id"])
    op.create_index("ix_extractions_deal_id", "extractions", ["deal_id"])

    op.create_table(
        "model_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("snapshot_name", sa.String(), nullable=False),
        sa.Column("luckysheet_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("template_id", UUID(as_uuid=True), sa.ForeignKey("templates.id"), nullable=True),
        sa.Column("template_version", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.create_index("ix_model_snapshots_deal_id", "model_snapshots", ["deal_id"])

    op.create_table(
        "flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("tab_name", sa.String(), nullable=False),
        sa.Column("cell_address", sa.String(), nullable=False),
        sa.Column("field_name", sa.String(), nullable=False),
        sa.Column("flag_type", flag_type, nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("severity", flag_severity, nullable=False),
        sa.Column("source_a_label", sa.String(), nullable=True),
        sa.Column("source_a_value", sa.String(), nullable=True),
        sa.Column("source_b_label", sa.String(), nullable=True),
        sa.Column("source_b_value", sa.String(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("resolved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_flags_deal_id", "flags", ["deal_id"])


def downgrade() -> None:
    op.drop_table("flags")
    op.drop_table("model_snapshots")
    op.drop_table("extractions")
    op.drop_table("documents")
    op.drop_table("deals")
    op.drop_table("templates")
    op.drop_table("users")
    for name in ["user_role", "deal_status", "document_type", "file_format",
                 "extraction_status", "flag_type", "flag_severity"]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
