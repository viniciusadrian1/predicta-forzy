"""initial catalog schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-16

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plants",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(["plant_id"], ["plants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "assets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column("asset_type", sa.String(length=48), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("manufacturer", sa.String(length=80), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("serial_number", sa.String(length=80), nullable=True),
        sa.Column("power_kw", sa.Float(), nullable=True),
        sa.Column("voltage_v", sa.Float(), nullable=True),
        sa.Column("nominal_current_a", sa.Float(), nullable=True),
        sa.Column("nominal_rpm", sa.Integer(), nullable=True),
        sa.Column("connection_type", sa.String(length=32), nullable=True),
        sa.Column("insulation_class", sa.String(length=16), nullable=True),
        sa.Column("ip_rating", sa.String(length=16), nullable=True),
        sa.Column("weight_kg", sa.Float(), nullable=True),
        sa.Column("manufacture_date", sa.Date(), nullable=True),
        sa.Column("plant_id", sa.Uuid(), nullable=True),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("position_x", sa.Float(), nullable=True),
        sa.Column("position_y", sa.Float(), nullable=True),
        sa.Column("datasheet_url", sa.String(length=300), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["plant_id"], ["plants.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tag"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=48), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("path", sa.String(length=300), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("assets")
    op.drop_table("areas")
    op.drop_table("plants")
