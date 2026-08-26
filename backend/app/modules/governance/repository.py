"""Acesso a dados do log de auditoria e da trilha de TAG."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.governance.models import AuditLog, TagAuditEvent


class AuditRepository:
    """Consulta do log de auditoria (escrita feita pelo middleware)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(self, limit: int = 100) -> list[AuditLog]:
        result = await self._session.execute(
            select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
        )
        return list(result.scalars().all())


def integrity_hash(payload: dict[str, Any]) -> str:
    """SHA-256 do estado do evento - detecta adulteracao retroativa do log."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class TagAuditRepository:
    """Trilha imutavel de associacao / movimentacao / edicao de TAG na planta."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        action: str,
        user_id: str,
        user_role: str,
        tag_id: str,
        equipment_id: str | None = None,
        coords_before: dict[str, Any] | None = None,
        coords_after: dict[str, Any] | None = None,
        data_origin: str = "humano",
        map_version: str = "v1.0",
    ) -> TagAuditEvent:
        created_at = datetime.now(UTC)
        payload = {
            "action": action,
            "user_id": user_id,
            "user_role": user_role,
            "tag_id": tag_id,
            "equipment_id": equipment_id,
            "map_version": map_version,
            "coords_before": coords_before,
            "coords_after": coords_after,
            "data_origin": data_origin,
            "created_at": created_at.isoformat(),
        }
        event = TagAuditEvent(
            action=action,
            user_id=user_id,
            user_role=user_role,
            tag_id=tag_id,
            equipment_id=equipment_id,
            map_version=map_version,
            coords_before=coords_before,
            coords_after=coords_after,
            data_origin=data_origin,
            validation_status="validado",
            validated_by=user_id,
            integrity_hash=integrity_hash(payload),
            created_at=created_at,
        )
        self._session.add(event)
        await self._session.commit()
        await self._session.refresh(event)
        return event

    async def list_recent(self, limit: int, tag_id: str | None = None) -> list[TagAuditEvent]:
        stmt = select(TagAuditEvent).order_by(TagAuditEvent.created_at.desc()).limit(limit)
        if tag_id:
            stmt = stmt.where(TagAuditEvent.tag_id == tag_id)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
