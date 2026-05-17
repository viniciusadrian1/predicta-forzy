"""Cliente OPC-UA assincrono para ingestao de telemetria.

Conecta ao simulador/gateway, cria uma *subscription* (modelo push, nao
polling) nos nodes de sensor do motor e entrega cada amostra a um callback.
Reconecta automaticamente, com backoff, em caso de falha de rede.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from asyncua import Client, Node

logger = logging.getLogger("forzy.opcua.client")

# Nodes de sensor publicados pelo simulador (sob Forzy/Motor/<TAG>).
SENSOR_VARIABLES = (
    "Tensao",
    "Corrente",
    "Temperatura",
    "Rotacao",
    "Vibracao_Velocidade_RMS",
    "Vibracao_Aceleracao_RMS",
)


@dataclass(slots=True)
class TelemetrySample:
    """Uma leitura de sensor recebida via OPC-UA."""

    asset_tag: str
    variable: str
    value: float
    timestamp: datetime
    quality: int
    source: str


SampleCallback = Callable[[TelemetrySample], Awaitable[None]]


def _extract_metadata(data: object) -> tuple[datetime, int]:
    """Extrai timestamp e qualidade da notificacao, com fallbacks seguros."""
    timestamp = datetime.now(UTC)
    quality = 0
    monitored = getattr(data, "monitored_item", None)
    data_value = getattr(monitored, "Value", None)
    if data_value is not None:
        source_ts = getattr(data_value, "SourceTimestamp", None)
        if isinstance(source_ts, datetime):
            timestamp = source_ts if source_ts.tzinfo else source_ts.replace(tzinfo=UTC)
        status = getattr(data_value, "StatusCode", None)
        status_value = getattr(status, "value", None)
        if status_value is not None:
            quality = int(status_value)
    return timestamp, quality


class _SubscriptionHandler:
    """Recebe as notificacoes de mudanca de valor da subscription."""

    def __init__(self, node_map: dict[str, str], asset_tag: str, callback: SampleCallback) -> None:
        self._node_map = node_map  # nodeid (string) -> nome da variavel
        self._asset_tag = asset_tag
        self._callback = callback

    async def datachange_notification(self, node: Node, value: object, data: object) -> None:
        variable = self._node_map.get(node.nodeid.to_string())
        if variable is None:
            return
        try:
            numeric = float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        timestamp, quality = _extract_metadata(data)
        await self._callback(
            TelemetrySample(
                asset_tag=self._asset_tag,
                variable=variable,
                value=numeric,
                timestamp=timestamp,
                quality=quality,
                source="opcua",
            )
        )


class OpcuaIngestionClient:
    """Gerencia a conexao OPC-UA e a subscription de telemetria."""

    def __init__(
        self,
        endpoint: str,
        namespace_uri: str,
        publishing_interval_ms: int,
        asset_tag: str,
        on_sample: SampleCallback,
    ) -> None:
        self._endpoint = endpoint
        self._namespace_uri = namespace_uri
        self._period = publishing_interval_ms
        self._asset_tag = asset_tag
        self._on_sample = on_sample
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        """Inicia o loop de ingestao como uma task em background."""
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        """Encerra o loop de ingestao e libera a conexao."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run_forever(self) -> None:
        backoff = 2.0
        while self._running:
            try:
                await self._connect_and_subscribe()
                backoff = 2.0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # reconectar em qualquer falha de rede
                logger.warning("OPC-UA indisponivel (%s); nova tentativa em %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 1.5, 30.0)

    async def _connect_and_subscribe(self) -> None:
        client = Client(url=self._endpoint)
        async with client:
            ns = await client.get_namespace_index(self._namespace_uri)
            motor = await client.nodes.objects.get_child(
                [f"{ns}:Forzy", f"{ns}:Motor", f"{ns}:{self._asset_tag}"]
            )
            node_map: dict[str, str] = {}
            nodes: list[Node] = []
            for variable in SENSOR_VARIABLES:
                node = await motor.get_child(f"{ns}:{variable}")
                node_map[node.nodeid.to_string()] = variable
                nodes.append(node)

            handler = _SubscriptionHandler(node_map, self._asset_tag, self._on_sample)
            subscription = await client.create_subscription(self._period, handler)
            await subscription.subscribe_data_change(nodes)
            logger.info(
                "Subscription OPC-UA ativa: %d nodes do ativo %s",
                len(nodes),
                self._asset_tag,
            )

            ticks = 0
            while self._running:
                await asyncio.sleep(1.0)
                ticks += 1
                if ticks % 15 == 0:
                    # Probe de liveness: forca a deteccao de conexao perdida.
                    await client.nodes.server_state.read_value()
            await subscription.delete()
