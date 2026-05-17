"""Regras de negocio do modulo de alertas."""

from __future__ import annotations

from uuid import UUID

from app.modules.alerts.models import Alert
from app.modules.alerts.repository import AlertRepository


class AlertNotFoundError(Exception):
    """Nenhum alerta encontrado para o id informado."""


class AlertService:
    """Consulta e reconhecimento de alertas."""

    def __init__(self, repository: AlertRepository) -> None:
        self._repo = repository

    async def list_alerts(
        self,
        asset_tag: str | None = None,
        severity: str | None = None,
        only_active: bool = False,
        limit: int = 100,
    ) -> list[Alert]:
        return await self._repo.list_alerts(asset_tag, severity, only_active, limit)

    async def acknowledge(self, alert_id: UUID, actor: str, comment: str | None = None) -> Alert:
        alert = await self._repo.get(alert_id)
        if alert is None:
            raise AlertNotFoundError(str(alert_id))
        return await self._repo.acknowledge(alert, actor, comment)
