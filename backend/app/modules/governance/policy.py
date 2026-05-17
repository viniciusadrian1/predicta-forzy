"""Catalogo de dados e politica de acesso (governanca - Sprint 4).

Estrutura, de forma legivel por maquina, a classificacao de dados
(``docs/governance/data-classification.md``) e a matriz RBAC
(``docs/governance/access-control.md``), expostas pela API de governanca.
"""

from __future__ import annotations

from app.core.rbac import ROLE_HIERARCHY
from app.modules.governance.schemas import AccessRule, DataAssetEntry

CLASSIFICATION_LEVELS: list[str] = ["operacional", "pessoal", "sensivel"]
ROLES: list[str] = list(ROLE_HIERARCHY.keys())

# Inventario de dados - espelha docs/governance/data-classification.md.
DATA_INVENTORY: list[DataAssetEntry] = [
    DataAssetEntry(
        dataset="telemetry_raw",
        origin="Simulador / gateway OPC-UA",
        classification="operacional",
        storage="TimescaleDB",
        retention="30 dias",
        notes="Tensao, corrente, temperatura, rotacao e vibracao brutas.",
    ),
    DataAssetEntry(
        dataset="telemetry_processed",
        origin="Pipeline de processamento",
        classification="operacional",
        storage="TimescaleDB",
        retention="1 ano",
        notes="Telemetria validada e normalizada.",
    ),
    DataAssetEntry(
        dataset="assets / plants / areas",
        origin="Cadastro manual e OCR de placas",
        classification="operacional",
        storage="PostgreSQL",
        retention="Enquanto o ativo existir",
        notes="Metadados de equipamentos e da planta.",
    ),
    DataAssetEntry(
        dataset="nameplate_images",
        origin="Upload do usuario (OCR)",
        classification="operacional",
        storage="Transitorio (nao persistido)",
        retention="Descartado apos a extracao",
        notes="Pode conter o numero de serie do ativo.",
    ),
    DataAssetEntry(
        dataset="audit_log",
        origin="Middleware de auditoria",
        classification="pessoal",
        storage="PostgreSQL",
        retention="1 ano (politica de expurgo a definir)",
        notes="Contem o usuario (actor) e o endereco IP - dado pessoal (LGPD).",
    ),
    DataAssetEntry(
        dataset="users",
        origin="Cadastro de usuarios",
        classification="sensivel",
        storage="PostgreSQL",
        retention="Enquanto a conta existir",
        notes="Senha protegida por hashing argon2; nunca exposta pela API.",
    ),
    DataAssetEntry(
        dataset="jwt_tokens",
        origin="Autenticacao",
        classification="sensivel",
        storage="Nao persistido",
        retention="Expiracao curta (15 min)",
        notes="Assinados com JWT_SECRET_KEY.",
    ),
    DataAssetEntry(
        dataset="llm_api_keys",
        origin="Configuracao de ambiente",
        classification="sensivel",
        storage="Variavel de ambiente",
        retention="Gerenciada fora do repositorio",
        notes="Nunca versionar; .env esta no .gitignore.",
    ),
    DataAssetEntry(
        dataset="rag_knowledge_base",
        origin="Documentacao tecnica curada",
        classification="operacional",
        storage="Indice vetorial (memoria ou ChromaDB)",
        retention="Reindexado sob demanda",
        notes="Manuais e guias tecnicos; sem dado pessoal.",
    ),
]

# Matriz RBAC - espelha docs/governance/access-control.md.
ACCESS_RULES: list[AccessRule] = [
    AccessRule(
        resource="/auth/login",
        methods=["POST"],
        min_role="viewer",
        description="Autenticacao - endpoint publico.",
    ),
    AccessRule(
        resource="/assets, /plants, /telemetry, /alerts (consulta)",
        methods=["GET"],
        min_role="viewer",
        description="Consulta de catalogo, telemetria e alertas.",
    ),
    AccessRule(
        resource="/assets (cadastro)",
        methods=["POST"],
        min_role="operator",
        description="Cadastro de ativos.",
    ),
    AccessRule(
        resource="/alerts/{id}/ack",
        methods=["POST"],
        min_role="operator",
        description="Reconhecimento (ack) de alertas.",
    ),
    AccessRule(
        resource="/vision/extract-from-image, /automation/register-from-image",
        methods=["POST"],
        min_role="operator",
        description="OCR de placas e cadastro automatizado (RPA).",
    ),
    AccessRule(
        resource="/ml (predicao e RUL)",
        methods=["GET", "POST"],
        min_role="viewer",
        description="Predicoes de baseline, anomalia e RUL.",
    ),
    AccessRule(
        resource="/ml/train",
        methods=["POST"],
        min_role="engineer",
        description="Retreino dos modelos de ML.",
    ),
    AccessRule(
        resource="/rag/chat",
        methods=["POST"],
        min_role="viewer",
        description="Chat de troubleshooting com RAG.",
    ),
    AccessRule(
        resource="/rag/ingest",
        methods=["POST"],
        min_role="engineer",
        description="Reindexacao da base de conhecimento.",
    ),
    AccessRule(
        resource="/governance/access-policy",
        methods=["GET"],
        min_role="viewer",
        description="Consulta da propria matriz de acesso.",
    ),
    AccessRule(
        resource="/governance/data-lineage",
        methods=["GET"],
        min_role="engineer",
        description="Catalogo de dados classificado.",
    ),
    AccessRule(
        resource="/audit",
        methods=["GET"],
        min_role="admin",
        description="Trilha de auditoria do sistema.",
    ),
    AccessRule(
        resource="/users",
        methods=["GET"],
        min_role="admin",
        description="Gestao de contas de usuario.",
    ),
]
