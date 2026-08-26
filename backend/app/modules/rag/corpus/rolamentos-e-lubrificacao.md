# Rolamentos e Lubrificacao - Guia Detalhado

Aprofunda o tema dos rolamentos, principal origem de falha mecanica em
motores de inducao. Complementa o "Plano de Manutencao" e o
"Troubleshooting - Falhas Comuns".

## Por que o rolamento e critico

A maioria das falhas mecanicas de motores comeca no rolamento. A degradacao
costuma ser gradual e **detectavel com antecedencia** pela vibracao - por
isso e o alvo principal da manutencao preditiva.

## Lubrificacao correta

- Usar o **tipo de graxa** especificado pelo fabricante (em geral base de
  litio ou poliureia). **Nao misturar** graxas de bases incompativeis - a
  mistura pode liquefazer e perder a capacidade de lubrificar.
- Respeitar **intervalo e quantidade** de relubrificacao da tabela do
  fabricante (variam com o tamanho do rolamento, a rotacao e a temperatura).
- **Excesso de graxa e tao nocivo quanto a falta**: superlotar o mancal eleva
  a temperatura por atrito interno da graxa. Aplicar a quantidade correta,
  com o motor girando quando o desenho permitir.
- Rolamentos **blindados/vedados (2Z/2RS)** ja vem lubrificados para a vida
  util e nao sao relubrificaveis - substituir ao fim da vida.

## Assinatura de vibracao das falhas de rolamento

Defeitos localizados nas pistas/esferas geram impactos periodicos em
**frequencias caracteristicas**, visiveis sobretudo na **aceleracao RMS** e
na analise de envelope:

| Sigla | Defeito associado |
|---|---|
| BPFO | pista externa (outer race) |
| BPFI | pista interna (inner race) |
| BSF | esfera / elemento rolante |
| FTF | gaiola (cage / fundamental train) |

Um **aumento da aceleracao RMS sem aumento proporcional da velocidade RMS** e
um forte indicio de rolamento no inicio de degradacao (defeito de alta
frequencia). A velocidade RMS sobe mais tarde, quando a folga ja avancou.

## Estagios da degradacao

1. **Incipiente**: micro-defeito; energia so em altas frequencias (envelope).
2. **Intermediario**: aceleracao RMS sobe de forma consistente; ruido audivel.
3. **Avancado**: velocidade RMS cresce, temperatura do mancal sobe, folga
   aumenta - risco de travamento. Trocar antes de a vibracao atingir 7,1 mm/s.

## Correntes de rolamento (motores com inversor/VFD)

Motores alimentados por **inversor** podem sofrer **correntes de eixo**:
descargas eletricas que passam pelo rolamento e marcam as pistas (fluting),
acelerando a falha. Mitigacoes usuais:

- **Rolamento isolado** no lado oposto ao acionamento.
- **Anel de aterramento de eixo** (shaft grounding ring).
- Cabo e aterramento adequados entre motor e inversor.

## Boas praticas de troca

- Usar ferramenta de extracao/montagem adequada; nunca golpear o rolamento.
- Aquecer o rolamento (indutor) para montagem por interferencia, sem exceder
  a temperatura recomendada.
- Registrar na ordem de servico a leitura de vibracao **antes e depois** da
  troca - isso realimenta os modelos preditivos do Predicta.
