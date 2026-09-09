"""Testes do agente do Volt (function calling): loop de ferramentas + guardrails."""

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.modules.volt.agent import VoltAgent
from app.modules.volt.schemas import VoltStateModel

_ASSET = SimpleNamespace(
    tag="MTR-001",
    parent_tag=None,
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
    vib_warning=None,
    vib_critical=None,
    temp_warning=None,
    temp_critical=None,
)


class _Assets:
    async def get_asset_by_tag(self, tag):
        return _ASSET if tag == "MTR-001" else None

    async def list_points(self, parent_tag=None):
        return []  # ativo simples: mede a si proprio, sem pontos filhos

    async def list_assets(self):
        return [_ASSET]


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


# --- O agente enxergando o mesmo sistema que as telas ------------------------

_CONJUNTO = SimpleNamespace(
    tag="MTR-F00", name="Motor-bomba Forzy — bancada de teste", status="unknown",
    parent_tag=None, manufacturer="Forzy", model="Bancada R11", power_kw=None,
    voltage_v=220, nominal_current_a=None, nominal_rpm=None,
    insulation_class=None, ip_rating=None,
    vib_warning=None,
    vib_critical=None,
    temp_warning=None,
    temp_critical=None,
)
_MANCAL_A = SimpleNamespace(
    tag="MTR-F01", name="Bancada de teste — mancal lado bomba", status="ok",
    parent_tag="MTR-F00", manufacturer="Forzy", model="Bancada R11", power_kw=None,
    voltage_v=220, nominal_current_a=None, nominal_rpm=None,
    insulation_class=None, ip_rating=None,
    vib_warning=None,
    vib_critical=None,
    temp_warning=None,
    temp_critical=None,
)
_MANCAL_B = SimpleNamespace(
    tag="MTR-F02", name="Bancada de teste — mancal lado motor", status="warning",
    parent_tag="MTR-F00", manufacturer="Forzy", model="Bancada R11", power_kw=None,
    voltage_v=220, nominal_current_a=None, nominal_rpm=None,
    insulation_class=None, ip_rating=None,
    vib_warning=None,
    vib_critical=None,
    temp_warning=None,
    temp_critical=None,
)


class _AssetsConjunto:
    async def get_asset_by_tag(self, tag):
        return {"MTR-F00": _CONJUNTO, "MTR-F01": _MANCAL_A, "MTR-F02": _MANCAL_B}.get(tag)

    async def list_points(self, parent_tag=None):
        pontos = [_MANCAL_A, _MANCAL_B]
        return [p for p in pontos if parent_tag is None or p.parent_tag == parent_tag]

    async def list_assets(self):
        return [_CONJUNTO, _MANCAL_A, _MANCAL_B]


class _TelemetriaDosPontos:
    """So os MANCAIS medem; o conjunto nao tem linha nenhuma."""

    async def latest(self, tag):
        if tag == "MTR-F01":
            return [{"variable": "Vibracao_Velocidade_RMS", "value": 2.0},
                    {"variable": "Temperatura", "value": 41.0}]
        if tag == "MTR-F02":
            return [{"variable": "Vibracao_Velocidade_RMS", "value": 7.4},
                    {"variable": "Temperatura", "value": 38.0}]
        return []


async def test_ferramenta_do_agente_devolve_status_e_leituras_do_conjunto():
    """O que o LLM recebe precisa bater com o que as telas mostram.

    Era esta ferramenta que alimentava a resposta "o status do motor é
    'unknown' e não há leituras atuais disponíveis": ela lia o status CRU do
    conjunto e pedia telemetria da TAG dele, que nao mede nada.
    """
    agente = VoltAgent(
        assets=_AssetsConjunto(),
        telemetry=_TelemetriaDosPontos(),
        work_orders=_Orders(),
        settings=Settings(),
        role="engineer",
        llm=_FakeLlm([]),
    )
    agente._state = VoltStateModel(
        step="aguardando_ativo", asset_tag=None, asset_name=None,
        symptom=None, not_found_attempts=0,
    )
    dados = await agente._t_dados_do_ativo("MTR-F00")

    assert dados["encontrado"] is True
    # Status consolidado: o pior entre os mancais, nunca o "unknown" da linha.
    assert dados["status"] == "warning"
    # Leituras vindas dos pontos, com o PIOR valor de cada grandeza.
    assert dados["leituras_atuais"]["Vibracao_Velocidade_RMS"] == 7.4
    assert dados["leituras_atuais"]["Temperatura"] == 41.0
    # E dizendo de qual mancal veio cada numero.
    assert dados["origem_das_leituras"]["Vibracao_Velocidade_RMS"] == _MANCAL_B.name


async def test_agente_diagnostica_conjunto_com_leituras_dos_mancais():
    """Sem o fan-out, o diagnostico do conjunto caia em "sem dados de sensor"."""
    agente = VoltAgent(
        assets=_AssetsConjunto(),
        telemetry=_TelemetriaDosPontos(),
        work_orders=_Orders(),
        settings=Settings(),
        role="engineer",
        llm=_FakeLlm([]),
    )
    agente._state = VoltStateModel(
        step="aguardando_ativo", asset_tag=None, asset_name=None,
        symptom=None, not_found_attempts=0,
    )
    agente._diagnosis = None
    agente._critical = set()
    resultado = await agente._t_diagnosticar("MTR-F00", "vibracao")
    assert "sem dados de sensor" not in resultado["falha"].lower()
    assert resultado["confianca"] >= 0.5  # 7.4 mm/s cai na faixa de atencao


async def test_ferramenta_entrega_os_DOIS_sensores_do_conjunto():
    """MTR-F00 tem dois mancais: a resposta nao pode sair por um so.

    Antes, a ferramenta consolidava tudo no pior valor e o modelo recebia um
    unico bloco de leituras — dava para responder por um sensor sem nem avisar
    que existia outro. Agora o payload carrega cada ponto separado, e o
    consolidado continua ali so para alimentar o diagnostico.
    """
    agente = VoltAgent(
        assets=_AssetsConjunto(),
        telemetry=_TelemetriaDosPontos(),
        work_orders=_Orders(),
        settings=Settings(),
        role="engineer",
        llm=_FakeLlm([]),
    )
    agente._state = VoltStateModel(
        step="aguardando_ativo", asset_tag=None, asset_name=None,
        symptom=None, not_found_attempts=0,
    )
    dados = await agente._t_dados_do_ativo("MTR-F00")

    assert dados["total_de_pontos"] == 2
    pontos = {p["tag"]: p for p in dados["pontos_de_medicao"]}
    assert set(pontos) == {"MTR-F01", "MTR-F02"}

    # Cada mancal com as SUAS leituras, nao a mistura dos dois.
    assert pontos["MTR-F01"]["leituras"]["Vibracao_Velocidade_RMS"] == 2.0
    assert pontos["MTR-F02"]["leituras"]["Vibracao_Velocidade_RMS"] == 7.4
    assert pontos["MTR-F01"]["leituras"]["Temperatura"] == 41.0
    assert pontos["MTR-F02"]["leituras"]["Temperatura"] == 38.0
    # E cada um com o proprio status, que difere entre eles.
    assert pontos["MTR-F01"]["status"] == "ok"
    assert pontos["MTR-F02"]["status"] == "warning"

    # O consolidado segue existindo para o diagnostico (pior de cada grandeza).
    assert dados["leituras_atuais"]["Vibracao_Velocidade_RMS"] == 7.4
    assert dados["leituras_atuais"]["Temperatura"] == 41.0


async def test_ativo_de_ponto_unico_tambem_lista_seu_ponto():
    """Ativo que mede a si proprio aparece como UM ponto, nao como zero.

    Assim o modelo tem sempre a mesma forma de payload e nao precisa tratar
    dois formatos diferentes.
    """
    agente = VoltAgent(
        assets=_Assets(),
        telemetry=_Telemetry(),
        work_orders=_Orders(),
        settings=Settings(),
        role="engineer",
        llm=_FakeLlm([]),
    )
    agente._state = VoltStateModel(
        step="aguardando_ativo", asset_tag=None, asset_name=None,
        symptom=None, not_found_attempts=0,
    )
    dados = await agente._t_dados_do_ativo("MTR-001")
    assert dados["total_de_pontos"] == 1
    assert dados["pontos_de_medicao"][0]["tag"] == "MTR-001"
    assert dados["origem_das_leituras"] is None  # nao ha fan-out aqui


async def test_ferramenta_entrega_saude_limiares_e_alertas():
    """O que a tela de saude mostra precisa chegar ao modelo.

    A ferramenta so devolvia placa + leitura instantanea. Perguntado sobre RUL,
    anomalia, alerta ou limiar, o modelo respondia "nao tenho acesso" — porque
    de fato nao tinha: o dado nunca entrava no contexto dele.
    """
    agente = VoltAgent(
        assets=_AssetsConjunto(),
        telemetry=_TelemetriaDosPontos(),
        work_orders=_Orders(),
        settings=Settings(),
        role="engineer",
        llm=_FakeLlm([]),
    )
    agente._state = VoltStateModel(
        step="aguardando_ativo", asset_tag=None, asset_name=None,
        symptom=None, not_found_attempts=0,
    )
    dados = await agente._t_dados_do_ativo("MTR-F00")

    for ponto in dados["pontos_de_medicao"]:
        # As chaves precisam existir mesmo quando o ML esta indisponivel:
        # o modelo tem que ver que o campo EXISTE e esta vazio, e nao concluir
        # que a metrica nao faz parte do sistema.
        assert "saude" in ponto
        assert "alertas" in ponto
        assert "limiares" in ponto
        # Limiar sempre resolve: do proprio ativo ou o fallback ISO.
        assert ponto["limiares"]["vib_critical"] > 0
        assert ponto["limiares"]["temp_critical"] > 0


def test_ferramenta_anuncia_as_metricas_que_devolve():
    """Um modelo so chama o que entende que existe.

    A descricao dizia apenas "placa, status e leituras atuais"; nada de RUL,
    anomalia, alerta ou limiar. Enumerar o que vem no payload e o que faz a
    ferramenta ser escolhida para uma pergunta de metrica.
    """
    from app.modules.volt.agent import TOOLS

    descricao = next(
        t["function"]["description"]
        for t in TOOLS
        if t["function"]["name"] == "dados_do_ativo"
    ).lower()
    for termo in ("rul", "anomalia", "alerta", "limiar", "saude"):
        assert termo in descricao, f"a descricao nao menciona {termo}"


def test_prompt_manda_consultar_antes_de_dizer_que_nao_tem():
    """A instrucao que produzia o "nao tenho acesso" tinha que sair.

    "se nao tiver o dado, diga o que sabe em termos gerais" virava recusa. O
    prompt agora exige chamar a ferramenta ANTES de negar.
    """
    from app.modules.volt.agent import AGENT_SYSTEM_PROMPT

    prompt = AGENT_SYSTEM_PROMPT.lower()
    assert "antes de responder" in prompt
    assert "sem ter chamado a ferramenta" in prompt
