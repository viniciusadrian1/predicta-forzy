"""Testes do aviso de plantao no Telegram e do enganche no handoff do Volt.

O que se quer travar aqui: escalada que NAO avisa ninguem e pior que nao ter
aviso nenhum, porque a tela promete ao tecnico que alguem foi chamado.
"""

import json

import httpx
import pytest

from app.core import notify
from app.core.config import get_settings
from app.core.notify import enviar_telegram
from app.core.security import create_access_token


# A classe real, guardada ANTES de qualquer monkeypatch: a fabrica abaixo
# substitui httpx.AsyncClient no modulo, entao chamar httpx.AsyncClient dentro
# dela chamaria a propria fabrica, de novo e de novo.
_ASYNC_CLIENT_REAL = httpx.AsyncClient


def _telegram_falso(capturado: list, status: int = 200):
    """Fabrica de AsyncClient que responde no lugar da API do Telegram."""

    async def responder(request: httpx.Request) -> httpx.Response:
        capturado.append({"url": str(request.url), "corpo": json.loads(request.content)})
        return httpx.Response(status, json={"ok": status == 200})

    def fabricar(*_args, **_kwargs):
        return _ASYNC_CLIENT_REAL(transport=httpx.MockTransport(responder))

    return fabricar


@pytest.fixture
def telegram_configurado(monkeypatch):
    """Token e chat definidos, com o cache de settings limpo dos dois lados."""
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:FAKE-TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1001234567890")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def telegram_desligado(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_sem_token_nao_chama_a_rede(telegram_desligado, monkeypatch):
    """Recurso opcional: sem configurar, nem tenta sair - e nao quebra nada."""
    capturado: list = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _telegram_falso(capturado))
    assert await enviar_telegram("oi") is False
    assert capturado == []


async def test_envia_no_formato_que_o_telegram_espera(telegram_configurado, monkeypatch):
    capturado: list = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _telegram_falso(capturado))

    assert await enviar_telegram("motor parado") is True
    assert len(capturado) == 1
    assert capturado[0]["url"] == "https://api.telegram.org/bot123456:FAKE-TOKEN/sendMessage"
    assert capturado[0]["corpo"]["chat_id"] == "-1001234567890"
    assert capturado[0]["corpo"]["text"] == "motor parado"


async def test_recusa_do_telegram_nao_levanta(telegram_configurado, monkeypatch):
    """chat_id errado devolve 400; o atendimento nao pode cair por causa disso."""
    capturado: list = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _telegram_falso(capturado, status=400))
    assert await enviar_telegram("oi") is False


async def test_rede_fora_nao_levanta(telegram_configurado, monkeypatch):
    def explodir(*_args, **_kwargs):
        raise httpx.ConnectError("sem rede")

    monkeypatch.setattr(notify.httpx, "AsyncClient", explodir)
    assert await enviar_telegram("oi") is False


# --------------------- Enganche no handoff do Volt ---------------------


async def test_handoff_avisa_o_plantao(client, telegram_configurado, monkeypatch):
    """Escalada real, pela rota HTTP: a mensagem sai com o ativo e o motivo."""
    capturado: list = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _telegram_falso(capturado))
    cabecalho = {"Authorization": f"Bearer {create_access_token('operador', 'operator')}"}

    r1 = await client.post(
        "/api/v1/volt/message",
        json={"message": "MTR-9999", "state": {}},
        headers=cabecalho,
    )
    corpo1 = r1.json()
    # 1a tentativa so pede conferencia: ninguem deve ser incomodado ainda.
    assert corpo1["handoff"] is None
    assert capturado == []

    r2 = await client.post(
        "/api/v1/volt/message",
        json={"message": "MTR-9999", "state": corpo1["state"]},
        headers=cabecalho,
    )
    assert r2.json()["handoff"] is not None
    assert len(capturado) == 1
    texto = capturado[0]["corpo"]["text"]
    assert "MTR-9999" in texto
    assert "encaminhou" in texto.lower()


async def test_turno_normal_nao_avisa(client, telegram_configurado, monkeypatch):
    """Sem escalada, o plantao fica em paz."""
    capturado: list = []
    monkeypatch.setattr(notify.httpx, "AsyncClient", _telegram_falso(capturado))

    resposta = await client.post(
        "/api/v1/volt/message", json={"message": "MTR-9999", "state": {}}
    )
    assert resposta.json()["handoff"] is None
    assert capturado == []


def test_texto_do_handoff_escapa_o_que_o_tecnico_digitou():
    """O sintoma vem do teclado do tecnico e o Telegram interpreta HTML."""
    from app.modules.volt.schemas import HandoffSummary
    from app.modules.volt.service import _texto_do_handoff

    texto = _texto_do_handoff(
        HandoffSummary(
            asset_tag="MTR-001",
            asset_name="Motor da bancada",
            symptom="barulho <estranho> & vibracao",
            diagnosis="rolamento",
            confidence=0.42,
            actions_taken="Nenhuma ordem de servico aberta.",
            reason="Confianca baixa.",
        )
    )
    assert "&lt;estranho&gt;" in texto
    assert "<estranho>" not in texto
    assert "MTR-001 - Motor da bancada" in texto
    assert "(42%)" in texto
