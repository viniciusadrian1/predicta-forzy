# ADR 0007 — RBAC e governança final

- **Status:** Aceito
- **Data:** 2026-05-17
- **Sprint:** 4

## Contexto

As Sprints 1–3 usaram um login *mock* com usuários em memória. A Sprint 4
encerra a governança: **RBAC completo**, usuários persistidos e *data lineage*.

A introdução de RBAC não pode quebrar o comportamento das sprints anteriores
nem a suíte de testes existente.

## Decisão

- **Hierarquia de papéis:** `viewer < operator < engineer < admin`. Cada papel
  herda as permissões dos inferiores.
- **Tabela de usuários:** modelo `User` (migration `0003`), senha protegida por
  hashing **argon2**. O `login` valida contra a tabela e recai sobre os usuários
  de demonstração quando ela não está populada (testes).
- **Dependency `require_role(min)`:** declara o papel mínimo de um endpoint.
  Requisições sem token são tratadas como o usuário anônimo (papel `viewer`,
  somente leitura).
- **Flag `RBAC_ENABLED`:** liga/desliga a verificação (padrão: ligada). Os
  testes a desativam por padrão e a reativam pontualmente em `test_rbac.py`.
- **Endpoints de governança:** `/governance/access-policy` expõe a matriz RBAC
  legível por máquina; `/governance/data-lineage` expõe o inventário de dados
  classificado; `/audit` (restrito a `admin`) expõe a trilha de auditoria.
- **Auditoria:** mantém-se o middleware que registra toda requisição (log JSON)
  e persiste as operações de escrita em `audit_log`.

## Consequências

- **Positivas:** autenticação real com hashing forte; princípio do menor
  privilégio aplicado no *gateway*; política de acesso e linhagem de dados
  auditáveis via API; compatível com as Sprints 1–3.
- **Negativas:** a aplicação do RBAC cobre um subconjunto **documentado** de
  endpoints sensíveis no MVP (ver `access-control.md`); não há ainda *refresh*
  de token com rotação nem federação de identidade.
- **Evolução:** *diff* before/after por campo no `audit_log`; rotação de tokens;
  integração com provedor OIDC; expurgo automático do log de auditoria.
