# Troubleshooting - Falhas Comuns em Motores Eletricos

Guia de diagnostico das falhas mais frequentes em motores de inducao,
com sintomas observaveis na telemetria do Predicta e acoes recomendadas.

## Desgaste de rolamento (bearing wear)

**Sintomas**
- Aumento gradual da vibracao, mais acentuado na aceleracao RMS.
- Elevacao da temperatura da carcaca proxima ao mancal.
- Ruido de rolamento (zumbido ou estalido) que piora com o tempo.

**Causas provaveis**
- Lubrificacao inadequada ou contaminacao do lubrificante.
- Fim da vida util do rolamento; cargas axiais excessivas.
- Corrente eletrica de eixo (descargas pelo rolamento).

**Acao recomendada**
- Confirmar a tendencia no painel do ativo e a estimativa de RUL.
- Programar a troca do rolamento antes de a vibracao atingir 7,1 mm/s.
- Revisar o plano de lubrificacao.

## Desbalanceamento (imbalance)

**Sintomas**
- Vibracao elevada dominante na frequencia de rotacao (1x RPM).
- Velocidade RMS alta com aceleracao RMS relativamente estavel.

**Causas provaveis**
- Acumulo de sujeira no rotor ou no acoplamento.
- Componente solto, empenado ou massa perdida nas pas/ventoinha.

**Acao recomendada**
- Inspecionar e limpar o rotor e o acoplamento.
- Solicitar balanceamento dinamico se a vibracao persistir.

## Sobrecarga (overload)

**Sintomas**
- Corrente sustentada acima de 30 A (nominal 25,4 A).
- Temperatura da carcaca subindo de forma continua.
- Leve queda de rotacao sob carga constante.

**Causas provaveis**
- Carga mecanica acima da capacidade do motor.
- Problema no processo acionado (ex.: bomba obstruida).

**Acao recomendada**
- Reduzir a carga e verificar o equipamento acionado.
- Confirmar a atuacao correta da protecao termica.

## Subtensao ou desequilibrio de fases

**Sintomas**
- Tensao fora da faixa 198 V - 242 V.
- Corrente elevada e aquecimento mesmo sem sobrecarga mecanica.

**Acao recomendada**
- Acionar a equipe eletrica para verificar a alimentacao e as conexoes.
- Nao reenergizar repetidamente um motor que desarma por protecao.

## Quando abrir um chamado de manutencao

Abrir chamado imediatamente quando houver alerta CRITICAL, quando a
vibracao entrar na zona D (acima de 7,1 mm/s) ou quando a estimativa de
RUL indicar menos de 30 dias de vida util remanescente.
