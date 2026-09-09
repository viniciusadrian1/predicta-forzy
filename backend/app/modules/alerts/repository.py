"""Acesso a dados dos alertas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.alerts.models import Alert


class AlertRepository:
    """Operacoes de persistencia e consulta de alertas."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, alert: Alert) -> Alert:
        self._session.add(alert)
        await self._session.commit()
        await self._session.refresh(alert)
        return alert

    async def list_alerts(
        self,
        asset_tag: str | None = None,
        severity: str | None = None,
        only_active: bool = False,
        limit: int = 100,
        acknowledged_by: str | None = None,
    ) -> list[Alert]:
        stmt = select(Alert)
        if asset_tag:
            stmt = stmt.where(Alert.asset_tag == asset_tag)
        if severity:
            stmt = stmt.where(Alert.severity == severity)
        if only_active:
            stmt = stmt.where(Alert.acknowledged == False)  # noqa: E712
        if acknowledged_by == "humano":
            # Fechamento automatico grava ack_by="auto"; o historico de quem
            # reconheceu de verdade some no meio dele se nao der para separar.
            stmt = stmt.where(
                Alert.acknowledged == True,  # noqa: E712
                Alert.ack_by.is_not(None),
                Alert.ack_by != "auto",
            ).order_by(Alert.ack_at.desc()).limit(limit)
            result = await self._session.execute(stmt)
            return list(result.scalars().all())
        stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, alert_id: UUID) -> Alert | None:
        return await self._session.get(Alert, alert_id)

    async def has_open(self, asset_tag: str, alert_type: str) -> bool:
        """Indica se ja existe um alerta ABERTO deste tipo para o ativo.

        Sem janela de tempo: enquanto a condicao seguir verdadeira o alerta
        continua sendo o mesmo episodio, e nao um alerta novo a cada ciclo.
        """
        stmt = (
            select(Alert.id)
            .where(
                Alert.asset_tag == asset_tag,
                Alert.alert_type == alert_type,
                Alert.acknowledged == False,  # noqa: E712
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def reabrir_recente(
        self, asset_tag: str, alert_type: str, minutes: int
    ) -> bool:
        """Reabre o alerta que acabou de fechar, em vez de criar outro.

        Uma condicao intermitente normaliza e volta em segundos. Como
        `close_resolved` ja fechou o registro, `has_open` libera e nasceria uma
        linha nova a cada ida e volta - 28 delas em 24h so num tipo de alerta.
        Dentro da janela, isso vira reincidencia do MESMO episodio: o contador
        sobe e `last_seen_at` avanca.

        So reabre o que a MAQUINA fechou (ack_by="auto"). Reconhecimento humano
        e uma decisao registrada; reabri-la por baixo apagaria o comentario do
        tecnico e faria o alerta ressurgir sem explicacao.
        """
        desde = datetime.now(UTC) - timedelta(minutes=minutes)
        stmt = (
            select(Alert)
            .where(
                Alert.asset_tag == asset_tag,
                Alert.alert_type == alert_type,
                Alert.acknowledged == True,  # noqa: E712
                Alert.ack_by == "auto",
                Alert.ack_at.is_not(None),
                Alert.ack_at >= desde,
            )
            .order_by(Alert.ack_at.desc())
            .limit(1)
        )
        alerta = (await self._session.execute(stmt)).scalars().first()
        if alerta is None:
            return False
        alerta.acknowledged = False
        alerta.ack_by = None
        alerta.ack_at = None
        alerta.ack_comment = None
        alerta.occurrence_count = (alerta.occurrence_count or 1) + 1
        alerta.last_seen_at = datetime.now(UTC)
        await self._session.commit()
        return True

    async def marcar_ocorrencia(self, asset_tag: str, alert_type: str) -> None:
        """Avanca `last_seen_at` do alerta aberto: a condicao segue valendo."""
        stmt = (
            update(Alert)
            .where(
                Alert.asset_tag == asset_tag,
                Alert.alert_type == alert_type,
                Alert.acknowledged == False,  # noqa: E712
            )
            .values(last_seen_at=datetime.now(UTC))
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def close_resolved(self, asset_tag: str, active_types: set[str]) -> int:
        """Fecha os alertas de ESTADO cuja condicao nao vale mais.

        Contrapartida de ``has_open``: sem isto, "ativo" significaria apenas
        "foi verdade uma vez e ninguem reconheceu", e o primeiro episodio
        silenciaria todos os seguintes. ``ack_by="auto"`` distingue o
        fechamento automatico do reconhecimento humano na trilha de auditoria.
        """
        governed = {
            "THRESHOLD_APPROACHING",
            "THRESHOLD_EXCEEDED",
            "CIRCUIT_BREAKER",
            "ANOMALY_DETECTED",
        }
        stale = governed - active_types
        if not stale:
            return 0
        stmt = (
            update(Alert)
            .where(
                Alert.asset_tag == asset_tag,
                Alert.acknowledged == False,  # noqa: E712
                Alert.alert_type.in_(stale),
            )
            .values(
                acknowledged=True,
                ack_by="auto",
                ack_at=datetime.now(UTC),
                ack_comment="Fechado automaticamente: condicao normalizada.",
            )
        )
        result = await self._session.execute(stmt)
        await self._session.commit()
        return int(result.rowcount or 0)

    async def acknowledge(self, alert: Alert, actor: str, comment: str | None = None) -> Alert:
        alert.acknowledged = True
        alert.ack_by = actor
        alert.ack_at = datetime.now(UTC)
        alert.ack_comment = comment
        await self._session.commit()
        await self._session.refresh(alert)
        return alert
