"""Testes do modulo de ativos (CRUD de ativos, plantas e areas)."""


async def test_create_and_get_asset(client):
    payload = {"tag": "MTR-TEST", "name": "Motor de teste", "manufacturer": "WEG"}
    create = await client.post("/api/v1/assets", json=payload)
    assert create.status_code == 201
    assert create.json()["tag"] == "MTR-TEST"

    fetched = await client.get("/api/v1/assets/MTR-TEST")
    assert fetched.status_code == 200
    assert fetched.json()["manufacturer"] == "WEG"


async def test_list_assets(client):
    await client.post("/api/v1/assets", json={"tag": "MTR-A"})
    await client.post("/api/v1/assets", json={"tag": "MTR-B"})
    response = await client.get("/api/v1/assets")
    assert response.status_code == 200
    tags = {asset["tag"] for asset in response.json()}
    assert {"MTR-A", "MTR-B"}.issubset(tags)


async def test_duplicate_asset_returns_conflict(client):
    await client.post("/api/v1/assets", json={"tag": "MTR-DUP"})
    duplicate = await client.post("/api/v1/assets", json={"tag": "MTR-DUP"})
    assert duplicate.status_code == 409


async def test_get_missing_asset_returns_404(client):
    response = await client.get("/api/v1/assets/NAO-EXISTE")
    assert response.status_code == 404


async def test_update_asset(client):
    await client.post("/api/v1/assets", json={"tag": "MTR-UPD"})
    response = await client.patch("/api/v1/assets/MTR-UPD", json={"status": "ok", "power_kw": 7.5})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["power_kw"] == 7.5


async def test_delete_asset(client):
    await client.post("/api/v1/assets", json={"tag": "MTR-DEL"})
    deleted = await client.delete("/api/v1/assets/MTR-DEL")
    assert deleted.status_code == 204
    missing = await client.get("/api/v1/assets/MTR-DEL")
    assert missing.status_code == 404


async def test_create_asset_requires_tag(client):
    response = await client.post("/api/v1/assets", json={"name": "Sem tag"})
    assert response.status_code == 422


async def test_create_plant_and_area(client):
    plant = await client.post("/api/v1/plants", json={"name": "Planta Teste", "code": "PLANT-T"})
    assert plant.status_code == 201
    plant_id = plant.json()["id"]

    area = await client.post(
        "/api/v1/areas",
        json={"plant_id": plant_id, "name": "Area Teste", "code": "AREA-T"},
    )
    assert area.status_code == 201
    assert area.json()["plant_id"] == plant_id


async def test_create_area_with_invalid_plant_returns_404(client):
    response = await client.post(
        "/api/v1/areas",
        json={
            "plant_id": "00000000-0000-0000-0000-000000000000",
            "name": "Area Orfa",
            "code": "AREA-X",
        },
    )
    assert response.status_code == 404
