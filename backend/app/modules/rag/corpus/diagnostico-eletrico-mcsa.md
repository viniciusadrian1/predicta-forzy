# Diagnostico Eletrico e Analise da Corrente (MCSA)

Cobre as falhas de origem eletrica do motor de inducao e a analise da
assinatura de corrente (MCSA). Complementa o "Troubleshooting - Falhas
Comuns" no que diz respeito a enrolamento, alimentacao e rotor.

## Isolamento do enrolamento

- **Resistencia de isolamento** (megohmetro / megger): medir entre fases e
  fase-terra com o motor desenergizado. Valores muito baixos indicam
  umidade, contaminacao ou isolamento degradado. Regra pratica de referencia:
  no minimo ~1 MOhm por kV de tensao nominal +1, ajustada por temperatura.
- **Indice de polarizacao (IP)**: razao entre a resistencia medida em 10 min
  e em 1 min. IP baixo sugere umidade/contaminacao; IP saudavel indica
  isolamento seco e integro.
- Umidade e o inimigo comum: motores parados em ambiente umido podem precisar
  de secagem antes de reenergizar.

## Falhas de enrolamento (estator)

**Sintomas na telemetria**
- Corrente elevada e aquecimento localizado mesmo sem sobrecarga mecanica.
- Desarme recorrente da protecao.

**Causas**
- Curto entre espiras, fase-fase ou fase-terra; sobreaquecimento previo que
  carbonizou o verniz; surtos de tensao.

**Acao** - acionar a equipe eletrica. Nao reenergizar repetidamente um motor
que desarma por protecao; cada tentativa agrava o dano.

## Desequilibrio e subtensao de fases

- A tensao deve ficar em 220 V +/- 10% (198 V a 242 V) e **equilibrada** entre
  as tres fases. Um pequeno **desequilibrio de tensao** gera um desequilibrio
  de corrente varias vezes maior e aquece o motor de forma desproporcional.
- **Falta de fase (single-phasing)**: o motor perde uma fase e as duas
  restantes sobrecarregam; ruido e vibracao aumentam e a protecao deve atuar.
- Regra de manutencao: corrigir a alimentacao antes de investigar o motor -
  muitos "defeitos de motor" sao, na verdade, problemas de rede.

## MCSA - analise da assinatura de corrente

A MCSA identifica defeitos observando o **espectro da corrente** do estator,
sem parar a maquina:

| Defeito | Indicio na corrente |
|---|---|
| Barras de rotor quebradas | bandas laterais em torno da frequencia da rede, proporcionais ao escorregamento |
| Excentricidade de entreferro | componentes ligados a rotacao e as ranhuras |
| Problemas de acoplamento/carga | modulacoes na frequencia de rotacao |

No Predicta, a corrente e uma das seis variaveis monitoradas: uma corrente
media alta indica carga/sobrecarga, enquanto **oscilacoes e modulacoes**
podem apontar defeitos de rotor ou de acionamento. A confirmacao definitiva
exige instrumento de MCSA dedicado.

## Efeitos do inversor (VFD)

- Inversores introduzem harmonicas e podem elevar o aquecimento e o ruido.
- Alem das correntes de rolamento (ver "Rolamentos e Lubrificacao"), a
  operacao em baixa rotacao reduz a ventilacao propria (TEFC) e pode exigir
  ventilacao forcada para manter a temperatura sob controle.

## Resumo de decisao

Falha eletrica confirmada (isolamento baixo, desequilibrio, desarme
recorrente) e caso de **encaminhamento a equipe eletrica** - nao e resolvida
por lubrificacao ou balanceamento. A decisao e sempre humana; o assistente e
a telemetria apoiam o diagnostico.
