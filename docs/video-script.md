# Roteiro de vídeo — Predicta

Roteiro para o vídeo de demonstração (~5 minutos). Cada cena traz a **narração**
e a **ação em tela**.

---

## Cena 1 — O problema (0:00–0:30)

**Narração:** "A manutenção de motores industriais ainda é, em boa parte,
corretiva ou baseada em calendário. O resultado são paradas não planejadas,
estoque caro de peças e risco de falhas graves. O desafio da Forzy pede uma
forma de antecipar essas falhas."

**Tela:** título "Predicta — Digital Twin para manutenção preditiva".

## Cena 2 — A solução (0:30–1:00)

**Narração:** "O Predicta é um gêmeo digital de motores elétricos. Ele captura
telemetria em tempo real via OPC-UA, aplica IA para detectar desvios e estimar a
vida útil, e oferece um assistente de troubleshooting — tudo navegável a partir
da planta."

**Tela:** diagrama de arquitetura (`docs/architecture.md`); a stack subindo com
`docker compose up`.

## Cena 3 — Planta e telemetria (1:00–1:45)

**Narração:** "O acesso é controlado por papéis. A partir da planta baixa,
chega-se ao motor MTR-001 e às suas seis variáveis de sensor, atualizadas em
tempo real."

**Tela:** login como `admin`; planta interativa; clique no MTR-001; os seis
sensores atualizando; expansão de um gráfico.

## Cena 4 — IA e alertas (1:45–2:45)

**Narração:** "Três modelos de IA avaliam a saúde do ativo: o baseline de
operação, a detecção de anomalia de vibração e a estimativa de vida útil
remanescente. Ao injetarmos uma falha de rolamento no simulador, a vibração
cresce e, em segundos, o sistema gera um alerta — e o mapa fica vermelho."

**Tela:** seção "Saúde do ativo"; injeção da falha `BEARING_WEAR`; o alerta
surgindo em `/alerts`; reconhecimento do alerta.

## Cena 5 — Assistente de troubleshooting (2:45–3:55)

**Narração:** "Agora a novidade da Sprint 4: o assistente conversacional. Ele
usa RAG sobre os manuais técnicos e responde fundamentando-se na documentação,
sempre citando as fontes. No widget da página do ativo, ele também enxerga a
telemetria, os alertas e o RUL daquele motor — combinando o manual com os dados
reais para apoiar a decisão."

**Tela:** página `/chat`, pergunta sobre desgaste de rolamento, resposta em
streaming com as fontes; widget flutuante em `/asset/MTR-001` perguntando sobre
a saúde do ativo.

## Cena 6 — Governança (3:55–4:30)

**Narração:** "A governança fecha o MVP: controle de acesso por papéis,
usuários com senha protegida por argon2, trilha de auditoria e um catálogo de
dados classificado e exposto pela API."

**Tela:** Swagger mostrando `/governance/access-policy`, `/governance/data-lineage`
e `/audit`.

## Cena 7 — Encerramento (4:30–5:00)

**Narração:** "O Predicta entrega o ciclo completo de um gêmeo digital —
aquisição, visualização, IA, alertas, assistente e governança — modular e
pronto para implantar via Docker ou Kubernetes. Da manutenção corretiva à
manutenção preditiva."

**Tela:** visão geral do painel; logo do Predicta; "Challenge FIAP × Forzy".

---

### Notas de gravação

- Ter a stack no ar e o *seed* aplicado antes de gravar.
- Para a Cena 5 em linguagem natural, configurar `ANTHROPIC_API_KEY`; sem ela, o
  assistente responde em modo offline (também demonstrável).
- A injeção de falha da Cena 4 pode ser preparada segundos antes para o alerta
  aparecer no tempo da narração.
