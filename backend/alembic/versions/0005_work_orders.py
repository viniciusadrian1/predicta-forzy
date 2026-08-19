"""work_orders table (chatbot Volt)

Revision ID: 0005_work_orders
Revises: 0003_users
Create Date: 2026-08-19

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_work_orders"
down_revision: str | None = "0003_users"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "work_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=64), nullable=False),
        sa.Column("asset_tag", sa.String(length=64), nullable=False),
        sa.Column("symptom", sa.String(length=32), nullable=False),
        sa.Column("fault", sa.String(length=160), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("opened_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_work_orders_number", "work_orders", ["number"], unique=True)
    op.create_index("ix_work_orders_asset_tag", "work_orders", ["asset_tag"])
    op.create_index("ix_work_orders_created_at", "work_orders", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_work_orders_created_at", table_name="work_orders")
    op.drop_index("ix_work_orders_asset_tag", table_name="work_orders")
    op.drop_index("ix_work_orders_number", table_name="work_orders")
    op.drop_table("work_orders")
