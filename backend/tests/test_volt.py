"""Testes do chatbot de manutencao Volt (fluxo, NLU e diagnostico)."""

from datetime import UTC, datetime

from sqlalchemy import insert

from app.core.security import create_access_token
from app.infra.db.timescale import telemetry_processed
from app.modules.volt.diagnosis import diagnose
from app.modules.volt.nlu import detect_symptom, extract_asset_code, is_question, wants_human

# --------------------------- NLU (unidade) ---------------------------


def test_extract_asset_code_normaliza():
    assert extract_asset_code("o ativo e MTR-2291") == "MTR-2291"
    assert extract_asset_code("mtr 2291 esta ruim") == "MTR-2291"
    assert extract_asset_code("bmb001") == "BMB-001"
    assert extract_asset_code("sem codigo aqui") is None


def test_detect_symptom():
    assert detect_symptom("esta vibrando bastante") == "vibracao"
    assert detect_symptom("faz um barulho estranho") == "ruido"
    assert detect_symptom("o motor esta muito quente") == "temperatura"
    assert detect_symptom("nao sei") is None


def test_wants_human():
    assert wants_human("quero falar com uma pessoa")
    assert wants_human("me transfere pro suporte")
    assert not wants_human("MTR-2291")


def test_is_question():
    assert is_question("como faço a manutenção do rolamento?")
    assert is_question("qual o procedimento de manutenção preventiva")
    assert not is_question("MTR-2291")
    assert not is_question("esta vibrando")


# ------------------------ Diagnostico (unidade) ------------------------


def test_diagnose_rolamento_por_aceleracao():
    dx = diagnose("vibracao", {"Vibracao_Velocidade_RMS": 6.0, "Vibracao_Aceleracao_RMS": 2.0})
    assert "rolamento" in dx.fault.lower()
    assert dx.confidence >= 0.7


def test_diagnose_sobreaquecimento():
    dx = diagnose("temperatura", {"Temperatura": 98.0, "Corrente": 34.0})
    assert "sobreaquec" in dx.fault.lower()
    assert dx.confidence >= 0.5


def test_diagnose_sem_dados_confianca_baixa():
    dx = diagnose("vibracao", {})
    assert dx.confidence < 0.5  # forca handoff


# --------------------------- Fluxo (API) ----------------------------


async def _seed_high_vibration(sessionmaker, tag: str) -> None:
    now = datetime.now(UTC)
    values = {
        "Vibracao_Velocidade_RMS": 8.2,
        "Vibracao_Aceleracao_RMS": 2.1,
        "Temperatura": 70.0,
        "Corrente": 24.0,
    }
    async with sessionmaker() as session:
        for variable, value in values.items():
            await session.execute(
                insert(telemetry_processed).values(
                    time=now, asset_tag=tag, variable=variable, value=value, unit="x", quality=0
                )
            )
        await session.commit()


async def _create_asset(client, tag: str) -> None:
    resp = await client.post("/api/v1/assets", json={"tag": tag, "name": f"Motor {tag}"})
    assert resp.status_code == 201


async def test_greeting(client):
    resp = await client.get("/api/v1/volt/greeting")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"]["step"] == "aguardando_ativo"
    assert "Volt" in body["message"]


async def test_happy_path_abre_ordem_de_servico(client, timeseries_sessionmaker):
    await _create_asset(client, "MTR-2291")
    await _seed_high_vibration(timeseries_sessionmaker, "MTR-2291")

    # 1. informa o ativo
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-2291", "state": {}})
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["state"]["step"] == "aguardando_sintoma"
    assert b1["state"]["asset_tag"] == "MTR-2291"

    # 2. relata o sintoma -> diagnostico + OS
    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "esta vibrando muito e com ruido", "state": b1["state"]},
    )
    b2 = r2.json()
    assert b2["done"] is True
    assert b2["work_order"] is not None
    assert b2["work_order"]["number"] == "MTR-2291-OS001"
    assert b2["diagnosis"]["confidence"] >= 0.5
    assert "ordem de serviço" in b2["message"].lower()

    # a OS foi persistida de verdade
    orders = await client.get("/api/v1/volt/work-orders?tag=MTR-2291")
    assert orders.status_code == 200
    assert any(o["number"] == "MTR-2291-OS001" for o in orders.json())


async def test_ativo_inexistente_e_handoff(client):
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-9999", "state": {}})
    b1 = r1.json()
    assert b1["handoff"] is None  # 1a tentativa: pede conferencia
    assert "MTR-9999" in b1["message"]

    r2 = await client.post(
        "/api/v1/volt/message", json={"message": "MTR-9999", "state": b1["state"]}
    )
    b2 = r2.json()
    assert b2["handoff"] is not None  # 2a tentativa: handoff
    assert b2["handoff"]["actions_taken"].startswith("Nenhuma")


async def test_baixa_confianca_faz_handoff(client, timeseries_sessionmaker):
    await _create_asset(client, "MTR-3000")
    # sem telemetria -> confianca baixa -> handoff
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-3000", "state": {}})
    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "acho que esta vibrando", "state": r1.json()["state"]},
    )
    b2 = r2.json()
    assert b2["work_order"] is None
    assert b2["handoff"] is not None


async def test_ativo_critico_sempre_handoff(client, timeseries_sessionmaker):
    # MTR-001 e critico por padrao (volt_critical_asset_tags)
    await _create_asset(client, "MTR-001")
    await _seed_high_vibration(timeseries_sessionmaker, "MTR-001")
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-001", "state": {}})
    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "vibrando muito", "state": r1.json()["state"]},
    )
    b2 = r2.json()
    assert b2["work_order"] is None
    assert b2["handoff"] is not None
    assert "crítico" in b2["handoff"]["reason"].lower()


async def test_pergunta_tecnica_consulta_base(client):
    # Assistente unificado: uma duvida tecnica e respondida pela base de manuais,
    # sem tentar identificar um ativo (o fluxo guiado nao avanca).
    r = await client.post(
        "/api/v1/volt/message",
        json={"message": "qual o procedimento de manutenção preventiva?", "state": {}},
    )
    assert r.status_code == 200
    b = r.json()
    assert b["state"]["step"] == "aguardando_ativo"
    assert b["work_order"] is None and b["handoff"] is None
    assert b["message"].strip()
    # nao caiu no ramo de "codigo nao identificado"
    assert "informe o código do ativo" not in b["message"].lower()


async def test_pergunta_tecnica_preserva_fluxo(client):
    # Perguntar no meio do atendimento responde a duvida e mantem o passo do fluxo.
    await _create_asset(client, "MTR-2100")
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-2100", "state": {}})
    state = r1.json()["state"]
    assert state["step"] == "aguardando_sintoma"

    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "o que causa desgaste de rolamento?", "state": state},
    )
    b2 = r2.json()
    assert b2["state"]["step"] == "aguardando_sintoma"
    assert b2["state"]["asset_tag"] == "MTR-2100"
    assert b2["work_order"] is None and b2["handoff"] is None
    assert b2["message"].strip()


async def test_pergunta_com_numero_vai_para_a_base(client):
    # Regressao: o regex de codigo de ativo capturava numeros de frases
    # ("operar com 30 A" -> COM-30) e derrubava o roteamento aos manuais.
    r = await client.post(
        "/api/v1/volt/message",
        json={"message": "de quanto em quanto tempo posso operar com 30 A?", "state": {}},
    )
    b = r.json()
    assert b["state"]["step"] == "aguardando_ativo"
    assert b["work_order"] is None and b["handoff"] is None
    assert "informe o código do ativo" not in b["message"].lower()


async def test_codigo_puro_com_pontuacao_entra_no_fluxo(client):
    # "MTR-7000?" e essencialmente so o codigo: deve entrar no fluxo guiado.
    await _create_asset(client, "MTR-7000")
    r = await client.post("/api/v1/volt/message", json={"message": "MTR-7000?", "state": {}})
    b = r.json()
    assert b["state"]["step"] == "aguardando_sintoma"
    assert b["state"]["asset_tag"] == "MTR-7000"


async def test_abertura_de_os_exige_operator_com_rbac(client, monkeypatch, timeseries_sessionmaker):
    # Com RBAC ativo, abrir uma OS (escrita) exige operator+; viewer so diagnostica.
    monkeypatch.setattr("app.modules.volt.service.rbac_enforced", lambda: True)
    op = {"Authorization": f"Bearer {create_access_token('operador', 'operator')}"}
    await _create_asset(client, "MTR-8000")
    await _seed_high_vibration(timeseries_sessionmaker, "MTR-8000")

    # viewer (sem token): diagnostica mas nao abre OS -> handoff
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-8000", "state": {}})
    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "vibrando muito", "state": r1.json()["state"]},
    )
    b2 = r2.json()
    assert b2["work_order"] is None
    assert b2["handoff"] is not None
    assert "operador" in b2["handoff"]["reason"].lower()

    # operador: abre a OS normalmente
    r3 = await client.post(
        "/api/v1/volt/message", json={"message": "MTR-8000", "state": {}}, headers=op
    )
    r4 = await client.post(
        "/api/v1/volt/message",
        json={"message": "vibrando muito", "state": r3.json()["state"]},
        headers=op,
    )
    assert r4.json()["work_order"] is not None


async def test_pedido_explicito_de_humano(client):
    await _create_asset(client, "MTR-2000")
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-2000", "state": {}})
    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "quero falar com uma pessoa", "state": r1.json()["state"]},
    )
    b2 = r2.json()
    assert b2["handoff"] is not None
    assert "solicitação" in b2["handoff"]["reason"].lower()
