# Simulador OPC-UA — Motor MTR-001

Servidor OPC-UA que simula um motor de indução trifásico 220 V, publicando
telemetria realista e permitindo **injeção de falhas** para demonstração.

## Endpoint

```
opc.tcp://localhost:4840/forzy/server/
```

## Variáveis publicadas (namespace `ns=2`)

| Node | Unidade | Descrição |
|---|---|---|
| `Forzy/Motor/MTR-001/TAG` | — | Identificador do ativo |
| `.../Tensao` | V | Tensão de alimentação (~220 V + ruído) |
| `.../Corrente` | A | Corrente, função do carregamento |
| `.../Temperatura` | °C | Temperatura (modelo térmico de 1ª ordem) |
| `.../Rotacao` | RPM | Rotação do eixo (~1750 RPM com escorregamento) |
| `.../Vibracao_Velocidade_RMS` | mm/s | Velocidade de vibração (DIN ISO 10816/20816) |
| `.../Vibracao_Aceleracao_RMS` | g | Aceleração de vibração RMS |

## Nodes de controle (graváveis)

| Node | Tipo | Faixa | Uso |
|---|---|---|---|
| `.../Control/LoadSetpoint` | double | 0.0 – 1.2 | Carga do motor |
| `.../Control/FaultMode` | string | `NONE` / `BEARING_WEAR` / `UNBALANCE` / `OVERLOAD` | Falha ativa |
| `.../Control/FaultSeverity` | double | 0.0 – 1.0 | Severidade da falha |
| `.../Control/BearingWear` | double | 0.0 – 1.0 | Desgaste acumulado (somente leitura) |

## Modelos físicos

- **Térmico** — sistema de 1ª ordem; elevação proporcional ao quadrado da carga.
- **Elétrico** — corrente interpolada entre vazio e nominal; escorregamento linear.
- **Vibração** — base saudável + carga + degradação de rolamento; aceleração
  cresce mais que a velocidade (defeitos de rolamento são de alta frequência).

## Executar localmente (sem Docker)

```bash
pip install -r requirements.txt
python server.py
```

## Variáveis de ambiente

`OPCUA_HOST`, `OPCUA_PORT`, `OPCUA_NAMESPACE_URI`, `ASSET_TAG`,
`OPCUA_STEP_INTERVAL_S`.
