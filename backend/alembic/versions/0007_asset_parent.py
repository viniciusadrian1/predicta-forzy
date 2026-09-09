"""Vincula pontos de medicao a um ativo pai (parent_tag).

Revision ID: 0007_asset_parent
Revises: 0006_governance
Create Date: 2026-09-09

Motivacao: MTR-F01 e MTR-F02 nunca foram dois motores. Sao os DOIS MANCAIS do
mesmo conjunto motor-bomba da Forzy. Com `parent_tag` eles deixam de aparecer
como ativos independentes e passam a ser PONTOS DE MEDICAO de um unico ativo.

Nulo = ativo raiz (aparece na lista). Preenchido = ponto de medicao do pai.
Cada ponto mantem sua propria telemetria, alertas e modelos de ML — o que muda
e a apresentacao: um equipamento, dois pontos.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0007_asset_parent"
down_revision: str | None = "0006_governance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("parent_tag", sa.String(length=64), nullable=True))
    op.create_index("ix_assets_parent_tag", "assets", ["parent_tag"])


def downgrade() -> None:
    op.drop_index("ix_assets_parent_tag", table_name="assets")
    op.drop_column("assets", "parent_tag")
