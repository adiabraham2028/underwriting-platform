"""Add unit_type_mapping to deals

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-25 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "deals",
        sa.Column("unit_type_mapping", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("deals", "unit_type_mapping")
