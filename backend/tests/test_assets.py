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


def test_rollup_status_usa_o_pior_ponto():
    """O status de um conjunto e o PIOR entre os seus pontos de medicao.

    O avaliador so mexe no status de quem tem telemetria propria; um conjunto
    (motor-bomba com dois mancais) ficaria "unknown" para sempre, e a arvore
    lateral mostraria "desligado" enquanto a tela do ativo mostrava operacional.
    """
    from app.modules.assets.models import Asset
    from app.modules.assets.service import rollup_status

    conjunto = Asset(tag="MTR-F00", asset_type="motor", status="unknown")
    mancal_ok = Asset(tag="MTR-F01", asset_type="mancal", status="ok")
    mancal_warn = Asset(tag="MTR-F02", asset_type="mancal", status="warning")
    mancal_crit = Asset(tag="MTR-F03", asset_type="mancal", status="critical")

    assert rollup_status(conjunto, [mancal_ok, mancal_ok]) == "ok"
    assert rollup_status(conjunto, [mancal_ok, mancal_warn]) == "warning"
    assert rollup_status(conjunto, [mancal_warn, mancal_crit]) == "critical"
    # Ponto sem leitura ainda nao contamina um conjunto que esta operando.
    assert rollup_status(conjunto, [mancal_ok, Asset(tag="X", status="unknown")]) == "ok"


def test_rollup_status_preserva_ativo_sem_pontos():
    """Ativo que mede a si proprio (MTR-001) mantem o status do avaliador."""
    from app.modules.assets.models import Asset
    from app.modules.assets.service import rollup_status

    simples = Asset(tag="MTR-001", asset_type="motor", status="warning")
    assert rollup_status(simples, []) == "warning"


async def test_hierarquia_reflete_status_dos_pontos(client, catalog_sessionmaker):
    """A arvore lateral mostra o conjunto com o status derivado dos mancais."""
    from app.modules.assets.models import Area, Asset, Plant

    async with catalog_sessionmaker() as session:
        plant = Plant(name="Planta Teste", code="PLANT-ROLLUP")
        session.add(plant)
        await session.flush()
        area = Area(plant_id=plant.id, name="Area Teste", code="AREA-ROLLUP")
        session.add(area)
        await session.flush()
        session.add_all(
            [
                Asset(
                    tag="CJ-001", asset_type="motor", status="unknown",
                    plant_id=plant.id, area_id=area.id,
                ),
                Asset(
                    tag="CJ-001-P1", asset_type="mancal", parent_tag="CJ-001",
                    status="warning", plant_id=plant.id, area_id=area.id,
                ),
            ]
        )
        await session.commit()

    body = (await client.get("/api/v1/hierarchy")).json()
    area_alvo = next(
        a for p in body for a in p["areas"] if a["code"] == "AREA-ROLLUP"
    )
    tags = {asset["tag"]: asset["status"] for asset in area_alvo["assets"]}
    # O ponto de medicao nao aparece na arvore; o conjunto herda o status dele.
    assert tags == {"CJ-001": "warning"}


async def test_atualizar_conjunto_nao_grava_status_derivado(client, catalog_sessionmaker):
    """Editar um conjunto nao pode persistir o status consolidado no banco.

    `get_asset` sobrescreve `status` com o rollup dos pontos; se o caminho de
    escrita usasse esse mesmo objeto, o derivado vazaria para a tabela e ficaria
    congelado quando os pontos mudassem.
    """
    from sqlalchemy import select

    from app.modules.assets.models import Asset

    async with catalog_sessionmaker() as session:
        session.add_all(
            [
                Asset(tag="CJ-W", asset_type="motor", status="unknown"),
                Asset(
                    tag="CJ-W-P1", asset_type="mancal",
                    parent_tag="CJ-W", status="critical",
                ),
            ]
        )
        await session.commit()

    # A leitura mostra o consolidado...
    assert (await client.get("/api/v1/assets/CJ-W")).json()["status"] == "critical"

    # ...mas editar outro campo nao pode gravar esse "critical" na linha do pai.
    resp = await client.patch("/api/v1/assets/CJ-W", json={"name": "Conjunto W"})
    assert resp.status_code == 200

    async with catalog_sessionmaker() as session:
        row = (
            await session.execute(select(Asset).where(Asset.tag == "CJ-W"))
        ).scalar_one()
        assert row.name == "Conjunto W"
        assert row.status == "unknown", "o status derivado vazou para o banco"
