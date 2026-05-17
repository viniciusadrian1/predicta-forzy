# ADR 0004 — Representação da planta baixa (DWG → SVG)

- **Status:** Aceito
- **Data:** 2026-05-17
- **Sprint:** 2

## Contexto

O desafio fornece a planta do ativo em `ChallengeForzy-bomba-teste.dwg`
(AutoCAD, formato binário AC1032 / AutoCAD 2026). A Sprint 2 exige uma planta
baixa **interativa e navegável** no frontend, com cada equipamento clicável.

Converter DWG → SVG exige ferramentas proprietárias/externas: **ODA File
Converter** ou **LibreCAD**, que não estão disponíveis no ambiente de build
deste MVP. O arquivo `.stp` (STEP) contém geometria 3D B-rep, cuja projeção
para uma planta 2D limpa é complexa e fora do escopo da sprint.

## Decisão

1. A planta baixa é **autorada manualmente** como um SVG vetorial
   (`assets/plant_layouts/ChallengeForzy-bomba-teste.svg`), representando de
   forma esquemática a Sala de Bombas onde opera o motor MTR-001. Esta opção é
   explicitamente prevista no escopo do desafio ("crie SVG manualmente").
2. O SVG é apenas o **pano de fundo** (paredes, áreas, equipamentos fixos). Os
   **marcadores de ativos são renderizados dinamicamente** pelo componente
   `PlantMap`, posicionados pelas coordenadas `position_x` / `position_y` de
   cada ativo vindas da API. Assim, novos ativos aparecem no mapa sem editar o
   SVG.
3. Cada marcador é um `<g data-asset-tag="...">` clicável, colorido conforme o
   status (verde / amarelo / vermelho) e com tooltip ao passar o mouse.

## Alternativas consideradas

- **ODA File Converter no pipeline de build:** caminho ideal para fidelidade ao
  DWG original; fica registrado como evolução futura quando a ferramenta puder
  ser incorporada à imagem de build.
- **Extrair 2D do STEP:** exigiria um kernel CAD (OpenCASCADE); desproporcional
  para o MVP.

## Consequências

- **Positivas:** mapa 100% web, leve, sem dependência de CAD; marcadores
  data-driven; o DWG/STEP originais permanecem versionados em `assets/3d_models/`.
- **Negativas:** o layout é esquemático, não a planta exata do DWG.
- **Evolução:** integrar o ODA File Converter ao build para gerar o SVG a
  partir do DWG real, mantendo a sobreposição dinâmica de marcadores.
