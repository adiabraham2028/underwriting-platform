"""Phase 2 tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PG_ENUM

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Pre-define PG enums with create_type=False so op.create_table never issues CREATE TYPE
source_format_enum = PG_ENUM("conam_gl", "conam_ext", "broker", "mri", "unknown", name="source_format", create_type=False)
classification_source_type_enum = PG_ENUM("seed", "ai", "human", name="classification_source_type", create_type=False)
session_status_enum = PG_ENUM("pending_review", "approved", "applied", name="session_status", create_type=False)
match_type_enum = PG_ENUM("exact_known", "ai_high", "ai_low", "human_override", name="match_type_enum", create_type=False)
comp_source_enum = PG_ENUM("import", "deal", name="comp_source", create_type=False)


def upgrade() -> None:
    # Create new enum types idempotently
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE source_format AS ENUM ('conam_gl', 'conam_ext', 'broker', 'mri', 'unknown');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE classification_source_type AS ENUM ('seed', 'ai', 'human');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE session_status AS ENUM ('pending_review', 'approved', 'applied');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE match_type_enum AS ENUM ('exact_known', 'ai_high', 'ai_low', 'human_override');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE comp_source AS ENUM ('import', 'deal');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$
    """)

    # line_item_classifications
    op.create_table(
        "line_item_classifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_line_item", sa.String(), nullable=False),
        sa.Column("normalized_line_item", sa.String(), nullable=False),
        sa.Column("source_format", source_format_enum, nullable=False),
        sa.Column("account_code", sa.String(), nullable=True),
        sa.Column("assigned_category", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("classification_source", classification_source_type_enum, nullable=False, server_default="seed"),
        sa.Column("confirmed_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("override_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lic_tenant_id", "line_item_classifications", ["tenant_id"])
    op.create_index("ix_lic_account_code", "line_item_classifications", ["account_code"])
    op.create_index("ix_lic_normalized", "line_item_classifications", ["normalized_line_item"])

    # classification_sessions
    op.create_table(
        "classification_sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", session_status_enum, nullable=False, server_default="pending_review"),
        sa.Column("total_line_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("auto_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("needs_review", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("human_corrected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_cs_deal_id", "classification_sessions", ["deal_id"])

    # classification_session_items
    op.create_table(
        "classification_session_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("session_id", UUID(as_uuid=True), sa.ForeignKey("classification_sessions.id"), nullable=False),
        sa.Column("line_item_name", sa.String(), nullable=False),
        sa.Column("account_code", sa.String(), nullable=True),
        sa.Column("monthly_values", JSONB(), nullable=False, server_default="{}"),
        sa.Column("trailing_total", sa.Float(), nullable=False, server_default="0"),
        sa.Column("ai_suggested_category", sa.String(), nullable=False),
        sa.Column("ai_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("final_category", sa.String(), nullable=False),
        sa.Column("match_type", match_type_enum, nullable=False, server_default="ai_low"),
        sa.Column("was_corrected", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_csi_session_id", "classification_session_items", ["session_id"])

    # expense_comps
    op.create_table(
        "expense_comps",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("property_name", sa.String(), nullable=False),
        sa.Column("yardi_mri_code", sa.String(), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("num_units", sa.Integer(), nullable=True),
        sa.Column("avg_sf", sa.Float(), nullable=True),
        sa.Column("city", sa.String(), nullable=True),
        sa.Column("state", sa.String(), nullable=True),
        sa.Column("financial_stmt_year", sa.String(), nullable=False),
        sa.Column("financial_stmt_type", sa.String(), nullable=False),
        sa.Column("metrics", JSONB(), nullable=False, server_default="{}"),
        sa.Column("metrics_per_unit_yr", JSONB(), nullable=False, server_default="{}"),
        sa.Column("metrics_per_unit_mo", JSONB(), nullable=False, server_default="{}"),
        sa.Column("source", comp_source_enum, nullable=False, server_default="import"),
        sa.Column("deal_id", UUID(as_uuid=True), sa.ForeignKey("deals.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_ec_tenant_id", "expense_comps", ["tenant_id"])

    # client_templates
    op.create_table(
        "client_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("file_data", sa.LargeBinary(), nullable=True),
        sa.Column("cell_mapping", JSONB(), nullable=False, server_default="{}"),
        sa.Column("mapping_confirmed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("tab_names", JSONB(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
    )
    op.create_index("ix_ct_tenant_id", "client_templates", ["tenant_id"])

    # tenant_settings
    op.create_table(
        "tenant_settings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("auto_accept_threshold", sa.Float(), nullable=False, server_default="0.90"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tenant_settings")
    op.drop_table("client_templates")
    op.drop_table("expense_comps")
    op.drop_table("classification_session_items")
    op.drop_table("classification_sessions")
    op.drop_table("line_item_classifications")
    for name in ["source_format", "classification_source_type", "session_status", "match_type_enum", "comp_source"]:
        op.execute(f"DROP TYPE IF EXISTS {name}")
