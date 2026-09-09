"""Reincidencia de alerta: ultima ocorrencia e contador de episodios.

Revision ID: 0008_alert_recurrence
Revises: 0007_asset_parent
Create Date: 2026-09-09

Motivacao: uma condicao que vai e volta sozinha (intermitencia) e uma falha
DIFERENTE de uma que fica ligada (degradacao continua), e hoje as duas viram a
mesma pilha de cards. Medido no historico real de 24h: MTR-F01/ANOMALY_DETECTED
abriu e fechou 28 vezes, em episodios de ~1 min que voltavam 1-1,5 min depois.

Com `occurrence_count` e `last_seen_at`, uma reincidencia dentro da janela de
debounce reabre o MESMO registro em vez de criar outro: 57 -> 26 linhas em 24h,
e a frase "reincidiu 9x em 30 min" passa a existir.

O contador conta EPISODIOS FISICOS, nao ciclos do avaliador. Incrementar a cada
ciclo mediria duracao/30s - numero enganoso, e a duracao ja sai de
created_at -> ack_at.

ATENCAO: escrita a mao de proposito. A tabela `alerts` do banco tem uma coluna
`sensor_tag` (com indice) que nao existe em nenhuma migration nem em nenhum .py
do projeto - drift de uma cadeia antiga. `alembic revision --autogenerate`
emitiria um DROP COLUMN dela junto com estes ADDs.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0008_alert_recurrence"
down_revision: str | None = "0007_asset_parent"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "alerts",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column(
            "occurrence_count",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    # Linhas antigas: a unica ocorrencia conhecida e a da criacao.
    op.execute("UPDATE alerts SET last_seen_at = created_at WHERE last_seen_at IS NULL")


def downgrade() -> None:
    op.drop_column("alerts", "occurrence_count")
    op.drop_column("alerts", "last_seen_at")
