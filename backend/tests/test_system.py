"""Testes dos endpoints de sistema: health, autenticacao e visao (stub)."""


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


async def test_login_success(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["role"] == "admin"


async def test_login_invalid_credentials(client):
    response = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "errada"}
    )
    assert response.status_code == 401


async def test_vision_extract_stub(client):
    response = await client.post(
        "/api/v1/assets/extract-from-image",
        files={"file": ("placa.jpg", b"conteudo-de-imagem-falso", "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "stub"
    assert len(body["fields"]) > 0
