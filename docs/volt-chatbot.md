# Volt — Chatbot de Manutenção

Assistente conversacional de manutenção preditiva da Predicta, especificado no
nano-projeto FIAP (Grupo 2TIAPF). O Volt faz o **primeiro atendimento**:
identifica o ativo, coleta o sintoma, cruza com os sensores IoT e — quando o
diagnóstico é confiável — abre a ordem de serviço na hora; caso contrário,
encaminha a um técnico humano com um resumo estruturado.

## Persona

- **Nome:** Volt.
- **Tom:** direto, técnico e objetivo, como um colega de manutenção experiente.
- **Vocabulário:** termos de chão de fábrica (ativo, ordem de serviço, sensor,
  vibração); sem jargão acadêmico de estatística/ML.
- **Limite essencial (o que NUNCA faz):** nunca decide sozinho um diagnóstico de
  baixa confiança, nem executa ação física no equipamento (desligar, reiniciar,
  travar) — apenas **lê** sensores e abre/encaminha a ordem de serviço.

## O que faz / o que não faz

| Faz | Não faz |
|---|---|
| Valida o código do ativo no cadastro | Diagnóstico definitivo em ativo crítico sem revisão humana |
| Pergunta o sintoma (vibração/ruído/temperatura) | Ações físicas remotas no equipamento |
| Diagnostica cruzando sintoma + sensores | Aprovar compra de peças / orçamento |
| Abre OS com prioridade automática (confiança alta) | Atendimento fora de manutenção (RH, financeiro) |
| Encaminha a humano (ativo não encontrado / baixa confiança) | Substituir a inspeção humana em baixa confiança |

## Fluxo (happy path)

1. **Saudação** — o Volt se apresenta, diz o que faz (transparência) e pede o
   código do ativo.
2. **Ativo** — valida o código; se localizado, confirma o nome e pergunta o
   sintoma (uma pergunta por vez).
3. **Sintoma** — identifica vibração/ruído/temperatura.
4. **Diagnóstico** — lê a última telemetria e classifica a falha com um nível de
   confiança (assinaturas ISO 10816 + limites térmicos/elétricos).
5. **Decisão** — confiança ≥ 50% e ativo não-crítico → abre a OS
   (`<TAG>-OS0NN`, prioridade automática) e confirma. Senão → **handoff**.

## Guardrails

- **Somente leitura** de sensores — nenhuma ação física exposta.
- **Limiar de confiança de 50%** (`VOLT_CONFIDENCE_THRESHOLD`): abaixo dele, o
  caso é escalado a um humano.
- **Ativos críticos** (`VOLT_CRITICAL_ASSET_TAGS`) sempre exigem revisão humana,
  mesmo com alta confiança.
- **RBAC**: o operador vê o diagnóstico e a OS; as leituras brutas dos sensores
  só aparecem para engenheiro/admin.
- **Log de auditoria** de cada interação (evento `volt_interaction`: ativo,
  sintoma, decisão) e persistência da OS para rastreabilidade.

## Handoff

Transfere para um técnico quando: o ativo não é localizado após conferência; a
confiança fica abaixo de 50%; o usuário pede explicitamente uma pessoa; ou o
ativo é crítico. O atendente recebe um **resumo estruturado** — código do ativo,
sintoma, diagnóstico e confiança (quando houve consulta), e as ações já tomadas
(nenhuma OS aberta) — para o técnico não repetir nada.

## Arquitetura (mínima)

| Peça | Implementação |
|---|---|
| Canal / UI | Página `/volt` (chat guiado) na aplicação |
| NLU | Regras determinísticas (`nlu.py`): código do ativo, sintoma, pedido de humano, urgência |
| Estado / contexto | Máquina de estados no cliente, enviada a cada turno (backend stateless) |
| Motor | Híbrido: regras (validação do ativo + limiar de handoff) + diagnóstico por assinatura dos sensores (`diagnosis.py`) |
| Integrações | Cadastro de ativos, telemetria (TimescaleDB), ordens de serviço (`work_orders`) |
| NLG | Mensagens de status, diagnóstico e confirmação da OS (`service.py`) |
| Guardrails | Limiar 50%, RBAC, log de auditoria, leitura-só |
| Handoff | Equipe de manutenção, com resumo estruturado |

## API

- `GET /api/v1/volt/greeting` — saudação inicial (capacidades ditas de cara).
- `POST /api/v1/volt/message` — um turno do atendimento (`{message, state}` →
  próximo turno com `diagnosis`/`work_order`/`handoff`).
- `GET /api/v1/volt/work-orders` — ordens de serviço abertas (requer operator).
