"""Testes das funcionalidades da Sprint 2: busca, hierarquia, PDF e CSV."""

from datetime import UTC, datetime

from sqlalchemy import insert

from app.infra.db.timescale import telemetry_processed


async def _create_plant_area_asset(client) -> str:
    plant = await client.post("/api/v1/plants", json={"name": "Planta X", "code": "PX"})
    plant_id = plant.json()["id"]
    area = await client.post(
        "/api/v1/areas", json={"plant_id": plant_id, "name": "Area X", "code": "AX"}
    )
    await client.post(
        "/api/v1/assets",
        json={
            "tag": "MTR-S2",
            "manufacturer": "WEG",
            "plant_id": plant_id,
            "area_id": area.json()["id"],
        },
    )
    return plant_id


async def test_search_assets_by_manufacturer(client):
    await client.post("/api/v1/assets", json={"tag": "MTR-X1", "manufacturer": "WEG"})
    await client.post("/api/v1/assets", json={"tag": "MTR-X2", "manufacturer": "Siemens"})
    response = await client.get("/api/v1/assets", params={"search": "weg"})
    assert response.status_code == 200
    tags = [asset["tag"] for asset in response.json()]
    assert "MTR-X1" in tags
    assert "MTR-X2" not in tags


async def test_hierarchy_endpoint(client):
    await _create_plant_area_asset(client)
    response = await client.get("/api/v1/hierarchy")
    assert response.status_code == 200
    plant = next(item for item in response.json() if item["code"] == "PX")
    assert plant["areas"][0]["assets"][0]["tag"] == "MTR-S2"


async def test_smart_pdf_generation(client):
    plant_id = await _create_plant_area_asset(client)
    response = await client.get(f"/api/v1/plants/{plant_id}/smart-pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


async def test_telemetry_csv_export(client, timeseries_sessionmaker):
    async with timeseries_sessionmaker() as session:
        await session.execute(
            insert(telemetry_processed).values(
                time=datetime.now(UTC),
                asset_tag="MTR-CSV",
                variable="Temperatura",
                value=55.0,
                unit="C",
                quality=0,
            )
        )
        await session.commit()
    response = await client.get("/api/v1/telemetry/MTR-CSV/export")
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "time,asset_tag,variable" in response.text
