# ADR 0003 — Estratégia de OCR para placas de identificação

- **Status:** Aceito
- **Data:** 2026-05-16
- **Sprint:** 1 (decisão) / 2 (implementação)

## Contexto

O cadastro de ativos deve extrair dados da placa de identificação do motor
(fabricante, modelo, potência, tensão, corrente, RPM, IP, classe de isolamento)
a partir de uma foto. As placas têm texto pequeno, baixo contraste, superfície
metálica e layout que varia entre fabricantes (WEG, Siemens, Dutchi, etc.).

## Alternativas avaliadas

| Opção | Prós | Contras |
|---|---|---|
| **Tesseract** | Maduro, offline, gratuito | Fraco em texto pequeno/metálico; exige muito pré-processamento |
| **PaddleOCR** | SOTA em detecção + reconhecimento; bom em texto denso; offline; gratuito | Imagem Docker maior; primeira carga lenta |
| **Azure Form Recognizer** | Alta acurácia; modelos prontos | Custo recorrente; dependência de nuvem; *vendor lock-in* |
| **Claude Vision (API)** | Excelente em layout variável; entende contexto | Custo por chamada; dependência de API externa |

## Decisão

Adotar **PaddleOCR** como motor primário (implementação na Sprint 2): roda
localmente, é gratuito, mantém o dado da placa dentro do ambiente do cliente e
tem boa acurácia em texto pequeno. **Claude Vision** fica documentado como
alternativa para placas de layout muito difícil (*fallback* configurável).

Na Sprint 1, o endpoint `POST /api/v1/assets/extract-from-image` é um **stub**
que devolve a estrutura final esperada (campos + grau de confiança), permitindo
integrar o frontend antes do OCR real.

## Consequências

- **Positivas:** sem custo recorrente; o dado sensível da placa não sai do
  ambiente do cliente.
- **Negativas:** a imagem do backend cresce com as dependências do PaddleOCR.
- **Mitigação:** o módulo `vision` é ativável por *feature flag*
  (`FEATURE_VISION`), evitando carregar o OCR quando não for necessário.
