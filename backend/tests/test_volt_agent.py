"""Testes do agente do Volt (function calling): loop de ferramentas + guardrails."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.modules.volt.agent import VoltAgent
from app.modules.volt.schemas import VoltStateModel

_ASSET = SimpleNamespace(
    tag="MTR-001",
    name="Motor da bomba",
    status="ok",
    manufacturer="WEG",
    model="W22 IR3",
    power_kw=7.5,
    voltage_v=220,
    nominal_current_a=25.4,
    nominal_rpm=1755,
    insulation_class="F",
    ip_rating="IP55",
)


class _Assets:
    async def get_asset_by_tag(self, tag):
        return _ASSET if tag == "MTR-001" else None


class _Telemetry:
    async def latest(self, tag):
        return [{"variable": "Corrente", "value": 21.5}]


class _Orders:
    async def next_number(self, tag):
        return f"{tag}-OS001"

    async def create(self, order):
        return order


class _FakeLlm:
    """LLM roteirizado: devolve as mensagens na ordem definida."""

    def __init__(self, script):
        self._script = list(script)

    async def complete_with_tools(self, messages, tools):
        return self._script.pop(0)


def _agent(script):
    return VoltAgent(
        assets=_Assets(),
        telemetry=_Telemetry(),
        work_orders=_Orders(),
        settings=Settings(),
        role="engineer",
        llm=_FakeLlm(script),
    )


def _tool_call(name, arguments):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "c1", "function": {"name": name, "arguments": arguments}}],
    }


async def test_agent_uses_asset_tool_then_answers():
    agent = _agent(
        [
            _tool_call("dados_do_ativo", '{"tag": "MTR-001"}'),
            {"role": "assistant", "content": "O MTR-001 é um WEG W22 de 7,5 kW."},
        ]
    )
    reply = await agent.run("me fala do MTR-001", VoltStateModel(), [])
    assert "WEG" in reply.message
    assert reply.state.asset_tag == "MTR-001"


async def test_agent_work_order_blocked_on_critical_asset():
    # MTR-001 e o ativo critico padrao -> abrir OS deve ser recusado (handoff).
    agent = _agent(
        [
            _tool_call(
                "abrir_ordem_servico",
                '{"tag":"MTR-001","sintoma":"vibracao","diagnostico":"Rolamento","confianca":0.85}',
            ),
            {"role": "assistant", "content": "Encaminhei a um técnico (ativo crítico)."},
        ]
    )
    reply = await agent.run("abre uma OS pro MTR-001", VoltStateModel(), [])
    assert reply.work_order is None
    assert reply.handoff is not None
    assert reply.done is True


@pytest.mark.parametrize("no_key_provider", ["openai", "anthropic"])
def test_llm_offline_without_key_disables_agent(no_key_provider):
    # Sem chave, o modo e offline -> o VoltService nao instancia o agente.
    from app.modules.rag.llm import LlmClient

    assert LlmClient(provider=no_key_provider, api_key="", model="m").mode == "offline"
