"""Acesso a dados dos alertas."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
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
    ) -> list[Alert]:
        stmt = select(Alert)
        if asset_tag:
            stmt = stmt.where(Alert.asset_tag == asset_tag)
        if severity:
            stmt = stmt.where(Alert.severity == severity)
        if only_active:
            stmt = stmt.where(Alert.acknowledged == False)  # noqa: E712
        stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get(self, alert_id: UUID) -> Alert | None:
        return await self._session.get(Alert, alert_id)

    async def has_recent_unacked(self, asset_tag: str, alert_type: str, minutes: int) -> bool:
        """Indica se ja existe um alerta similar nao reconhecido recente."""
        since = datetime.now(UTC) - timedelta(minutes=minutes)
        stmt = (
            select(Alert.id)
            .where(
                Alert.asset_tag == asset_tag,
                Alert.alert_type == alert_type,
                Alert.acknowledged == False,  # noqa: E712
                Alert.created_at >= since,
            )
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.first() is not None

    async def acknowledge(self, alert: Alert, actor: str, comment: str | None = None) -> Alert:
        alert.acknowledged = True
        alert.ack_by = actor
        alert.ack_at = datetime.now(UTC)
        alert.ack_comment = comment
        await self._session.commit()
        await self._session.refresh(alert)
        return alert

    async def active_severities(self, asset_tag: str) -> list[str]:
        """Severidades dos alertas ativos (nao reconhecidos) de um ativo."""
        stmt = select(Alert.severity).where(
            Alert.asset_tag == asset_tag,
            Alert.acknowledged == False,  # noqa: E712
        )
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all()]
