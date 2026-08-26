"""Persistencia do feedback de ML (loop de melhoria)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ml.models import MlFeedback


class MlFeedbackRepository:
    """Grava e consulta os reportes de feedback dos operadores."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, feedback: MlFeedback) -> MlFeedback:
        self._session.add(feedback)
        await self._session.commit()
        await self._session.refresh(feedback)
        return feedback

    async def list_recent(self, limit: int, asset_tag: str | None = None) -> list[MlFeedback]:
        stmt = select(MlFeedback).order_by(MlFeedback.created_at.desc()).limit(limit)
        if asset_tag:
            stmt = stmt.where(MlFeedback.asset_tag == asset_tag)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
