"""Testes do controle de acesso baseado em papeis (RBAC)."""

from app.core import rbac
import pytest
from fastapi import HTTPException

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


def test_credencial_invalida_e_401_e_nao_rebaixamento_silencioso():
    """Token apresentado e invalido => 401. NUNCA rebaixar para viewer.

    O rebaixamento silencioso deixava o usuario "logado" como admin na tela e
    valendo viewer no servidor: telas de Administracao davam 403 (mensagem de
    permissao para uma sessao que na verdade morreu) e toda escrita era negada,
    sem que o cliente jamais recebesse o 401 que dispara o relogin.
    """
    with pytest.raises(HTTPException) as exc:
        resolve_principal("Bearer token-invalido")
    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Bearer"}


def test_token_expirado_tambem_e_401():
    expirado = create_access_token("admin", "admin", expires_minutes=-1)
    with pytest.raises(HTTPException) as exc:
        resolve_principal(f"Bearer {expirado}")
    assert exc.value.status_code == 401


def test_sem_credencial_continua_anonimo_e_nao_401():
    """Ausencia de credencial nao e erro: leitura publica segue funcionando."""
    assert resolve_principal(None).role == "viewer"
    assert resolve_principal("").role == "viewer"


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


def test_auditor_role_is_read_only_and_sees_audit():
    from app.core.rbac import AUDIT_ROLES, LINEAGE_ROLES

    # Auditor tem acesso de leitura a auditoria e linhagem...
    assert "auditor" in AUDIT_ROLES and "admin" in AUDIT_ROLES
    assert "viewer" not in AUDIT_ROLES
    assert "auditor" in LINEAGE_ROLES
    # ...mas nivel de escrita = viewer (nao passa em operator+).
    assert not has_required_role("auditor", "operator")
    assert not has_required_role("auditor", "admin")


async def test_auditor_cannot_write_but_can_read(client, monkeypatch):
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)
    auditor = {"Authorization": f"Bearer {create_access_token('auditor', 'auditor')}"}

    # LE dados normais (GET de catalogo e aberto a viewer+).
    assert (await client.get("/api/v1/assets", headers=auditor)).status_code == 200
    # NAO escreve (cadastro exige operator).
    denied = await client.post(
        "/api/v1/assets", json={"tag": "AUD-1", "name": "x"}, headers=auditor
    )
    assert denied.status_code == 403
    # NAO administra (gestao de usuarios exige admin).
    assert (await client.get("/api/v1/users", headers=auditor)).status_code == 403


async def test_validate_asset_requires_gestor_or_admin(client, monkeypatch):
    # Validacao de cadastro (perfil Gestor de Planta=engineer, ou Admin).
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)
    op = {"Authorization": f"Bearer {create_access_token('operador', 'operator')}"}
    gestor = {"Authorization": f"Bearer {create_access_token('gestor', 'engineer')}"}

    created = await client.post("/api/v1/assets", json={"tag": "VAL-1", "name": "x"}, headers=op)
    assert created.status_code == 201

    # Operador (Tecnico) NAO valida.
    assert (await client.post("/api/v1/assets/VAL-1/validate", headers=op)).status_code == 403

    # Gestor de Planta valida e fica registrado como responsavel.
    ok = await client.post("/api/v1/assets/VAL-1/validate", headers=gestor)
    assert ok.status_code == 200
    assert ok.json()["validated_by"] == "gestor"


async def test_asset_writes_require_role(client, monkeypatch):
    # Escritas de ativo/planta/area nao podem ser feitas por anonimo/viewer.
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)
    op = {"Authorization": f"Bearer {create_access_token('operador', 'operator')}"}
    eng = {"Authorization": f"Bearer {create_access_token('engenheiro', 'engineer')}"}

    created = await client.post("/api/v1/assets", json={"tag": "SEC-1", "name": "x"}, headers=op)
    assert created.status_code == 201

    # PATCH exige operator
    assert (await client.patch("/api/v1/assets/SEC-1", json={"name": "y"})).status_code == 403
    assert (
        await client.patch("/api/v1/assets/SEC-1", json={"name": "y"}, headers=op)
    ).status_code == 200

    # DELETE exige engineer (operator nao basta)
    assert (await client.delete("/api/v1/assets/SEC-1", headers=op)).status_code == 403
    assert (await client.delete("/api/v1/assets/SEC-1", headers=eng)).status_code == 204

    # POST /plants exige operator
    assert (
        await client.post("/api/v1/plants", json={"name": "P", "code": "P1"})
    ).status_code == 403
    assert (
        await client.post("/api/v1/plants", json={"name": "P", "code": "P1"}, headers=op)
    ).status_code == 201


async def test_auth_me_recusa_sessao_expirada(client):
    """/auth/me e como o cliente descobre que a sessao morreu: precisa dar 401.

    Enquanto ele respondia 200 {"username": "anonymous"}, o guarda de sessao do
    frontend recebia "tudo certo" e mantinha o usuario numa sessao morta -
    exibindo controles de admin que o servidor ja recusava.
    """
    expirado = create_access_token("admin", "admin", expires_minutes=-1)
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expirado}"}
    )
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


async def test_auth_me_sem_token_nao_quebra(client):
    """Sem credencial nao e erro de autenticacao: segue anonimo."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["username"] == "anonymous"


async def test_escrita_com_token_expirado_manda_relogar_e_nao_nega_permissao(client):
    """Escrita com sessao morta deve dizer 401 (relogue), nunca 403 (sem permissao).

    O 403 mentia para o usuario: ele era admin, a sessao e que havia expirado -
    e como 401 nunca chegava, o cliente nao tinha como saber que precisava
    relogar. Era esse o "fico impedido de mexer em qualquer coisa".
    """
    expirado = create_access_token("admin", "admin", expires_minutes=-1)
    resp = await client.post(
        "/api/v1/assets",
        json={"tag": "ZZZ-EXPIRADO", "asset_type": "motor"},
        headers={"Authorization": f"Bearer {expirado}"},
    )
    assert resp.status_code == 401


async def test_rotas_que_escrevem_ou_gastam_llm_recusam_anonimo(client, monkeypatch):
    """Escrita e chamada de LLM nao podem sair de requisicao sem dono.

    `require_role("viewer")` nao serviria aqui: sem credencial o principal ja e
    resolvido como viewer anonimo, entao o gate passaria batido. O que se cobra
    e IDENTIDADE. /ml/feedback gravava linha com actor='anonymous', e as rotas
    de chat consomem a chave paga do servidor num IP publico.
    """
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)

    for metodo, rota, corpo in (
        ("post", "/api/v1/ml/feedback",
         {"asset_tag": "MTR-001", "model": "anomaly", "prediction": "x", "is_correct": True}),
        ("post", "/api/v1/volt/message", {"message": "oi"}),
        ("post", "/api/v1/ml/anomaly/predict", {"asset_tag": "MTR-001"}),
    ):
        resp = await getattr(client, metodo)(rota, json=corpo)
        assert resp.status_code == 401, f"{rota} respondeu {resp.status_code} para anonimo"
        assert resp.headers.get("WWW-Authenticate") == "Bearer"


async def test_leitura_publica_continua_aberta(client, monkeypatch):
    """As telas leem sem token; proteger leitura quebraria a aplicacao.

    Trava o limite do endurecimento: so escrita e LLM foram fechados.
    """
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)

    for rota in ("/api/v1/assets", "/api/v1/alerts", "/api/v1/hierarchy"):
        assert (await client.get(rota)).status_code == 200


async def test_sessao_valida_continua_passando(client, monkeypatch):
    """O endurecimento nao pode barrar quem esta logado."""
    monkeypatch.setattr(rbac, "rbac_enforced", lambda: True)
    login = await client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin123"}
    )
    if login.status_code != 200:
        pytest.skip("usuario demo ausente neste ambiente de teste")
    token = login.json()["access_token"]
    resp = await client.post(
        "/api/v1/ml/anomaly/predict",
        json={"asset_tag": "MTR-001"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code != 401
