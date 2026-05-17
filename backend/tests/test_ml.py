"""Testes do modulo de Machine Learning."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import insert

from app.infra.db.timescale import telemetry_processed

_SENSORS = {
    "Tensao": 220.0,
    "Corrente": 20.0,
    "Temperatura": 55.0,
    "Rotacao": 1750.0,
    "Vibracao_Velocidade_RMS": 1.7,
    "Vibracao_Aceleracao_RMS": 0.22,
}


async def _seed_telemetry(sessionmaker, samples: int = 140) -> None:
    base = datetime.now(UTC) - timedelta(minutes=samples + 4)
    async with sessionmaker() as session:
        for index in range(samples):
            timestamp = base + timedelta(minutes=index)
            for variable, value in _SENSORS.items():
                await session.execute(
                    insert(telemetry_processed).values(
                        time=timestamp,
                        asset_tag="MTR-001",
                        variable=variable,
                        value=value + (index % 9) * 0.04,
                        unit="x",
                        quality=0,
                    )
                )
        await session.commit()


async def test_ml_train_and_status(client, timeseries_sessionmaker):
    await _seed_telemetry(timeseries_sessionmaker)
    response = await client.post("/api/v1/ml/train")
    assert response.status_code == 200
    assert response.json()["ready"] is True


async def test_ml_baseline_predict(client, timeseries_sessionmaker):
    await _seed_telemetry(timeseries_sessionmaker)
    response = await client.post("/api/v1/ml/baseline/predict", json={"asset_tag": "MTR-001"})
    assert response.status_code == 200
    assert response.json()["ready"] is True


async def test_ml_rul_estimate(client, timeseries_sessionmaker):
    await _seed_telemetry(timeseries_sessionmaker)
    response = await client.get("/api/v1/ml/rul/MTR-001")
    assert response.status_code == 200
    assert response.json()["ready"] is True


async def test_ml_feedback(client):
    response = await client.post(
        "/api/v1/ml/feedback",
        json={
            "asset_tag": "MTR-001",
            "model": "baseline",
            "prediction": "normal",
            "is_correct": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["recorded"] is True
