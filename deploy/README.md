# Deploy — Predicta

Artefatos de implantação do Predicta para dois cenários: **Docker Compose**
(nó único) e **Kubernetes** (orquestrado).

## Opção 1 — Docker Compose de produção

Stack de produção em um único host (`docker-compose.prod.yml`, na raiz do
repositório):

```bash
# 1. Definir os segredos no .env (senhas e chaves)
cp .env.example .env
#    Edite POSTGRES_PASSWORD, TIMESCALE_PASSWORD, JWT_SECRET_KEY
#    e, opcionalmente, ANTHROPIC_API_KEY.

# 2. Subir a stack de producao
docker compose -f docker-compose.prod.yml up -d --build

# 3. Migrations + seed
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
docker compose -f docker-compose.prod.yml exec backend python -m app.scripts.seed
```

Diferenças em relação ao `docker-compose.yml` de desenvolvimento:

- frontend compilado (`next build` + `next start`) via `frontend/Dockerfile.prod`;
- backend com o extra `[rag]` e `RAG_VECTOR_BACKEND=chroma` (usa o ChromaDB);
- limites de CPU/memória por serviço;
- senhas obrigatórias (sem default inseguro).

## Opção 2 — Kubernetes

Pré-requisitos: um cluster Kubernetes, `kubectl` configurado e um Ingress
Controller (ex.: `ingress-nginx`).

```bash
# Build das imagens + deploy completo
./deploy/deploy.sh all

# Ou em etapas
./deploy/deploy.sh build
./deploy/deploy.sh deploy
```

O script aplica os manifests de `deploy/k8s/` na ordem correta:

1. `namespace.yaml` — namespace, ConfigMap e Secret;
2. `databases.yaml` — PostgreSQL, TimescaleDB, Redis, ChromaDB, simulador OPC-UA;
3. `backend.yaml` — Job de migração/seed + Deployment do backend (2 réplicas);
4. `frontend.yaml` — Deployment do frontend (2 réplicas);
5. `ingress.yaml` — Ingress (`predicta.local`).

### Segredos

O `namespace.yaml` traz um `Secret` com **valores de exemplo**. Em produção:

- **nunca** versione segredos reais;
- gere o `JWT_SECRET_KEY` com `openssl rand -hex 32`;
- use um cofre de segredos — Sealed Secrets, External Secrets Operator ou Vault.

### Acesso

Aponte `predicta.local` para o IP do Ingress Controller (DNS ou `/etc/hosts`)
e acesse `http://predicta.local`. A API fica sob `http://predicta.local/api`.

## Variáveis úteis

| Variável | Padrão | Descrição |
|---|---|---|
| `VERSION` | `0.4.0` | Tag das imagens |
| `REGISTRY` | `predicta` | Prefixo do registry das imagens |
| `PUBLIC_API_URL` | `http://predicta.local` | URL pública da API (embutida no frontend) |
