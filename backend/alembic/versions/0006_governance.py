"""governanca: rastreabilidade de ativos, limiares por ativo, feedback de ML e trilha de TAG

Revision ID: 0006_governance
Revises: 0005_work_orders
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_governance"
down_revision: str | None = "0005_work_orders"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # --- assets: rastreabilidade do cadastro + limiares por ativo ---
    op.add_column(
        "assets",
        sa.Column("data_origin", sa.String(length=16), nullable=False, server_default="humano"),
    )
    op.add_column("assets", sa.Column("registration_photo_at", sa.DateTime(timezone=True)))
    op.add_column("assets", sa.Column("ocr_engine_version", sa.String(length=48)))
    op.add_column("assets", sa.Column("ocr_confidence", sa.Float()))
    op.add_column("assets", sa.Column("validated_by", sa.String(length=120)))
    op.add_column("assets", sa.Column("validated_at", sa.DateTime(timezone=True)))
    op.add_column("assets", sa.Column("image_source", sa.String(length=48)))
    op.add_column("assets", sa.Column("visual_condition", sa.String(length=300)))
    op.add_column("assets", sa.Column("vib_warning", sa.Float()))
    op.add_column("assets", sa.Column("vib_critical", sa.Float()))
    op.add_column("assets", sa.Column("temp_warning", sa.Float()))
    op.add_column("assets", sa.Column("temp_critical", sa.Float()))

    # --- ml_feedback: feedback loop persistido ---
    op.create_table(
        "ml_feedback",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_tag", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=48), nullable=False),
        sa.Column("prediction", sa.String(length=120), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.String(length=400)),
        sa.Column("actor", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ml_feedback_asset_tag", "ml_feedback", ["asset_tag"])
    op.create_index("ix_ml_feedback_created_at", "ml_feedback", ["created_at"])

    # --- tag_audit_event: trilha de associacao/movimentacao de TAG ---
    op.create_table(
        "tag_audit_event",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("user_role", sa.String(length=24), nullable=False),
        sa.Column("tag_id", sa.String(length=64), nullable=False),
        sa.Column("equipment_id", sa.String(length=120)),
        sa.Column("map_version", sa.String(length=16), nullable=False),
        sa.Column("coords_before", sa.JSON()),
        sa.Column("coords_after", sa.JSON()),
        sa.Column("data_origin", sa.String(length=16), nullable=False),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("validation_status", sa.String(length=16), nullable=False),
        sa.Column("validated_by", sa.String(length=120)),
        sa.Column("integrity_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tag_audit_event_tag_id", "tag_audit_event", ["tag_id"])
    op.create_index("ix_tag_audit_event_created_at", "tag_audit_event", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_tag_audit_event_created_at", table_name="tag_audit_event")
    op.drop_index("ix_tag_audit_event_tag_id", table_name="tag_audit_event")
    op.drop_table("tag_audit_event")
    op.drop_index("ix_ml_feedback_created_at", table_name="ml_feedback")
    op.drop_index("ix_ml_feedback_asset_tag", table_name="ml_feedback")
    op.drop_table("ml_feedback")
    for col in (
        "temp_critical",
        "temp_warning",
        "vib_critical",
        "vib_warning",
        "visual_condition",
        "image_source",
        "validated_at",
        "validated_by",
        "ocr_confidence",
        "ocr_engine_version",
        "registration_photo_at",
        "data_origin",
    ):
        op.drop_column("assets", col)
