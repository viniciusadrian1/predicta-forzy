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
