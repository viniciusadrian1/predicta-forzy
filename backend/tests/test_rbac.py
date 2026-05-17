"""Testes do controle de acesso baseado em papeis (RBAC)."""

from app.core import rbac
from app.core.rbac import ROLE_HIERARCHY, has_required_role, resolve_principal
from app.core.security import create_access_token
from app.modules.governance.policy import ACCESS_RULES, CLASSIFICATION_LEVELS, DATA_INVENTORY


def test_role_hierarchy_comparisons():
    assert has_required_role("admin", "viewer")
    assert has_required_role("engineer", "operator")
    assert has_required_role("operator", "operator")
    assert not has_required_role("viewer", "operator")
    assert not has_required_role("operator", "admin")


def test_resolve_principal_without_token_is_anonymous_viewer():
    principal = resolve_principal(None)
    assert principal.username == "anonymous"
    assert principal.role == "viewer"
    assert principal.is_authenticated is False


def test_resolve_principal_from_valid_token():
    token = create_access_token("engenheiro", "engineer")
    principal = resolve_principal(f"Bearer {token}")
    assert principal.username == "engenheiro"
    assert principal.role == "engineer"
    assert principal.is_authenticated is True
    assert principal.level == 2


def test_resolve_principal_with_invalid_token_falls_back():
    principal = resolve_principal("Bearer token-invalido")
    assert principal.username == "anonymous"
    assert principal.role == "viewer"


def test_unknown_role_is_downgraded_to_viewer():
    token = create_access_token("x", "superuser")
    principal = resolve_principal(f"Bearer {token}")
    assert principal.role == "viewer"


def test_governance_policy_data_is_consistent():
    assert len(DATA_INVENTORY) >= 5
    assert len(ACCESS_RULES) >= 5
    assert all(rule.min_role in ROLE_HIERARCHY for rule in ACCESS_RULES)
    assert all(entry.classification in CLASSIFICATION_LEVELS for entry in DATA_INVENTORY)


async def test_users_endpoint_requires_admin(client, monkeypatch):
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)

    operator_token = create_access_token("operador", "operator")
    denied = await client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert denied.status_code == 403

    admin_token = create_access_token("admin", "admin")
    allowed = await client.get("/api/v1/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert allowed.status_code == 200
    assert isinstance(allowed.json(), list)


async def test_rag_ingest_requires_engineer(client, monkeypatch):
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)

    anonymous = await client.post("/api/v1/rag/ingest")
    assert anonymous.status_code == 403

    operator_token = create_access_token("operador", "operator")
    denied = await client.post(
        "/api/v1/rag/ingest", headers={"Authorization": f"Bearer {operator_token}"}
    )
    assert denied.status_code == 403

    engineer_token = create_access_token("engenheiro", "engineer")
    allowed = await client.post(
        "/api/v1/rag/ingest", headers={"Authorization": f"Bearer {engineer_token}"}
    )
    assert allowed.status_code == 200


async def test_rbac_disabled_allows_anonymous_access(client):
    # Com RBAC desligado (padrao dos testes), o endpoint admin responde 200.
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
