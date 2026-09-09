"""Resolucao de ativo e leitura de dados para o assistente Volt.

Existe porque o Volt lia o catalogo por conta propria e enxergava um sistema
diferente do que as telas mostram:

* pegava ``asset.status`` cru do repositorio, entao um CONJUNTO (motor-bomba da
  Forzy) aparecia como "unknown" enquanto a interface mostrava "operacional" -
  quem consolida e ``rollup_status``, no servico de ativos;
* pedia telemetria da TAG do conjunto, que nao mede nada (quem mede sao os
  mancais), e respondia "sem leituras disponiveis" com os dois sensores ativos;
* so reconhecia ativo por codigo, entao "o mancal do lado da bomba" nao chegava
  a lugar nenhum.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.assets.service import rollup_status
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.volt.nlu import extract_asset_code

logger = logging.getLogger("forzy.volt.lookup")

# Variaveis em que "maior e pior": ao consolidar varios pontos de medicao num
# unico conjunto, o pior valor e o que interessa para manutencao.
_PIOR_E_MAIOR = (
    "Vibracao_Velocidade_RMS",
    "Vibracao_Aceleracao_RMS",
    "Temperatura",
    "Corrente",
)

# Palavras vazias: nao ajudam a distinguir um ativo de outro.
_STOPWORDS = {
    "do", "da", "de", "dos", "das", "o", "a", "os", "as", "um", "uma", "no",
    "na", "em", "com", "que", "esta", "estao", "meu", "minha", "esse", "essa",
    "qual", "sobre", "para", "pelo", "pela", "ativo", "equipamento",
}


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sem_acento if not unicodedata.combining(c))


def _tokens(texto: str) -> set[str]:
    return {
        palavra
        for palavra in re.findall(r"[a-z0-9]{3,}", _normalizar(texto))
        if palavra not in _STOPWORDS
    }


@dataclass
class LeituraDePonto:
    """As leituras de UM ponto de medicao, preservadas separadamente."""

    tag: str
    nome: str
    status: str
    leituras: dict[str, float] = field(default_factory=dict)


@dataclass
class Telemetria:
    """O que o Volt le de um ativo.

    Duas visoes da MESMA telemetria, porque servem a coisas diferentes:

    * ``consolidado`` usa os nomes canonicos das variaveis e guarda o PIOR valor
      de cada uma. E o que `diagnose` sabe interpretar.
    * ``pontos`` preserva cada sensor separado. Um conjunto como o motor-bomba da
      Forzy tem DOIS mancais, e responder so pelo pior (ou so por um) esconde
      metade do equipamento de quem perguntou.
    """

    consolidado: dict[str, float] = field(default_factory=dict)
    origem: dict[str, str] = field(default_factory=dict)
    pontos: list[LeituraDePonto] = field(default_factory=list)

    @property
    def tem_multiplos_pontos(self) -> bool:
        return len(self.pontos) > 1


async def resolver_ativo(
    repo: AssetRepository, texto: str
) -> tuple[Asset, str] | None:
    """Acha o ativo por CODIGO ou por NOME/descricao, com status consolidado.

    Devolve ``(asset, status_consolidado)``. O status vem separado de proposito:
    escrever em ``asset.status`` marcaria o objeto como sujo na sessao e o valor
    derivado acabaria persistido no banco.
    """
    codigo = extract_asset_code(texto)
    asset = await repo.get_asset_by_tag(codigo) if codigo else None

    if asset is None:
        asset = await _casar_por_nome(repo, texto)
    if asset is None:
        return None

    pontos = await repo.list_points(asset.tag)
    return asset, rollup_status(asset, pontos)


async def _casar_por_nome(repo: AssetRepository, texto: str) -> Asset | None:
    """Casa "mancal do lado da bomba" com o ativo cujo nome tem esses termos.

    Exige pelo menos DOIS termos em comum e nenhum empate no topo: com um termo
    so, "motor" casaria com qualquer coisa, e um palpite errado e pior que pedir
    o codigo. O catalogo tem poucos ativos, entao a varredura linear basta.
    """
    termos = _tokens(texto)
    if len(termos) < 2:
        return None

    pontuados: list[tuple[int, Asset]] = []
    for candidato in await repo.list_assets():
        # So TAG e nome. O modelo e identico entre os pontos do mesmo conjunto
        # ("Bancada bomba de teste R11..."), entao ele empatava os dois mancais
        # e afogava justamente a palavra que os distingue (bomba x motor).
        alvo = _tokens(f"{candidato.tag} {candidato.name or ''}")
        pontuados.append((len(termos & alvo), candidato))
    pontuados.sort(key=lambda item: item[0], reverse=True)

    if not pontuados or pontuados[0][0] < 2:
        return None
    if len(pontuados) > 1 and pontuados[1][0] == pontuados[0][0]:
        return None  # empate: melhor perguntar do que chutar
    return pontuados[0][1]


async def ler_telemetria(
    telemetry: TelemetryRepository, repo: AssetRepository, asset: Asset
) -> Telemetria:
    """Leituras atuais do ativo; de seus PONTOS quando ele nao mede sozinho.

    Devolve SEMPRE os dois recortes: cada ponto separado (para a resposta poder
    falar dos dois mancais) e o consolidado por variavel (para o diagnostico).

    O consolidado mantem os nomes canonicos das variaveis - prefixa-los com a
    TAG do ponto faria `diagnose` deixar de reconhecer as grandezas e responder
    "os sensores nao confirmam o sintoma" com um mancal em 9 mm/s.
    """
    proprias = await telemetry.latest(asset.tag)
    if proprias:
        leituras = {linha["variable"]: linha["value"] for linha in proprias}
        return Telemetria(
            consolidado=leituras,
            pontos=[
                LeituraDePonto(
                    tag=asset.tag,
                    nome=asset.name or asset.tag,
                    status=asset.status,
                    leituras=leituras,
                )
            ],
        )

    consolidado: dict[str, float] = {}
    origem: dict[str, str] = {}
    pontos: list[LeituraDePonto] = []
    for ponto in await repo.list_points(asset.tag):
        rotulo = ponto.name or ponto.tag
        do_ponto: dict[str, float] = {}
        for linha in await telemetry.latest(ponto.tag):
            variavel, valor = linha["variable"], linha["value"]
            do_ponto[variavel] = valor
            atual = consolidado.get(variavel)
            if atual is None or (variavel in _PIOR_E_MAIOR and valor > atual):
                consolidado[variavel] = valor
                origem[variavel] = rotulo
        if do_ponto:
            pontos.append(
                LeituraDePonto(
                    tag=ponto.tag, nome=rotulo, status=ponto.status, leituras=do_ponto
                )
            )
    return Telemetria(consolidado=consolidado, origem=origem, pontos=pontos)


# ---------------------------- Saude e contexto ----------------------------
# O agente so respondia placa + leitura instantanea. Metrica que a tela mostra
# (baseline, anomalia, RUL, alerta, limiar) nunca entrava no contexto dele - e
# ai o modelo dizia "nao tenho acesso", porque de fato nao tinha.


async def ler_saude(asset_tag: str) -> dict[str, object]:
    """Veredito dos modelos para um ponto de medicao, como na tela de saude.

    `train_if_missing=False` de proposito: treinar dentro de um turno de chat
    seguraria a resposta. Sem artefato pronto o campo sai `available: false`, e
    o assistente diz que o modelo nao esta disponivel - o que e verdade.
    Falha de ML nunca derruba o atendimento: devolve o que conseguiu.
    """
    from app.infra.db.base import timeseries_session_factory
    from app.modules.ml.service import ml_service

    saude: dict[str, object] = {}
    try:
        async with timeseries_session_factory() as sessao:
            baseline = await ml_service.predict_baseline(
                sessao, asset_tag, train_if_missing=False
            )
            anomalia = await ml_service.predict_anomaly(
                sessao, asset_tag, train_if_missing=False
            )
            rul = await ml_service.estimate_rul(sessao, asset_tag)
            # predict_fault NAO aceita train_if_missing (ml/service.py:475):
            # passar o kwarg levantaria TypeError e derrubaria a ferramenta
            # inteira, para qualquer ativo.
            falha = await ml_service.predict_fault(sessao, asset_tag)
    except Exception:  # pragma: no cover - ML fora do ar nao pode quebrar o chat
        logger.warning("saude indisponivel para %s", asset_tag, exc_info=True)
        return {}

    if baseline.available:
        saude["baseline"] = {
            "decisao": baseline.decision,
            "score": baseline.score,
        }
    if anomalia.available:
        saude["anomalia"] = {
            "detectada": anomalia.is_anomaly,
            "erro_reconstrucao": anomalia.reconstruction_error,
            "limiar_do_modelo": anomalia.threshold,
        }
    if rul.available:
        saude["vida_util_restante"] = {
            "dias": rul.rul_days,
            "intervalo_dias": [rul.confidence_low_days, rul.confidence_high_days],
            "tendencia_mm_s_por_dia": rul.trend_mm_s_per_day,
            "observacao": rul.note,
        }
    if falha.available:
        saude["classificacao_de_falha"] = {
            "falha": falha.fault,
            "confianca": falha.confidence,
            # O schema ja marca o que e demonstracao; repassar para o modelo
            # nao apresentar dado simulado como medicao de campo.
            "simulado": falha.simulated,
            "observacao": falha.note,
        }
    return saude


async def ler_alertas(asset_tag: str, limite: int = 5) -> list[dict[str, object]]:
    """Alertas do ativo: os abertos primeiro, como a tela mostra."""
    from app.infra.db.base import catalog_session_factory
    from app.modules.alerts.repository import AlertRepository

    try:
        async with catalog_session_factory() as sessao:
            repo = AlertRepository(sessao)
            abertos = await repo.list_alerts(
                asset_tag=asset_tag, only_active=True, limit=limite
            )
            recentes = await repo.list_alerts(asset_tag=asset_tag, limit=limite)
    except Exception:  # pragma: no cover
        logger.warning("alertas indisponiveis para %s", asset_tag, exc_info=True)
        return []

    vistos: set[str] = set()
    saida: list[dict[str, object]] = []
    for alerta in [*abertos, *recentes]:
        chave = str(alerta.id)
        if chave in vistos:
            continue
        vistos.add(chave)
        saida.append(
            {
                "severidade": alerta.severity,
                "tipo": alerta.alert_type,
                "mensagem": alerta.message,
                "aberto": not alerta.acknowledged,
                "criado_em": alerta.created_at.isoformat() if alerta.created_at else None,
                "reincidencias": getattr(alerta, "occurrence_count", 1),
            }
        )
    return saida[: limite * 2]


def limiares_de(asset: Asset) -> dict[str, float]:
    """Limiares DO ATIVO, com o fallback ISO — os mesmos do avaliador.

    Sem isto o assistente julgaria 6,4 mm/s pelo ISO global (4,5) sem ver que o
    limite deste mancal e 6,92: diria "critico" onde o sistema diz "atencao".
    """
    from app.modules.alerts.evaluator import AlertsEvaluator

    return AlertsEvaluator._thresholds(asset)
