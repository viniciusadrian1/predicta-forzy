"""Testes do modulo de telemetria (processamento e consulta)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import insert

from app.infra.db.timescale import telemetry_processed
from app.infra.opcua_client.client import TelemetrySample
from app.modules.telemetry.processing import process_sample
from app.modules.telemetry.stream import TelemetryBroadcaster


def _sample(variable: str, value: float) -> TelemetrySample:
    return TelemetrySample(
        asset_tag="MTR-001",
        variable=variable,
        value=value,
        timestamp=datetime.now(UTC),
        quality=0,
        source="opcua",
    )


def test_process_sample_valid_range():
    processed = process_sample(_sample("Temperatura", 60.0))
    assert processed.unit == "C"
    assert processed.quality == 0
    assert processed.value == 60.0


def test_process_sample_out_of_range_flags_quality():
    processed = process_sample(_sample("Temperatura", 999.0))
    assert processed.quality == 1


def test_process_sample_unknown_variable():
    processed = process_sample(_sample("VariavelDesconhecida", 1.0))
    assert processed.unit == ""


async def test_broadcaster_delivers_events():
    broadcaster = TelemetryBroadcaster()
    queue = broadcaster.subscribe()
    assert broadcaster.subscriber_count == 1
    await broadcaster.publish({"variable": "Temperatura", "value": 60})
    assert queue.get_nowait()["value"] == 60
    broadcaster.unsubscribe(queue)
    assert broadcaster.subscriber_count == 0


async def test_query_telemetry_empty(client):
    response = await client.get("/api/v1/telemetry", params={"tag": "MTR-001"})
    assert response.status_code == 200
    body = response.json()
    assert body["asset_tag"] == "MTR-001"
    assert body["count"] == 0


async def test_query_telemetry_with_data(client, timeseries_sessionmaker):
    now = datetime.now(UTC)
    async with timeseries_sessionmaker() as session:
        for offset in range(5):
            await session.execute(
                insert(telemetry_processed).values(
                    time=now,
                    asset_tag="MTR-001",
                    variable="Temperatura",
                    value=50.0 + offset,
                    unit="C",
                    quality=0,
                )
            )
        await session.commit()

    response = await client.get(
        "/api/v1/telemetry",
        params={
            "tag": "MTR-001",
            "variable": "Temperatura",
            "from": (now - timedelta(minutes=5)).isoformat(),
            "to": (now + timedelta(minutes=5)).isoformat(),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5
    assert body["points"][0]["variable"] == "Temperatura"


async def test_latest_telemetry(client, timeseries_sessionmaker):
    now = datetime.now(UTC)
    async with timeseries_sessionmaker() as session:
        await session.execute(
            insert(telemetry_processed).values(
                time=now,
                asset_tag="MTR-001",
                variable="Temperatura",
                value=58.0,
                unit="C",
                quality=0,
            )
        )
        await session.commit()

    response = await client.get("/api/v1/telemetry/MTR-001/latest")
    assert response.status_code == 200
    readings = response.json()["readings"]
    assert any(reading["variable"] == "Temperatura" for reading in readings)
