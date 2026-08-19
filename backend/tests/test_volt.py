"""Testes do chatbot de manutencao Volt (fluxo, NLU e diagnostico)."""

from datetime import UTC, datetime

from sqlalchemy import insert

from app.infra.db.timescale import telemetry_processed
from app.modules.volt.diagnosis import diagnose
from app.modules.volt.nlu import detect_symptom, extract_asset_code, wants_human

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
    assert "ordem de servico" in b2["message"].lower()

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
    assert "critico" in b2["handoff"]["reason"].lower()


async def test_pedido_explicito_de_humano(client):
    await _create_asset(client, "MTR-2000")
    r1 = await client.post("/api/v1/volt/message", json={"message": "MTR-2000", "state": {}})
    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "quero falar com uma pessoa", "state": r1.json()["state"]},
    )
    b2 = r2.json()
    assert b2["handoff"] is not None
    assert "solicitacao" in b2["handoff"]["reason"].lower()
