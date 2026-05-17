# Classificação de Dados — Forzy Digital Twin

Documento de governança da Sprint 1. Classifica cada tipo de dado tratado pela
plataforma, orientando políticas de acesso, retenção e conformidade (LGPD).

## Esquema de classificação

| Categoria | Definição |
|---|---|
| **Operacional** | Dado de processo industrial. Sem vínculo com pessoa física. |
| **Pessoal** | Dado que identifica, direta ou indiretamente, uma pessoa natural (LGPD, Art. 5º). |
| **Sensível** | Subconjunto crítico — credenciais, segredos e dados cuja exposição gera risco elevado. |

## Inventário de dados

| Dado | Origem | Categoria | Armazenamento | Observações |
|---|---|---|---|---|
| Telemetria bruta (`telemetry_raw`) | Simulador / gateway OPC-UA | Operacional | TimescaleDB | Tensão, corrente, temperatura, rotação, vibração |
| Telemetria processada (`telemetry_processed`) | Pipeline de processamento | Operacional | TimescaleDB | Dado validado e normalizado |
| Catálogo de ativos (`assets`, `plants`, `areas`) | Cadastro / OCR | Operacional | PostgreSQL | Metadados de equipamento e planta |
| Imagens de placas (OCR) | Upload do usuário | Operacional | Transitório (não persistido na Sprint 1) | Pode conter número de série do ativo |
| Log de auditoria (`audit_log`) | Middleware de auditoria | **Pessoal** | PostgreSQL | Contém `actor` (usuário) e `ip_address` |
| Credenciais de usuário | Login | **Sensível** | Em memória (mock Sprint 1) → tabela com hash argon2 (Sprint 4) | Nunca logar nem retornar |
| Tokens JWT | Autenticação | **Sensível** | Não persistido; expiração curta (15 min) | Assinados com `JWT_SECRET_KEY` |
| Chaves de API de LLM | Configuração | **Sensível** | Variável de ambiente | Nunca versionar; fora do repositório |

## Diretrizes por categoria

### Operacional
- Acesso liberado a todos os papéis autenticados (`viewer` ou superior).
- Retenção: dado bruto 30 dias; processado 1 ano (ver ADR 0002).

### Pessoal (LGPD)
- O `audit_log` registra usuário e endereço IP — **dado pessoal**.
- Base legal: legítimo interesse (segurança e rastreabilidade do sistema).
- Minimização: registrar apenas o necessário (usuário, ação, recurso, IP).
- Direitos do titular e política de retenção do `audit_log` serão detalhados
  no documento de governança final da Sprint 4.

### Sensível
- Senhas: nunca em texto plano em produção — hashing argon2 (Sprint 4).
- Segredos (`JWT_SECRET_KEY`, chaves de LLM): apenas em variáveis de ambiente,
  nunca commitados (`.env` está no `.gitignore`).
- O logging estruturado **não** deve registrar corpo de requisição de login,
  tokens ou senhas.

## Itens em aberto para a Sprint 4

- Política formal de retenção e expurgo do `audit_log`.
- Anonimização/pseudonimização de IPs após o período de retenção.
- Mapeamento completo LGPD (inventário, bases legais, encarregado).
