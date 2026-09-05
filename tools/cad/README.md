# Conversão do CAD da Forzy → GLB

A bancada de bomba de teste exibida no app **é o CAD real da Forzy**, não um
modelo genérico. Este diretório guarda o conversor que gera a malha.

## Origem

Arquivo entregue pela Forzy: `ChallengeForzy-bomba-teste.stp`
(AVEVA, ISO-10303 AP203, unidades em mm). O `.stp` **não** é versionado aqui —
é material do cliente; guarde-o fora do repositório.

## Saída

`frontend/public/models/bomba-teste.glb` — 17 sólidos, ~12k triângulos, 263 KB.
Já vem em metros, no referencial do three.js (eixo da máquina em X, vertical em
Y, profundidade em Z), centrado em X/Z com a base em Y=0.

## Como rodar

Precisa do kernel OpenCascade (não é dependência do projeto — é ferramenta de
build, roda uma vez quando o CAD muda):

```bash
python -m venv cqenv            # use um caminho CURTO: o OCP estoura MAX_PATH
cqenv/Scripts/pip install cadquery-ocp trimesh numpy
cqenv/Scripts/python tools/cad/step_to_glb.py
```

Ajuste `SRC` no script para o caminho do `.stp`.

## Por que tesselar, e não medir o STEP "na mão"

As superfícies do STEP são B-splines. O bounding box dos **pontos de controle**
fica FORA da superfície real e infla as medidas em ~55% — foi assim que o motor
"mediu" ⌀412 mm quando na verdade é ⌀265. As medidas em
`frontend/src/lib/benchGeometry.ts` vêm da **malha tesselada**, que é a
geometria de verdade.
