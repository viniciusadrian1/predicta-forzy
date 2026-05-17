# Plano de Manutencao - Motores Eletricos Industriais

## Estrategia de manutencao

O Predicta apoia a transicao de uma manutencao corretiva ou baseada em
calendario para uma manutencao **preditiva**, orientada pela condicao real
do ativo (telemetria, deteccao de anomalia e estimativa de RUL).

## Inspecoes periodicas

| Intervalo | Atividade |
|---|---|
| Diario | Conferir alertas e tendencias no painel do ativo |
| Semanal | Inspecao visual, ruido, aquecimento e limpeza externa |
| Mensal | Verificar aperto de conexoes eletricas e fixacao da base |
| Semestral | Avaliar rolamentos, alinhamento e estado do acoplamento |
| Anual | Medir resistencia de isolamento e revisar a protecao termica |

## Lubrificacao

- Seguir o intervalo e o tipo de graxa recomendados pelo fabricante.
- Nao misturar graxas de bases incompativeis.
- Excesso de graxa eleva a temperatura do mancal; aplicar a quantidade
  correta. A maioria das falhas de rolamento tem origem em lubrificacao
  inadequada.

## Alinhamento e fixacao

- O desalinhamento do acoplamento gera vibracao e sobrecarrega rolamentos.
- Verificar o alinhamento apos qualquer intervencao mecanica.
- Confirmar o torque dos parafusos da base; folga na fixacao aparece como
  vibracao com componentes em multiplos da rotacao.

## Manutencao preditiva com o gemeo digital

1. O painel do ativo mostra as 6 variaveis em tempo real e o historico.
2. Os modelos de ML sinalizam desvios do ponto de operacao normal e
   anomalias de vibracao.
3. A estimativa de RUL projeta quantos dias restam ate o limite ISO.
4. O assistente de troubleshooting (este chat) ajuda a interpretar os
   dados e a decidir a acao.

## Ordens de servico

Toda intervencao deve gerar uma ordem de servico registrando data,
responsavel, pecas trocadas e a leitura de vibracao antes e depois. Esse
historico realimenta os modelos preditivos e melhora as estimativas.

## Decisao de manutencao

A decisao final de intervencao e sempre humana. Os modelos e o assistente
oferecem apoio a decisao; nao substituem a avaliacao do tecnico responsavel.
