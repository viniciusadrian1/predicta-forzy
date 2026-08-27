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
    # Motor com so vibracao + temperatura (sem os 6 sensores). O modelo por ativo
    # deve treinar sob demanda com o que o ativo REALMENTE tem. Usa um tag SEM
    # modelo pronto no repo, para exercitar o retreino (nao o loader).
    from app.modules.ml.service import ml_service

    tag = "MTR-PARTIAL"
    ml_service._bundles.pop(tag, None)
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
                        asset_tag=tag,
                        variable=variable,
                        value=value,
                        unit="x",
                        quality=0,
                    )
                )
        await session.commit()

    response = await client.post("/api/v1/ml/baseline/predict", json={"asset_tag": tag})
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["available"] is True  # treinou e preve mesmo sem os 6 sensores

    # O modelo usa somente as features que o ativo possui.
    assert ml_service._bundles[tag].features == (
        "Temperatura",
        "Vibracao_Velocidade_RMS",
        "Vibracao_Aceleracao_RMS",
    )


def test_load_shipped_model_from_artifact():
    # O modelo PRONTO do F01 (treinado offline no dado real) carrega do repo e
    # traz um baseline usavel com as features do motor fisico. Se falhar, o
    # serving cai no retreino (fallback) - aqui garantimos o caminho feliz.
    from app.modules.ml.service import ARTIFACTS_DIR, MlService

    if not (ARTIFACTS_DIR / "MTR-F01.joblib").exists():
        return  # artefato ausente (ambiente sem modelo pronto): nada a testar
    service = MlService()
    assert service._load_shipped("MTR-F01") is True
    bundle = service._bundles["MTR-F01"]
    assert bundle.features == (
        "Temperatura",
        "Vibracao_Velocidade_RMS",
        "Vibracao_Aceleracao_RMS",
    )
    assert bundle.baseline is not None


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


async def test_ml_fault_predict_demo(client, timeseries_sessionmaker):
    # Classificador de falha (simulado) responde no ativo de demonstracao.
    await _seed_telemetry(timeseries_sessionmaker)
    response = await client.post("/api/v1/ml/fault/predict", json={"asset_tag": "MTR-001"})
    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    # Sem artefato no ambiente, available=False (fallback); com artefato, prediz.
    if body["available"]:
        assert isinstance(body["fault"], str)
        assert body["simulated"] is True


async def test_ml_fault_predict_only_demo_asset(client):
    # Nos motores reais o classificador simulado fica indisponivel de proposito.
    response = await client.post("/api/v1/ml/fault/predict", json={"asset_tag": "MTR-F01"})
    assert response.status_code == 200
    assert response.json()["available"] is False


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
