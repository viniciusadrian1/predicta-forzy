"""Testes dos endpoints de sistema: health, autenticacao e visao (OCR)."""

import io

from PIL import Image


def _png_bytes() -> bytes:
    """Gera os bytes de um PNG valido minimo."""
    buffer = io.BytesIO()
    Image.new("RGB", (160, 90), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


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


async def test_vision_extract_from_image(client):
    response = await client.post(
        "/api/v1/assets/extract-from-image",
        files={"file": ("placa.png", _png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["engine"] in {"tesseract", "paddleocr", "indisponivel"}
    assert isinstance(body["fields"], list)
    assert body["note"]  # sempre acompanha uma nota honesta
    # Jamais fabrica: o antigo stub WEG nao pode reaparecer.
    assert all(field["value"] != "W22 IR3 Premium" for field in body["fields"])


async def test_vision_rejects_invalid_image(client):
    response = await client.post(
        "/api/v1/assets/extract-from-image",
        files={"file": ("nao-imagem.txt", b"isto nao e uma imagem", "text/plain")},
    )
    assert response.status_code == 400
