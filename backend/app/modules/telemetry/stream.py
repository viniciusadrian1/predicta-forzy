"""Broadcaster em processo para streaming de telemetria via SSE.

Cada conexao SSE registra uma fila; a ingestao publica os eventos processados
em todas as filas ativas. Consumidores lentos descartam eventos (fila limitada).
"""

from __future__ import annotations

import asyncio

TelemetryEvent = dict[str, object]


class TelemetryBroadcaster:
    """Distribui eventos de telemetria para os assinantes SSE ativos."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[TelemetryEvent]] = set()

    def subscribe(self) -> asyncio.Queue[TelemetryEvent]:
        queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=200)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[TelemetryEvent]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, event: TelemetryEvent) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # consumidor lento: o evento e descartado
                continue

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# Singleton compartilhado entre a ingestao e os endpoints SSE.
broadcaster = TelemetryBroadcaster()
