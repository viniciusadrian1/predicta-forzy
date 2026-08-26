"""Testes da trilha de auditoria de TAG e do hash de integridade."""

from app.modules.governance.repository import TagAuditRepository, integrity_hash


def test_integrity_hash_is_deterministic_and_sensitive():
    base = {"tag": "MTR-1", "x": 1}
    assert integrity_hash(base) == integrity_hash({"x": 1, "tag": "MTR-1"})  # ordem nao importa
    assert integrity_hash(base) != integrity_hash({"tag": "MTR-1", "x": 2})  # conteudo importa
    assert len(integrity_hash(base)) == 64  # SHA-256 hex


async def test_patch_position_records_tag_movement(client, catalog_sessionmaker):
    await client.post(
        "/api/v1/assets",
        json={"tag": "MOV-1", "name": "m", "position_x": 0.1, "position_y": 0.1},
    )
    resp = await client.patch("/api/v1/assets/MOV-1", json={"position_x": 0.5, "position_y": 0.5})
    assert resp.status_code == 200

    async with catalog_sessionmaker() as session:
        events = await TagAuditRepository(session).list_recent(10, "MOV-1")

    assert events, "nenhum evento de trilha registrado"
    event = events[0]
    assert event.action == "movimentacao"
    assert event.coords_before == {"x": 0.1, "y": 0.1}
    assert event.coords_after == {"x": 0.5, "y": 0.5}
    assert len(event.integrity_hash) == 64
