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


async def test_per_asset_training_with_partial_sensors(client, timeseries_sessionmaker):
    # Motor fisico (MTR-F01) so tem vibracao + temperatura, nao os 6 sensores.
    # O modelo por ativo deve treinar com o que o ativo REALMENTE tem.
    from app.modules.ml.service import ml_service

    ml_service._bundles.pop("MTR-F01", None)
    now = datetime.now(UTC)
    async with timeseries_sessionmaker() as session:
        for index in range(140):
            timestamp = now - timedelta(minutes=140 - index)
            for variable, value in (
                ("Vibracao_Velocidade_RMS", 2.0 + (index % 9) * 0.03),
                ("Vibracao_Aceleracao_RMS", 0.30),
                ("Temperatura", 40.0),
            ):
                await session.execute(
                    insert(telemetry_processed).values(
                        time=timestamp,
                        asset_tag="MTR-F01",
                        variable=variable,
                        value=value,
                        unit="x",
                        quality=0,
                    )
                )
        await session.commit()

    response = await client.post("/api/v1/ml/baseline/predict", json={"asset_tag": "MTR-F01"})
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["available"] is True  # treinou e preve mesmo sem os 6 sensores

    # O modelo do F01 usa somente as features que o ativo possui.
    assert ml_service._bundles["MTR-F01"].features == (
        "Temperatura",
        "Vibracao_Velocidade_RMS",
        "Vibracao_Aceleracao_RMS",
    )


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

    # O feedback agora e persistido (nao so logado) e pode ser listado.
    listed = await client.get("/api/v1/ml/feedback?asset_tag=MTR-001")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["asset_tag"] == "MTR-001"
    assert body[0]["is_correct"] is False
