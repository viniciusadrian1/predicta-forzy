# Motor WEG W22 - Caracteristicas Tecnicas da Linha

Documento de referencia sobre a familia de motores WEG W22, base do ativo
MTR-001 (WEG W22 IR3 Premium). Complementa o "Manual de Operacao - Motor
MTR-001" com a construcao e os conceitos de projeto da linha.

## Visao geral

O W22 e uma linha de motores de inducao trifasicos, rotor de gaiola,
totalmente fechados com ventilacao externa (TEFC / IC411 - ventoinha no
proprio eixo). E projetada para uso industrial continuo, com enfase em
eficiencia energetica e baixo nivel de vibracao e ruido.

## Classes de eficiencia

A nomenclatura da WEG indica a classe de eficiencia:

| Denominacao WEG | Classe IEC equivalente | Observacao |
|---|---|---|
| W22 IR2 | IE2 (alta eficiencia) | linha de eficiencia intermediaria |
| W22 IR3 Premium | IE3 (premium) | caso do MTR-001 |
| W22 Super Premium | IE4 (super premium) | maior eficiencia da familia |

O MTR-001 e IR3 Premium (IE3): perdas menores e menor aquecimento em regime
que a geracao anterior, para a mesma potencia.

## Sistema de isolamento e classe termica

- Isolamento **classe F** (suporta ate 155 C no ponto mais quente do
  enrolamento). E comum projetar a **elevacao de temperatura em classe B**
  (ate 80 K), deixando uma margem termica que prolonga a vida do isolamento.
- A vida do isolamento cai pela metade a cada ~10 C de sobre-temperatura
  sustentada. Por isso o monitoramento termico e preventivo.
- Protecao termica embutida (conforme a opcao do motor): termistores **PTC**,
  termostatos **PTO** ou sensores **PT100** no enrolamento e/ou nos mancais.

## Dados de projeto tipicos

| Item | Referencia |
|---|---|
| Fator de servico | 1,15 (permite 15% acima da nominal em condicao normal) |
| Regime | S1 (continuo) |
| Grau de protecao | IP55 (protegido contra poeira e jatos de agua) |
| Condicao padrao | ate 1000 m de altitude e 40 C de ambiente |
| Ligacao | dupla tensao (ex.: 220/380 V) via fechamento triangulo/estrela |

Acima de 1000 m ou 40 C ha **derating** (reducao da potencia disponivel):
o ar mais rarefeito/quente refrigera menos. Consultar a placa e a tabela do
fabricante para os fatores exatos.

## Ligacao no bornes (terminal box)

Motor de dupla tensao traz 6 (ou 12) terminais. Para a **menor** tensao usa-se
o fechamento **triangulo**; para a **maior**, **estrela**. O MTR-001 opera em
220 V em **triangulo**. Conferir sempre o diagrama da placa antes de religar.

## Metodos de partida

| Metodo | Quando usar |
|---|---|
| Direto (DOL) | motores pequenos; corrente de partida ~6-8x a nominal |
| Estrela-triangulo | reduz a corrente de partida a ~1/3; carga de baixa inercia |
| Soft-starter | partida suave, reduz esforco mecanico e afundamento de tensao |
| Inversor (VFD) | velocidade variavel; exige cuidados adicionais (ver rolamentos) |

## Relacao com o gemeo digital

As seis variaveis monitoradas (tensao, corrente, temperatura, rotacao,
vibracao em velocidade e em aceleracao) refletem diretamente estas
caracteristicas: corrente x fator de servico/carga, temperatura x classe
termica, rotacao x escorregamento, e vibracao x estado mecanico. Desvios
sustentados devem ser interpretados a luz dos dados de placa do MTR-001.
