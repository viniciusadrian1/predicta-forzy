# Roteiro de demonstração — Predicta

Passo a passo para demonstrar o MVP completo do **Predicta** ponta a ponta.
Duração estimada: **8–10 minutos**.

## Pré-requisitos

- Docker + Docker Compose v2.
- (Opcional) `ANTHROPIC_API_KEY` no `.env` para o chat em linguagem natural —
  sem ela, o assistente opera em modo offline extrativo.

## Passo 0 — Subir a stack

```bash
cp .env.example .env
docker compose up -d --build
docker compose ps                                    # aguardar healthchecks
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.scripts.seed
```

Acessos:

- Frontend — <http://localhost:3001>
- API (Swagger) — <http://localhost:8000/docs>

## Passo 1 — Login e RBAC

1. Abrir <http://localhost:3001> → tela de login.
2. Entrar com **`admin` / `admin123`**.
3. *Falar:* a autenticação usa JWT; as senhas ficam protegidas por hashing
   argon2; cada papel (`viewer`, `operator`, `engineer`, `admin`) tem um nível
   de acesso — a matriz está em `GET /api/v1/governance/access-policy`.

## Passo 2 — Planta interativa e ativo

1. No painel, clicar na planta → mapa interativo (`/plant/...`).
2. Clicar no marcador do **MTR-001** → página do ativo.
3. *Falar:* a navegação parte da planta baixa; o badge de cor reflete o estado
   de saúde do motor em tempo real.

## Passo 3 — Telemetria em tempo real

1. Na página do ativo, observar os **6 sensores** (tensão, corrente,
   temperatura, rotação, vibração de velocidade e de aceleração).
2. Expandir um sensor → escolher a janela (1h / 24h / 7d / 30d) → exportar CSV.

## Passo 4 — Saúde do ativo (ML)

1. Rolar até a seção **"Saúde do ativo"**: baseline, anomalia e RUL com gauge.
2. *Falar:* três modelos de ML — Isolation Forest (baseline), autoencoder
   (anomalia) e regressão da tendência de vibração (RUL até o limite ISO 10816).

## Passo 5 — Injetar falha e ver o alerta

1. Com um cliente OPC-UA (ex.: UaExpert), conectar em
   `opc.tcp://localhost:4840/forzy/server/` e escrever:
   - `Forzy/Motor/MTR-001/Control/FaultMode = "BEARING_WEAR"`
   - `Forzy/Motor/MTR-001/Control/FaultSeverity = 1.0`
2. Em ~30–60 s: a vibração cresce, surge um alerta e o badge do mapa fica
   vermelho. Conferir em **`/alerts`** e reconhecer (ack) o alerta.

## Passo 6 — Assistente de troubleshooting (RAG)

1. Abrir **`/chat`** (menu "Assistente"). Notar os indicadores: documentos e
   trechos indexados, modo do LLM.
2. Perguntar: *"O que indica desgaste de rolamento?"* → a resposta é transmitida
   token a token e cita as fontes da documentação.
3. Voltar a `/asset/MTR-001` → abrir o **widget de chat flutuante** (canto
   inferior direito) → perguntar: *"Como está a saúde deste ativo?"*.
4. *Falar:* o assistente combina a documentação técnica (RAG) com a telemetria,
   os alertas e o RUL do próprio ativo. Sem chave de LLM, responde em modo
   offline extrativo, sempre citando as fontes.

## Passo 7 — Governança

1. Swagger (<http://localhost:8000/docs>):
   - `GET /api/v1/governance/access-policy` → matriz RBAC;
   - `GET /api/v1/governance/data-lineage` → inventário de dados classificado;
   - `GET /api/v1/audit` → trilha de auditoria (restrita a `admin`).
2. *Falar:* toda escrita é auditada; os dados são classificados (operacional /
   pessoal / sensível); o RBAC protege os endpoints sensíveis.

## Encerramento

O Predicta cobre o ciclo completo de um gêmeo digital: aquisição via OPC-UA,
visualização navegável, IA para anomalia e RUL, alertas, assistente
conversacional e governança — tudo modular e implantável via Docker ou
Kubernetes.
