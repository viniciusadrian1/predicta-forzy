"""Testes do modulo de alertas."""

from datetime import UTC, datetime, timedelta

from app.modules.alerts import evaluator as ev
from app.modules.alerts.evaluator import AlertsEvaluator
from app.modules.alerts.models import Alert

# Limiares globais ISO (fallback usado quando o ativo nao tem os proprios).
_TH = {"vib_warning": 4.5, "vib_critical": 7.1, "temp_warning": 95.0, "temp_critical": 105.0}


def test_threshold_critical_needs_two_consecutive():
    # 2 leituras consecutivas acima do critico -> CRITICO confirmado.
    recent = {"Vibracao_Velocidade_RMS": [{"value": 8.0}, {"value": 8.0}]}
    rules = AlertsEvaluator()._threshold_rules({"Vibracao_Velocidade_RMS": 8.0}, recent, _TH)
    assert any(severity == "CRITICAL" for severity, *_ in rules)


def test_threshold_single_reading_is_attention_not_critical():
    # Uma unica leitura acima do critico ainda nao e anomalia -> Atencao.
    recent = {"Vibracao_Velocidade_RMS": [{"value": 8.0}]}
    rules = AlertsEvaluator()._threshold_rules({"Vibracao_Velocidade_RMS": 8.0}, recent, _TH)
    assert rules and all(severity == "WARNING" for severity, *_ in rules)


def test_threshold_attention_band():
    # Valor entre warn (4.5) e crit (7.1) -> faixa de Atencao.
    recent = {"Vibracao_Velocidade_RMS": [{"value": 5.0}]}
    rules = AlertsEvaluator()._threshold_rules({"Vibracao_Velocidade_RMS": 5.0}, recent, _TH)
    assert any("Atenção" in message for _, _, message, _ in rules)


def test_threshold_rules_no_alert_when_normal():
    rules = AlertsEvaluator()._threshold_rules(
        {"Vibracao_Velocidade_RMS": 1.6, "Temperatura": 55.0}, {}, _TH
    )
    assert rules == []


def test_circuit_breaker_on_bad_quality():
    reason = AlertsEvaluator()._circuit_breaker(
        {"Vibracao_Velocidade_RMS": 5.0}, {"Vibracao_Velocidade_RMS": 1}, {}
    )
    assert reason is not None


def test_circuit_breaker_on_velocity_accel_divergence():
    reason = AlertsEvaluator()._circuit_breaker(
        {"Vibracao_Velocidade_RMS": 5.0, "Vibracao_Aceleracao_RMS": 0.0},
        {"Vibracao_Velocidade_RMS": 0},
        {},
    )
    assert reason is not None and "sensor" in reason


def test_circuit_breaker_on_gap():
    now = datetime.now(UTC)
    recent = {
        "Vibracao_Velocidade_RMS": [
            {"time": now, "value": 5.0},
            {"time": now - timedelta(seconds=300), "value": 5.0},
        ]
    }
    reason = AlertsEvaluator()._circuit_breaker({}, {}, recent)
    assert reason is not None and "comunicação" in reason


def test_circuit_breaker_clear_when_data_ok():
    reason = AlertsEvaluator()._circuit_breaker(
        {"Vibracao_Velocidade_RMS": 5.0, "Vibracao_Aceleracao_RMS": 0.5},
        {"Vibracao_Velocidade_RMS": 0},
        {},
    )
    assert reason is None


class _FakeHttpClient:
    """Cliente httpx falso que registra o POST do webhook."""

    calls: list[tuple[str, dict]] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> "_FakeHttpClient":
        return self

    async def __aexit__(self, *args) -> bool:
        return False

    async def post(self, url: str, json: dict) -> None:
        _FakeHttpClient.calls.append((url, json))


async def test_alert_webhook_notifies_when_configured(monkeypatch):
    _FakeHttpClient.calls = []
    monkeypatch.setattr(ev.httpx, "AsyncClient", _FakeHttpClient)
    monkeypatch.setattr(
        ev, "get_settings", lambda: type("S", (), {"alert_webhook_url": "http://hook"})
    )
    alert = Alert(
        asset_tag="MTR-X", severity="CRITICAL", alert_type="T", message="m", ml_score=None
    )
    await AlertsEvaluator()._notify(alert)
    assert _FakeHttpClient.calls and _FakeHttpClient.calls[0][0] == "http://hook"
    assert _FakeHttpClient.calls[0][1]["asset_tag"] == "MTR-X"


async def test_alert_webhook_noop_when_unset(monkeypatch):
    _FakeHttpClient.calls = []
    monkeypatch.setattr(ev.httpx, "AsyncClient", _FakeHttpClient)
    monkeypatch.setattr(ev, "get_settings", lambda: type("S", (), {"alert_webhook_url": ""}))
    alert = Alert(
        asset_tag="MTR-X", severity="CRITICAL", alert_type="T", message="m", ml_score=None
    )
    await AlertsEvaluator()._notify(alert)
    assert _FakeHttpClient.calls == []


async def test_list_alerts_empty(client):
    response = await client.get("/api/v1/alerts")
    assert response.status_code == 200
    assert response.json() == []


async def test_create_list_and_ack_alert(client, catalog_sessionmaker):
    async with catalog_sessionmaker() as session:
        alert = Alert(
            asset_tag="MTR-001",
            severity="WARNING",
            alert_type="THRESHOLD_EXCEEDED",
            message="Vibracao elevada de teste",
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        alert_id = str(alert.id)

    listing = await client.get("/api/v1/alerts")
    assert listing.status_code == 200
    assert len(listing.json()) >= 1

    ack = await client.post(f"/api/v1/alerts/{alert_id}/ack", json={"comment": "verificado"})
    assert ack.status_code == 200
    body = ack.json()
    assert body["acknowledged"] is True
    assert body["ack_comment"] == "verificado"


async def test_ack_missing_alert_returns_404(client):
    response = await client.post("/api/v1/alerts/00000000-0000-0000-0000-000000000000/ack", json={})
    assert response.status_code == 404


async def test_alerta_de_estado_abre_uma_vez_fecha_e_reabre(catalog_sessionmaker):
    """O ciclo de vida completo de um alerta de ESTADO.

    Antes, a dedup era so uma janela de 15 min: a condicao persistindo gerava um
    alerta novo a cada 15 min, e nada nunca fechava. Este teste trava as tres
    garantias: nao duplica enquanto aberto, fecha sozinho ao normalizar, e volta
    a abrir depois (senao o primeiro episodio silenciaria todos os seguintes).
    """
    from app.modules.alerts.repository import AlertRepository

    async with catalog_sessionmaker() as session:
        repo = AlertRepository(session)

        async def abrir() -> bool:
            """Simula um ciclo do avaliador com a condicao ligada."""
            if await repo.has_open("MTR-TESTE", "THRESHOLD_APPROACHING"):
                return False
            await repo.create(
                Alert(
                    asset_tag="MTR-TESTE",
                    severity="WARNING",
                    alert_type="THRESHOLD_APPROACHING",
                    message="Vibracao se aproximando do limite",
                )
            )
            return True

        # Ciclo 1 e 2, condicao ligada: um unico alerta, nao dois.
        assert await abrir() is True
        assert await abrir() is False

        # Ciclo 3, condicao normalizada: fecha sozinho, marcado como automatico.
        assert await repo.close_resolved("MTR-TESTE", set()) == 1
        abertos = await repo.list_alerts(asset_tag="MTR-TESTE", only_active=True)
        assert abertos == []
        todos = await repo.list_alerts(asset_tag="MTR-TESTE")
        assert todos[0].ack_by == "auto"
        assert todos[0].ack_at is not None

        # Ciclo 4, condicao volta: abre um alerta NOVO (garantia anti-mute).
        assert await abrir() is True
        assert len(await repo.list_alerts(asset_tag="MTR-TESTE")) == 2


async def test_close_resolved_nao_fecha_condicao_ainda_ativa(catalog_sessionmaker):
    """So fecha o tipo que saiu da condicao medida; o resto continua aberto."""
    from app.modules.alerts.repository import AlertRepository

    async with catalog_sessionmaker() as session:
        repo = AlertRepository(session)
        for alert_type in ("THRESHOLD_APPROACHING", "CIRCUIT_BREAKER"):
            await repo.create(
                Alert(
                    asset_tag="MTR-MISTO",
                    severity="WARNING",
                    alert_type=alert_type,
                    message=f"teste {alert_type}",
                )
            )

        # A vibracao normalizou, mas o circuit breaker segue ligado.
        assert await repo.close_resolved("MTR-MISTO", {"CIRCUIT_BREAKER"}) == 1
        abertos = await repo.list_alerts(asset_tag="MTR-MISTO", only_active=True)
        assert [a.alert_type for a in abertos] == ["CIRCUIT_BREAKER"]


async def test_consultivo_de_ml_fecha_so_quando_o_modelo_diz_normal(catalog_sessionmaker):
    """O consultivo fecha quando o modelo roda e nao acusa - e so nesse caso.

    `_ml_advisory` grava streak 0 quando o modelo roda e nao acusa, e REMOVE a
    chave quando o modelo falha. Se os dois casos fossem confundidos, uma falha
    transitoria de modelo fecharia o alerta como se tivesse normalizado.
    """
    from app.modules.alerts.repository import AlertRepository

    async with catalog_sessionmaker() as session:
        repo = AlertRepository(session)
        await repo.create(
            Alert(
                asset_tag="MTR-ML",
                severity="INFO",
                alert_type="ANOMALY_DETECTED",
                message="Consultivo: vibracao atipica",
            )
        )

        # Modelo ainda acusando (ou indisponivel): o alerta continua aberto.
        assert await repo.close_resolved("MTR-ML", {"ANOMALY_DETECTED"}) == 0
        assert len(await repo.list_alerts(asset_tag="MTR-ML", only_active=True)) == 1

        # Modelo rodou e nao acusou: fecha.
        assert await repo.close_resolved("MTR-ML", set()) == 1
        assert await repo.list_alerts(asset_tag="MTR-ML", only_active=True) == []


def test_streak_distingue_modelo_normal_de_modelo_quebrado():
    """O sinal que decide o fechamento do consultivo: 0 = normal, ausente = falhou."""
    evaluator = AlertsEvaluator()

    # Estado apos o modelo rodar e NAO acusar.
    evaluator._anomaly_streak["MTR-OK"] = 0
    assert evaluator._anomaly_streak.get("MTR-OK", -1) == 0  # -> pode fechar

    # Estado apos falha de ML (a chave e removida) e no boot do processo.
    evaluator._anomaly_streak.pop("MTR-QUEBRADO", None)
    assert evaluator._anomaly_streak.get("MTR-QUEBRADO", -1) != 0  # -> mantem aberto


async def test_historico_separa_reconhecimento_humano_do_fechamento_automatico(
    client, catalog_sessionmaker
):
    """O comentario do tecnico precisa ficar achavel depois de reconhecer.

    Antes a tela abria filtrada em "apenas ativos": ao reconhecer, o alerta
    deixava de ser ativo e o card sumia no mesmo segundo, levando junto o
    comentario. E, sem separar do fechamento automatico (ack_by="auto"), o
    punhado de reconhecimentos humanos ficava afogado em centenas de linhas.
    """
    from app.modules.alerts.models import Alert

    async with catalog_sessionmaker() as session:
        session.add_all(
            [
                Alert(
                    asset_tag="MTR-HIST", severity="WARNING",
                    alert_type="THRESHOLD_APPROACHING", message="vibracao subindo",
                ),
                Alert(
                    asset_tag="MTR-HIST", severity="INFO",
                    alert_type="ANOMALY_DETECTED", message="fechado pela maquina",
                    acknowledged=True, ack_by="auto",
                    ack_comment="Fechado automaticamente: condicao normalizada.",
                ),
            ]
        )
        await session.commit()

    aberto = [
        a for a in (await client.get("/api/v1/alerts?tag=MTR-HIST&only_active=true")).json()
    ]
    assert len(aberto) == 1
    alerta_id = aberto[0]["id"]

    ack = await client.post(
        f"/api/v1/alerts/{alerta_id}/ack", json={"comment": "Está tudo certo!"}
    )
    assert ack.status_code == 200

    # O reconhecimento humano fica no historico, com autor, hora e comentario...
    historico = (await client.get("/api/v1/alerts?acknowledged_by=humano")).json()
    meu = next(a for a in historico if a["id"] == alerta_id)
    assert meu["ack_comment"] == "Está tudo certo!"
    assert meu["ack_by"] and meu["ack_by"] != "auto"
    assert meu["ack_at"] is not None

    # ...e o fechamento automatico NAO polui esse historico.
    assert all(a["ack_by"] != "auto" for a in historico)
