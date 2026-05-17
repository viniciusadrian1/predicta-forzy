# Guia de Vibracao - DIN ISO 10816 / 20816

## Objetivo

Este guia resume como interpretar a severidade de vibracao de motores
eletricos industriais a partir da velocidade RMS (mm/s), conforme a
norma DIN ISO 10816/20816.

## Zonas de severidade

A norma define quatro zonas de avaliacao para a velocidade de vibracao:

| Zona | Faixa tipica (mm/s RMS) | Interpretacao |
|---|---|---|
| A | ate 1,4 | Maquina nova ou recem-comissionada, condicao otima |
| B | 1,4 a 4,5 | Operacao aceitavel para uso continuo de longo prazo |
| C | 4,5 a 7,1 | Insatisfatorio - aceitavel apenas por periodo limitado |
| D | acima de 7,1 | Severo - risco de dano; intervir o quanto antes |

O Predicta usa 4,5 mm/s como limiar de alerta (WARNING) e 7,1 mm/s como
limiar critico (CRITICAL), coerente com a fronteira das zonas C e D.

## Como agir por zona

- **Zona A/B**: nenhuma acao especifica; manter o monitoramento de rotina.
- **Zona C**: planejar inspecao. Verificar balanceamento, alinhamento e o
  estado dos rolamentos. Acompanhar a tendencia de perto.
- **Zona D**: condicao severa. Programar parada para manutencao corretiva;
  operar nessa faixa acelera a degradacao e pode causar falha catastrofica.

## Velocidade x aceleracao

- A **velocidade RMS** correlaciona-se com desbalanceamento, desalinhamento
  e folgas - defeitos de baixa frequencia.
- A **aceleracao RMS** e mais sensivel a defeitos incipientes de rolamento
  e engrenamento - defeitos de alta frequencia. Um aumento da aceleracao
  sem aumento proporcional da velocidade costuma indicar rolamento no
  inicio de degradacao.

## Tendencia x valor absoluto

O valor absoluto situa a maquina em uma zona; a **tendencia** (taxa de
crescimento) antecipa a falha. O modulo de RUL do Predicta projeta a
tendencia de vibracao ate o limite de 7,1 mm/s para estimar a vida util
remanescente. Uma tendencia crescente e consistente exige atencao mesmo
que o valor atual ainda esteja na zona B.
