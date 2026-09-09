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

import re
import unicodedata
from dataclasses import dataclass, field

from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.assets.service import rollup_status
from app.modules.telemetry.repository import TelemetryRepository
from app.modules.volt.nlu import extract_asset_code

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
class AssetSnapshot:
    """O que o Volt sabe de um ativo: cadastro, status real e leituras reais."""

    asset: Asset
    status: str
    readings: dict[str, float] = field(default_factory=dict)
    # De qual ponto de medicao veio cada leitura (so quando ha fan-out).
    origem: dict[str, str] = field(default_factory=dict)

    @property
    def tag(self) -> str:
        return self.asset.tag

    def descricao_origem(self) -> str:
        """Ex.: 'Vibracao do mancal lado motor' — de onde veio o pior valor."""
        if not self.origem:
            return ""
        pontos = sorted(set(self.origem.values()))
        return f"Leituras consolidadas de {len(pontos)} ponto(s): {', '.join(pontos)}."


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
) -> tuple[dict[str, float], dict[str, str]]:
    """Leituras atuais do ativo; de seus PONTOS quando ele nao mede sozinho.

    As chaves continuam sendo os nomes canonicos das variaveis - prefixa-las com
    a TAG do ponto faria ``diagnose`` deixar de reconhecer as grandezas e
    responder "os sensores nao confirmam o sintoma" com um mancal em 9 mm/s.
    Consolidando varios pontos, vence o PIOR valor, e guardamos de onde veio.
    """
    proprias = await telemetry.latest(asset.tag)
    if proprias:
        return {linha["variable"]: linha["value"] for linha in proprias}, {}

    leituras: dict[str, float] = {}
    origem: dict[str, str] = {}
    for ponto in await repo.list_points(asset.tag):
        rotulo = ponto.name or ponto.tag
        for linha in await telemetry.latest(ponto.tag):
            variavel, valor = linha["variable"], linha["value"]
            atual = leituras.get(variavel)
            if atual is None or (variavel in _PIOR_E_MAIOR and valor > atual):
                leituras[variavel] = valor
                origem[variavel] = rotulo
    return leituras, origem
