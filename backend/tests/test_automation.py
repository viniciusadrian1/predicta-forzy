"""Testes do modulo de automacao (RPA): cadastro a partir de foto da placa."""

import io

from PIL import Image


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (160, 90), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


async def test_rpa_register_returns_draft(client):
    response = await client.post(
        "/api/v1/automation/register-from-image",
        files={"file": ("placa.png", _png(), "image/png")},
        data={"tag": "MTR-RPA", "auto_create": "false"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["draft"]["tag"] == "MTR-RPA"
    assert body["created"] is False
    # Imagem sem placa legivel -> resultado honesto (sem dados fabricados).
    assert isinstance(body["fields"], list)
    assert body["ocr_engine"] in {"tesseract", "paddleocr", "indisponivel"}


async def test_rpa_auto_create(client):
    response = await client.post(
        "/api/v1/automation/register-from-image",
        files={"file": ("placa.png", _png(), "image/png")},
        data={"tag": "MTR-AUTO", "auto_create": "true"},
    )
    assert response.status_code == 200
    assert response.json()["created"] is True
    check = await client.get("/api/v1/assets/MTR-AUTO")
    assert check.status_code == 200


async def test_rpa_detects_duplicate(client):
    await client.post("/api/v1/assets", json={"tag": "MTR-DUP-RPA"})
    response = await client.post(
        "/api/v1/automation/register-from-image",
        files={"file": ("placa.png", _png(), "image/png")},
        data={"tag": "MTR-DUP-RPA", "auto_create": "true"},
    )
    assert response.status_code == 200
    assert response.json()["duplicate"] is True
