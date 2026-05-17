"""Testes do modulo de alertas."""

from app.modules.alerts.evaluator import AlertsEvaluator
from app.modules.alerts.models import Alert


def test_threshold_rules_detect_critical_vibration():
    rules = AlertsEvaluator()._threshold_rules({"Vibracao_Velocidade_RMS": 8.0})
    assert any(severity == "CRITICAL" for severity, *_ in rules)


def test_threshold_rules_no_alert_when_normal():
    rules = AlertsEvaluator()._threshold_rules(
        {"Vibracao_Velocidade_RMS": 1.6, "Temperatura": 55.0}
    )
    assert rules == []


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
