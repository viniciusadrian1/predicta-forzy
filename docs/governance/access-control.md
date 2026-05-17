# Controle de Acesso (RBAC) — Predicta

Documento de governança da Sprint 4. Define os papéis, a matriz de acesso e a
forma de aplicação do controle de acesso baseado em papéis (RBAC).

Ver também o [ADR 0007](../adr/0007-rbac-governanca.md).

## Papéis

A hierarquia é cumulativa — cada papel herda as permissões dos inferiores:

| Papel | Nível | Descrição |
|---|---|---|
| `viewer` | 0 | Visualização de ativos, telemetria, alertas e chat. |
| `operator` | 1 | Operação: cadastro de ativos, OCR, reconhecimento de alertas. |
| `engineer` | 2 | Engenharia: retreino de ML, reindexação do RAG, linhagem de dados. |
| `admin` | 3 | Administração: auditoria e gestão de usuários. |

Requisições **sem token** (ou com token inválido) são tratadas como o usuário
anônimo, com papel `viewer` (somente leitura).

## Matriz de acesso

| Recurso | Métodos | Papel mínimo |
|---|---|---|
| `/auth/login` | POST | público |
| `/assets`, `/plants`, `/telemetry`, `/alerts` (consulta) | GET | `viewer` |
| `/ml` (predição, RUL), `/rag/chat` | GET / POST | `viewer` |
| `/governance/access-policy` | GET | `viewer` |
| `/assets` (cadastro) | POST | `operator` |
| `/assets/extract-from-image`, `/automation/register-from-image` | POST | `operator` |
| `/alerts/{id}/ack` | POST | `operator` |
| `/ml/train` | POST | `engineer` |
| `/rag/ingest` | POST | `engineer` |
| `/governance/data-lineage` | GET | `engineer` |
| `/audit` | GET | `admin` |
| `/users` | GET | `admin` |

A matriz também é exposta, legível por máquina, em
`GET /api/v1/governance/access-policy`.

## Aplicação

- A verificação é feita pela dependency `require_role(min)` no *gateway* da API
  (`app/core/rbac.py`).
- Um token JWT inválido para o recurso resulta em **HTTP 403**; a tentativa é
  registrada no log estruturado (evento `rbac_denied`).
- A flag `RBAC_ENABLED` (padrão: `true`) permite desligar a verificação em
  ambientes de teste. Em produção deve permanecer ligada.

## Usuários de demonstração

O *seed* (`app/scripts/seed.py`) cria quatro contas, com senha protegida por
hashing **argon2**:

| Usuário | Senha | Papel |
|---|---|---|
| `admin` | `admin123` | `admin` |
| `engenheiro` | `eng123` | `engineer` |
| `operador` | `operador123` | `operator` |
| `viewer` | `viewer123` | `viewer` |

> As credenciais acima são apenas para a demonstração do desafio. Em produção,
> as contas devem ser criadas com senhas fortes e individuais.

## Itens em aberto

- Aplicação do RBAC à totalidade dos endpoints de escrita (hoje cobre o
  subconjunto sensível listado acima).
- *Refresh* de token com rotação e revogação.
- Expurgo automático do `audit_log` conforme a política de retenção.
