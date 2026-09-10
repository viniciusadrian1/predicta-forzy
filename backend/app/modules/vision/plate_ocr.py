"""Pipeline de OCR para placas de identificacao de equipamentos.

Etapas: pre-processamento da imagem -> OCR (Tesseract, ou PaddleOCR se o
extra ``ocr`` estiver instalado) -> parsing regex dos campos da placa.

IMPORTANTE: quando nenhum motor de OCR esta disponivel, o servico devolve
um resultado VAZIO e sinaliza a indisponibilidade - jamais inventa dados.
O parser reconhece tanto campos de motor (kW, V, A, RPM...) quanto campos
genericos de placa (fabricante, modelo, numero de serie, data).
"""

from __future__ import annotations

import difflib
import io
import itertools
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from PIL import Image, ImageChops, ImageFilter, ImageOps, ImageStat

logger = logging.getLogger("forzy.vision.ocr")


@dataclass(slots=True)
class ParsedField:
    """Um campo extraido da placa, com grau de confianca."""

    field: str
    label: str
    value: str | None
    confidence: float


@dataclass(slots=True)
class ExtractionResult:
    """Resultado completo da extracao de uma placa."""

    engine: str
    raw_text: str
    fields: list[ParsedField]
    coverage: float


# --------------------------- Pre-processamento ---------------------------
# Raio do BoxBlur (janela de ~51px na imagem ja normalizada em 1600px) e quanto
# o pixel precisa estar abaixo da media local para contar como tinta. Medidos:
# janelas menores com margem maior liam melhor em foto degradada, mas
# CORROMPIAM valor em placa limpa (a corrente "11,5/6,6" virava "11,5/6,66") -
# e valor errado com confianca alta e pior que campo ausente.
_RAIO_LOCAL = 25
_MARGEM_TINTA = 10
# Abaixo disto a leitura e considerada fraca e vale uma segunda tentativa.
_COBERTURA_ACEITAVEL = 0.6
# Foto de placa tirada na mao sai sempre alguns graus torta, e o Tesseract
# aguenta mal: a MESMA placa a 6 graus troca "1755" por "4755" e come um digito
# da corrente. Buscar ate 8 graus cobre a mao tremida; alem disso a foto foi
# tirada de lado e o problema e outro.
_LIMITE_INCLINACAO = 8.0
_PASSO_INCLINACAO = 0.5
# Endireitar so compensa se a medida melhorar de verdade. A margem tambem paga
# o borrao da reamostragem: `rotate(0)` devolve copia sem filtro, entao o angulo
# zero larga em vantagem e um ganho pequeno nao prova nada.
_GANHO_MINIMO = 1.08


def _variacao_entre_linhas(imagem: Image.Image) -> float:
    """Quao marcada e a alternancia entre linha de texto e entrelinha.

    Com o texto alinhado as linhas alternam entre escuro (a letra) e claro (a
    entrelinha), e a mudanca de uma linha para a seguinte e brusca; torto, tudo
    borra na mesma media e a mudanca some.

    Mede a diferenca entre linhas VIZINHAS, nao o desvio padrao do perfil
    inteiro: metade da placa na sombra e uma rampa suave que infla o desvio
    padrao sem dizer nada sobre alinhamento - com aquele criterio esta busca
    escolhia um angulo absurdo e destruia justamente a foto de luz desigual.

    `resize((1, altura))` e a media de cada linha calculada em C - sem numpy,
    que nem e dependencia declarada deste backend, e sem laco em Python.
    """
    perfil = imagem.resize((1, imagem.height), Image.BOX)
    vizinha = ImageChops.offset(perfil, 0, 1)
    return ImageStat.Stat(ImageChops.difference(perfil, vizinha)).mean[0]


def _angulo_do_texto(imagem: Image.Image) -> float:
    """Inclinacao do texto, pelo perfil de projecao horizontal.

    A busca roda numa miniatura: o angulo nao muda com a escala, e assim as 33
    rotacoes de teste custam poucos milissegundos.
    """
    largura = 320
    if imagem.width < largura:
        return 0.0
    miniatura = imagem.resize((largura, max(1, round(largura * imagem.height / imagem.width))))
    referencia = _variacao_entre_linhas(miniatura)
    melhor_angulo, melhor_variacao = 0.0, referencia
    passos = int(_LIMITE_INCLINACAO / _PASSO_INCLINACAO)
    for i in range(-passos, passos + 1):
        angulo = i * _PASSO_INCLINACAO
        if angulo == 0.0:
            continue
        girada = miniatura.rotate(angulo, resample=Image.BILINEAR, fillcolor=255)
        variacao = _variacao_entre_linhas(girada)
        if variacao > melhor_variacao:
            melhor_variacao, melhor_angulo = variacao, angulo
    return melhor_angulo if melhor_variacao > referencia * _GANHO_MINIMO else 0.0


def preprocess_image(raw: bytes) -> Image.Image:
    """Normaliza a imagem da placa para melhorar a leitura por OCR.

    Aplica correcao de orientacao, escala de cinza, realce de contraste,
    ENDIREITAMENTO do texto, nitidez e upscale de textos pequenos.
    """
    image = Image.open(io.BytesIO(raw))
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    angulo = _angulo_do_texto(image)
    if angulo:
        # Fundo branco na borda nova: depois do autocontraste o papel da placa
        # ja e o tom claro, entao o remendo nao vira uma faixa de "tinta".
        image = image.rotate(angulo, resample=Image.BICUBIC, expand=True, fillcolor=255)
    image = image.filter(ImageFilter.SHARPEN)
    longest = max(image.size)
    if longest < 1600:
        scale = 1600 / longest
        image = image.resize((round(image.width * scale), round(image.height * scale)))
    return image


def preprocess_adaptativo(raw: bytes) -> Image.Image:
    """Binariza com limiar ADAPTATIVO — segunda tentativa para foto ruim.

    Cada pixel e comparado com a media da sua vizinhanca, nao com um valor unico
    do quadro. E o que salva a foto de iluminacao desigual (metade da placa na
    sombra, metade estourada), onde qualquer limiar global apaga um lado ou
    satura o outro — e onde o pipeline padrao chega a devolver ZERO campo.

    NAO e o padrao. Medido em banco balanceado (so 2 de 8 degradacoes sendo de
    iluminacao): 9 casos melhoram, 9 PIORAM, cobertura media praticamente igual
    (0,848 -> 0,862) e 28% mais lento. O ganho grande so aparece quando o banco
    e dominado por iluminacao desigual. Como segunda tentativa, fica o resgate
    sem as regressoes.

    O BoxBlur do PIL ja e a media local: sem dependencia nova (numpy nem e
    dependencia declarada deste backend).
    """
    base = preprocess_image(raw)
    media_local = base.filter(ImageFilter.BoxBlur(_RAIO_LOCAL))
    # (pixel - media_local + 128): tinta e quem ficou abaixo da media local.
    contraste = ImageChops.subtract(base, media_local, scale=1, offset=128)
    binaria = contraste.point(lambda p: 0 if p < 128 - _MARGEM_TINTA else 255, mode="L")
    # Mediana depois do limiar tira o salpico que a binarizacao cria no grao.
    return binaria.filter(ImageFilter.MedianFilter(3))


# ------------------------------- Parser ----------------------------------
_KNOWN_MANUFACTURERS = (
    "WEG",
    "SIEMENS",
    "DUTCHI",
    "METALCORTE",
    "ABB",
    "TECO",
    "BALDOR",
)
_NUM = r"\d+(?:[.,]\d+)?"
_MULTI = rf"{_NUM}(?:\s*/\s*{_NUM})*"

# (chave, rotulo, padrao) para cada campo tipico de placa de motor.
_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("power_kw", "Potência (kW)", re.compile(rf"({_NUM})\s*k\s*W", re.IGNORECASE)),
    (
        "voltage_v",
        "Tensão (V)",
        re.compile(rf"({_MULTI})\s*V(?:olts)?(?![A-Za-z])", re.IGNORECASE),
    ),
    (
        "nominal_current_a",
        "Corrente (A)",
        re.compile(rf"({_MULTI})\s*A(?:mp)?(?![A-Za-z])", re.IGNORECASE),
    ),
    ("frequency_hz", "Frequência (Hz)", re.compile(r"(\d{2})\s*Hz", re.IGNORECASE)),
    (
        "nominal_rpm",
        "Rotação (RPM)",
        re.compile(r"(\d{3,4})\s*(?:RPM|r/min|min-?1)", re.IGNORECASE),
    ),
    (
        "ip_rating",
        "Grau de proteção",
        # O "I" de IP sai como 1 ou l no OCR de placa gravada ("1p55"). A faixa
        # 2x-6x cobre os graus reais (IP21..IP68) e evita casar com um ano solto
        # como "1955". O valor e normalizado para "IP##" em _NORMALIZADORES.
        re.compile(
            r"(?<![A-Za-z0-9])[I1l][Pp]\s?([0-9OSDBZGIl]{2})(?![A-Za-z0-9])"
        ),
    ),
    (
        "insulation_class",
        "Classe de isolamento",
        re.compile(r"(?:ISOL\w*|CLASSE|CL\.?|INS\w*)\s*[:.]?\s*([BFH])\b", re.IGNORECASE),
    ),
    (
        "service_factor",
        "Fator de serviço",
        re.compile(
            r"(?:F\.?\s?S\.?|FATOR\s*DE\s*SERVI\w*|SERVICE\s*FACTOR)\s*[:.]?\s*"
            r"([01OlLI][.,]?[\dOlLI]{1,2})",
            re.IGNORECASE,
        ),
    ),
    (
        "power_factor",
        "Fator de potência",
        re.compile(
            r"(?:F\.?\s?P\.?|COS\s*[O0]?|POWER\s*FACTOR)\s*[:.]?\s*([0O][.,]?[\dOlLI]{1,2})",
            re.IGNORECASE,
        ),
    ),
)
_POWER_CV = re.compile(rf"({_NUM})\s*(?:CV|HP)", re.IGNORECASE)
_MODEL = re.compile(
    r"(?:MOD(?:ELO)?|TYPE|TIPO)\.?\s*:?\s*([A-Z0-9][A-Z0-9 \-/]{2,30})", re.IGNORECASE
)

# Campos considerados no calculo de cobertura.
EXPECTED_FIELDS = (
    "manufacturer",
    "model",
    "power_kw",
    "voltage_v",
    "nominal_current_a",
    "frequency_hz",
    "nominal_rpm",
    "ip_rating",
    "insulation_class",
)


# Normalizacao do valor extraido. A regex de IP captura so os digitos (para
# tolerar o "1p55" que o OCR produz em placa gravada); o cadastro precisa
# receber "IP55", nao "55".
_NORMALIZADORES: dict[str, "Callable[[str], str]"] = {
    "ip_rating": lambda valor: f"IP{valor.strip()}",
}


# ------------------- Correcao das confusoes tipicas do OCR -----------------
# Placa de motor e texto GRAVADO em metal: baixo contraste, sem serifa e com
# reflexo. O Tesseract erra sempre nos mesmos pontos - e quase sempre na
# UNIDADE, nao no numero. Corrigir a unidade aqui, uma vez, deixa as regexes
# de campo simples em vez de cada uma ter que prever todo tipo de lixo.
_CORRECOES: tuple[tuple[re.Pattern[str], str], ...] = (
    # "7,5 kW" sai como "7,5 K\N", "KVV", "KN", "KM", "RW".
    (re.compile(r"(\d)\s*[KkRr]\s*(?:\\N|VV|N|M|W|VJ)(?![A-Za-z])"), r"\1 kW"),
    # O "I" de IP e o caractere mais instavel da placa: vira \ ( [ | / 1 l.
    (re.compile(r"(?<![A-Za-z0-9])[I1l|\\(\[/]\s?[Pp](?=\s?[0-9OSDBZGIl]{2})"), "IP"),
    # "220 V" sai como "220 NV", "220 \/", "220 |V".
    (re.compile(r"(\d)\s*(?:NV|\\/|\\V|\|V)(?![A-Za-z])"), r"\1 V"),
    # "60 Hz" sai como "60 H2", "60 HZ", "60 H z".
    (re.compile(r"(\d)\s*H\s*[z2Z](?![A-Za-z])"), r"\1 Hz"),
)

# Letra que o OCR troca por digito dentro de um codigo numerico (IP55 -> IPSS).
# Fica de fora o que e ambiguo demais para adivinhar (D pode ser 0 ou 5): campo
# ausente e melhor que campo errado.
_LETRA_PARA_DIGITO = str.maketrans(
    {
        "O": "0",
        "Q": "0",
        "I": "1",
        "l": "1",
        "L": "1",
        "Z": "2",
        "S": "5",
        "G": "6",
        "T": "7",
        "B": "8",
    }
)


def _normalizar_ocr(texto: str) -> str:
    """Aplica as correcoes de unidade ao texto lido, antes do parsing."""
    for padrao, troca in _CORRECOES:
        texto = padrao.sub(troca, texto)
    return texto


# --------------------------- Checagem fisica -------------------------------
# Todo campo numerico passa por aqui antes de virar valor. O parser antigo
# usava `search`: o PRIMEIRO casamento vencia, plausivel ou nao - e numa foto
# torta "60 Hz 4755 RPM" gravava 4755 rpm no ativo. Motor de inducao NAO gira
# a 4755 rpm em nenhuma frequencia de rede.

# Rotacao sincrona = 120 * f / polos, para 50 e 60 Hz e 2..12 polos.
_ROTACOES_SINCRONAS = tuple(
    sorted({round(120 * f / polos) for f in (50, 60) for polos in range(2, 14, 2)})
)


def _numeros(valor: str) -> list[float]:
    """Os componentes numericos de um valor tipo "220/380"."""
    return [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", valor)]


def _rpm_plausivel(valor: str) -> bool:
    """Rotacao possivel para um motor ligado em rede de 50 ou 60 Hz."""
    # Motor de inducao gira ABAIXO do sincrono (escorregamento de 0 a 10%). A
    # folga para cima cobre o motor sincrono, que gira exatamente no ponto.
    return any(
        sincrona * 0.90 <= n <= sincrona * 1.005
        for n in _numeros(valor)
        for sincrona in _ROTACOES_SINCRONAS
    )


def _faixa(minimo: float, maximo: float) -> "Callable[[str], bool]":
    """Checagem de faixa que vale para TODOS os componentes de "220/380"."""

    def checar(valor: str) -> bool:
        numeros = _numeros(valor)
        return bool(numeros) and all(minimo <= n <= maximo for n in numeros)

    return checar


_PLAUSIVEL: dict[str, "Callable[[str], bool]"] = {
    "nominal_rpm": _rpm_plausivel,
    # Rede industrial e 50 ou 60 Hz. 400 Hz e aeronautico, nao entra aqui.
    "frequency_hz": lambda v: _numeros(v) in ([50.0], [60.0]),
    "power_kw": _faixa(0.01, 10_000),
    "voltage_v": _faixa(12, 15_000),
    "nominal_current_a": _faixa(0.05, 10_000),
    "service_factor": _faixa(1.0, 1.5),
    "power_factor": _faixa(0.4, 1.0),
    # IP00 a IP69 sao os graus que a IEC 60529 define.
    "ip_rating": lambda v: bool(re.fullmatch(r"[0-6][0-9]", v)),
    "insulation_class": lambda v: v.upper() in {"A", "B", "E", "F", "H", "N", "R"},
}

# Digitos que o OCR troca entre si nesta fonte. Usado SO para consertar rotacao,
# onde a checagem fisica e discreta o bastante para o conserto ser verificavel.
_DIGITOS_CONFUNDIDOS = {
    "0": "8",
    "1": "47",
    "2": "7",
    "3": "89",
    "4": "1",
    "5": "68",
    "6": "58",
    "7": "12",
    "8": "036",
    "9": "38",
}


def _consertar_rotacao(valor: str) -> str | None:
    """Troca UM digito e devolve o conserto so se ele for o unico plausivel.

    "4755 RPM" numa foto torta e "1755": 4 e 1 se confundem nesta fonte, e 1755
    cai na faixa do motor de 4 polos a 60 Hz enquanto 4755 nao cai em nenhuma.
    Se mais de um conserto der certo nao ha o que decidir - devolve None e o
    campo fica vazio, que e o desfecho seguro.
    """
    candidatos = {
        valor[:i] + troca + valor[i + 1 :]
        for i, digito in enumerate(valor)
        for troca in _DIGITOS_CONFUNDIDOS.get(digito, "")
    }
    plausiveis = {c for c in candidatos if _rpm_plausivel(c)}
    return plausiveis.pop() if len(plausiveis) == 1 else None


# Campos onde a virgula decimal cabe. Fora daqui repor virgula seria invencao:
# "4755 RPM" viraria "475,5 RPM", que ate cai numa faixa sincrona valida.
_CAMPOS_DECIMAIS = frozenset(
    {"power_kw", "service_factor", "power_factor", "nominal_current_a"}
)


def _com_virgula_reposta(valor: str) -> set[str]:
    """Leituras possiveis do valor com a virgula reposta em cada componente.

    So mexe em componente que ficou SEM separador: o OCR come a virgula, nao a
    muda de lugar. Sem essa restricao "25,4/147" teria duas leituras com a mesma
    razao entre os componentes ("2,54/1,47" e "25,4/14,7") e nao haveria como
    decidir.
    """
    opcoes: list[list[str]] = []
    for parte in valor.split("/"):
        so_digitos = parte.translate(_LETRA_PARA_DIGITO)
        if any(sep in parte for sep in ",.") or not so_digitos.isdigit():
            opcoes.append([parte])
            continue
        opcoes.append(
            [so_digitos]
            + [f"{so_digitos[:i]},{so_digitos[i:]}" for i in range(1, len(so_digitos))]
        )
    return {"/".join(combinacao) for combinacao in itertools.product(*opcoes)}


def _reparar_numero(valor: str, chave: str, checar: "Callable[[str], bool]") -> str | None:
    """Conserta o valor quando a faixa do campo torna o conserto UNICO.

    "FS 1,15" sai como "FS 115" e "FS 1,0" sai como "FSLO" - o Tesseract come o
    separador e le O por 0, L por 1. Fator de servico vive entre 1,0 e 1,5,
    entao so uma posicao da virgula cabe na faixa, e o conserto e verificavel.
    Se mais de uma couber, devolve None e o campo fica vazio.
    """
    candidatos = {valor.translate(_LETRA_PARA_DIGITO)}
    if chave in _CAMPOS_DECIMAIS:
        candidatos |= _com_virgula_reposta(valor)
    validos = {c for c in candidatos if c != valor and checar(c)}
    return validos.pop() if len(validos) == 1 else None


def _melhor_casamento(
    padrao: re.Pattern[str], texto: str, chave: str
) -> tuple[str, bool] | None:
    """Melhor valor para um campo: o mais informativo que passa na checagem.

    Devolve (valor, foi_consertado). Entre varios casamentos prefere o que tem
    mais componentes - "25,4/14,7 A" descreve as duas ligacoes do motor, e "7 A"
    e o resto de uma leitura que o reflexo comeu.
    """
    checar = _PLAUSIVEL.get(chave)
    brutos = [m.group(1).strip() for m in padrao.finditer(texto)]
    if not brutos:
        return None
    if chave == "ip_rating":
        brutos = [b.translate(_LETRA_PARA_DIGITO) for b in brutos]
    if checar is None:
        return brutos[0], False

    validos = [b for b in brutos if checar(b)]
    if validos:
        return max(validos, key=lambda v: (len(_numeros(v)), len(v))), False
    for bruto in brutos:
        reparado = _reparar_numero(bruto, chave, checar)
        if reparado is not None:
            return reparado, True
    if chave == "nominal_rpm":
        for bruto in brutos:
            consertado = _consertar_rotacao(bruto)
            if consertado:
                return consertado, True
    return None


# Semelhanca minima para aceitar um nome que o OCR machucou. Medido sobre todas
# as palavras que o banco de placas produziu: "ETALCORTE", "JUTCHI" e "NEMENS"
# entram, e nenhuma palavra de fora ("INDUSTRIAL", "TRIFASICO", "PREMIUM")
# alcanca este valor contra nenhum dos nomes da lista.
_SEMELHANCA_MINIMA = 0.75


def _fabricante_conhecido(upper: str) -> tuple[str, bool] | None:
    """Nome da lista de fabricantes, tolerando a letra que o OCR comeu.

    Devolve (nome, foi_aproximado). "ETALCORTE" e "UTCHI MOTORS" sao placas
    conhecidas com a primeira letra perdida no corte ou na perspectiva da foto.
    O nome vira coluna do ativo e o tecnico filtra a frota por ele - vale
    reconhecer, desde que a tela avise que foi aproximacao.

    Fica com o MELHOR casamento de toda a placa, nao com o primeiro que passa:
    varrendo em ordem de leitura, uma palavra qualquer do subtitulo poderia
    ganhar de um nome que aparece mais abaixo e casa muito melhor.

    A comparacao aproximada so vale para nome com 5+ letras: "ABB", "WEG" e
    "TECO" sao curtos demais, qualquer palavra parecida viraria falso positivo.
    """
    for nome in _KNOWN_MANUFACTURERS:
        if nome in upper:
            return nome, False

    longos = [nome for nome in _KNOWN_MANUFACTURERS if len(nome) >= 5]
    melhor_nome, melhor_semelhanca = None, 0.0
    for palavra in re.findall(r"[A-Z]{4,}", upper):
        for nome in longos:
            semelhanca = difflib.SequenceMatcher(None, palavra, nome).ratio()
            if semelhanca > melhor_semelhanca:
                melhor_nome, melhor_semelhanca = nome, semelhanca
    if melhor_nome and melhor_semelhanca >= _SEMELHANCA_MINIMA:
        return melhor_nome, True
    return None


def parse_nameplate_text(text: str, base_confidence: float = 0.9) -> list[ParsedField]:
    """Extrai os campos tipicos de uma placa de motor a partir do texto OCR."""
    fields: list[ParsedField] = []
    text = _normalizar_ocr(text)
    upper = text.upper()

    reconhecido = _fabricante_conhecido(upper)
    if reconhecido:
        fabricante, aproximado = reconhecido
        fields.append(
            ParsedField(
                "manufacturer",
                "Fabricante",
                fabricante.title(),
                round(base_confidence - 0.3, 2) if aproximado else base_confidence,
            )
        )

    model = _MODEL.search(text)
    if model:
        fields.append(
            ParsedField("model", "Modelo", model.group(1).strip(), round(base_confidence - 0.1, 2))
        )

    for key, label, pattern in _PATTERNS:
        melhor = _melhor_casamento(pattern, text, key)
        if melhor is None:
            continue
        valor, consertado = melhor
        normalizar = _NORMALIZADORES.get(key)
        fields.append(
            ParsedField(
                key,
                label,
                normalizar(valor) if normalizar else valor,
                # Valor consertado vale menos: a tela pinta em ambar e pede
                # conferencia na placa.
                round(base_confidence - 0.25, 2) if consertado else base_confidence,
            )
        )

    # Potencia em CV/HP convertida para kW quando kW nao foi encontrado.
    if not any(f.field == "power_kw" for f in fields):
        cv = _POWER_CV.search(text)
        if cv:
            kw = float(cv.group(1).replace(",", ".")) * 0.7355
            fields.append(
                ParsedField(
                    "power_kw",
                    "Potência (kW)",
                    f"{kw:.1f}".replace(".", ","),
                    round(base_confidence - 0.15, 2),
                )
            )
    return fields


# ------------------- Coerencia eletrica da propria placa -------------------
# Potencia, tensao e corrente de um motor trifasico se amarram por
# P = raiz(3) . V . I . cos(phi) . rendimento. E o unico juiz disponivel quando
# o valor lido, sozinho, parece perfeitamente plausivel: "75 kW" no lugar de
# "7,5 kW" passa em qualquer checagem de faixa, e vira limiar de vibracao
# errado e ordem de servico errada la na frente.
#
# O produto cos(phi) x rendimento fica perto de 0,75 em motor industrial. A
# banda e larga de proposito: cobre a variacao real e ainda o motor monofasico
# e o de corrente continua, que nao levam o raiz(3) - e mesmo assim denuncia
# folgadamente um erro de uma casa decimal, que e o defeito que se quer pegar.
_FATOR_TIPICO = 0.75
_BANDA_COERENTE = (0.45, 2.2)
# Tolerancia da razao entre as duas correntes de uma placa de dupla tensao.
_TOLERANCIA_RAZAO = 0.15


def _potencia_esperada(tensao: str, corrente: str) -> float | None:
    """Potencia que a tensao e a corrente da placa implicam, em kW."""
    tensoes, correntes = _numeros(tensao), _numeros(corrente)
    if not tensoes or not correntes:
        return None
    # Placa de dupla tensao lista a corrente na mesma ordem: a maior corrente e
    # a da menor tensao. O produto V.I e o mesmo nas duas ligacoes, entao casar
    # a maior tensao com a menor corrente vale para os dois casos.
    return 1.732 * max(tensoes) * min(correntes) * _FATOR_TIPICO / 1000


def _unico(candidatos: set[str], aceitar: "Callable[[str], bool]") -> str | None:
    """O unico candidato aceito, ou None quando ha zero ou mais de um."""
    aceitos = {c for c in candidatos if aceitar(c)}
    return aceitos.pop() if len(aceitos) == 1 else None


def conferir_coerencia_eletrica(fields: list[ParsedField]) -> list[ParsedField]:
    """Corrige ou descarta potencia e corrente que nao fecham com a placa."""
    por_chave = {f.field: f for f in fields}
    tensao = por_chave.get("voltage_v")
    if not (tensao and tensao.value):
        return fields
    tensoes = _numeros(tensao.value)
    saida = list(fields)

    def trocar(chave: str, valor: str | None) -> None:
        """Substitui o valor do campo, ou tira o campo quando valor e None."""
        nonlocal saida
        campo = por_chave[chave]
        if valor is None:
            saida = [f for f in saida if f.field != chave]
            por_chave.pop(chave, None)
            logger.info("campo %s descartado por incoerencia eletrica", chave)
            return
        novo = ParsedField(campo.field, campo.label, valor, round(campo.confidence - 0.25, 2))
        saida = [novo if f.field == chave else f for f in saida]
        por_chave[chave] = novo

    # 1) Dupla tensao: a razao entre as duas correntes e a razao inversa entre
    #    as duas tensoes. Checagem exata da placa contra ela mesma.
    corrente = por_chave.get("nominal_current_a")
    if corrente and corrente.value and len(tensoes) == 2:
        correntes = _numeros(corrente.value)
        if len(correntes) == 2:
            alvo = max(tensoes) / min(tensoes)

            def casa_a_razao(valor: str) -> bool:
                numeros = _numeros(valor)
                if len(numeros) != 2 or min(numeros) <= 0:
                    return False
                return abs(max(numeros) / min(numeros) - alvo) <= alvo * _TOLERANCIA_RAZAO

            if not casa_a_razao(corrente.value):
                trocar(
                    "nominal_current_a",
                    _unico(_com_virgula_reposta(corrente.value), casa_a_razao),
                )

    # 2) P = raiz(3) . V . I . cos(phi) . rendimento
    potencia = por_chave.get("power_kw")
    corrente = por_chave.get("nominal_current_a")
    if not (potencia and potencia.value and corrente and corrente.value):
        return saida
    esperada = _potencia_esperada(tensao.value, corrente.value)
    if not esperada:
        return saida

    def coerente(valor: str) -> bool:
        numeros = _numeros(valor)
        if not numeros:
            return False
        razao = numeros[0] / esperada
        return _BANDA_COERENTE[0] <= razao <= _BANDA_COERENTE[1]

    if not coerente(potencia.value):
        # Tensao e corrente ja passaram por faixa e pela razao da dupla tensao;
        # a potencia nao tem juiz proprio, entao e ela que cede.
        trocar("power_kw", _unico(_com_virgula_reposta(potencia.value), coerente))
    return saida


def _coverage(fields: list[ParsedField]) -> float:
    found = {f.field for f in fields}
    hits = sum(1 for key in EXPECTED_FIELDS if key in found)
    return round(hits / len(EXPECTED_FIELDS), 2)


# ----------------------- Parser generico de placa ------------------------
# Campos rotulados comuns a qualquer placa (nao so motores). O valor pode
# estar na mesma linha do rotulo ou na linha seguinte (\n opcional).
_GENERIC_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "manufacturer",
        "Fabricante",
        re.compile(
            r"(?:FABRICANTE|MANUFACTURER|FABRICANT)\s*[:.]?\s*\n?\s*"
            r"([A-Za-z][\w .,&/\-]{2,48})",
            re.IGNORECASE,
        ),
    ),
    (
        "model",
        "Modelo",
        re.compile(
            r"(?:MACHINE|M[ÁA]QUINA|MODELO|MODEL)\s*[:.]?\s*\n?\s*" r"([A-Za-z0-9][\w .\-/]{1,40})",
            re.IGNORECASE,
        ),
    ),
    (
        "serial_number",
        "Número de série",
        re.compile(
            r"(?:SERIAL|S[ÉE]RIE|N[º°.]?\s*S[ÉE]RIE|SERIAL\s*(?:NO|N[º°]))"
            r"\s*[:.]?\s*\n?\s*([A-Za-z0-9][\w./\-]{2,40})",
            re.IGNORECASE,
        ),
    ),
    (
        "manufacture_date",
        "Data de fabricação",
        re.compile(
            r"(?:DATE|DATA)\s*[:.]?\s*\n?\s*(\d{1,2}[/.\-]\d{2,4}|\d{4})",
            re.IGNORECASE,
        ),
    ),
)

# "MOTOR ELETRICO INDUSTRIAL" e o subtitulo da placa, nao o fabricante - mas
# casa com a dica de empresa por causa do "MOTOR". Sem esta excecao, a linha de
# descricao virava o nome do fabricante do ativo.
_LINHA_DESCRITIVA = re.compile(
    r"\bMOTOR(?:ES)?\b.*\b(?:EL[EÉ]TRICO|TRIF[ÁA]SICO|MONOF[ÁA]SICO|INDU[CÇ][ÃA]O|"
    r"INDUSTRIAL|ASS[IÍ]NCRONO|S[ÍI]NCRONO)\b",
    re.IGNORECASE,
)

# Sufixos que denunciam um nome de empresa numa linha nao rotulada.
_COMPANY_HINT = re.compile(
    r"\b(S\.?p\.?A|S\.?A|LTDA|GMBH|INC|CO|EQUIPMENT|MOTORS?|MOTORES|IND[UÚ]STRIA|"
    r"EQUIPAMENTOS|TECHNOLOG|SISTEMAS)\b",
    re.IGNORECASE,
)


# Campos de TEXTO livre (fabricante, modelo, serie) sao os que mais sofrem com
# ruido: a regex acha o rotulo ("FABRICANTE") e leva junto o lixo que veio
# depois. E o pior tipo de defeito neste sistema, porque o valor vai direto
# para uma coluna do ativo - "cria A ico ce velo ENTS INDUSTRIAL S.A: IO" como
# fabricante e pior do que campo vazio: um humano corrige o vazio, mas confia
# no que ja veio preenchido.
_CAMPOS_DE_TEXTO = frozenset({"manufacturer", "model", "serial_number"})


def _parece_ruido(valor: str) -> bool:
    """Heuristica de lixo de OCR para campo de texto curto.

    Nome de fabricante ou modelo e curto e denso. Leitura ruim vira uma cadeia
    longa de fragmentos de 1-2 letras, com muito simbolo solto no meio.
    """
    palavras = valor.split()
    if not palavras:
        return True
    # Placa nao tem fabricante com 5+ palavras.
    if len(palavras) > 4:
        return True
    # Muitos fragmentos minusculos = OCR picotando letra solta.
    fragmentos = sum(1 for palavra in palavras if len(palavra) <= 2)
    if fragmentos >= 2:
        return True
    # Densidade: pouca letra/digito no meio de simbolo e ruido.
    uteis = sum(1 for c in valor if c.isalnum() or c.isspace())
    if uteis / len(valor) < 0.75:
        return True
    return False


def parse_generic_fields(text: str, base_confidence: float) -> list[ParsedField]:
    """Extrai campos genericos de placa (fabricante, modelo, serie, data).

    Cobre equipamentos que nao sao motores. Se o fabricante nao vier rotulado,
    usa a primeira linha que se pareca com um nome de empresa (confianca menor).
    """
    fields: list[ParsedField] = []
    seen: set[str] = set()

    for key, label, pattern in _GENERIC_PATTERNS:
        match = pattern.search(text)
        if match:
            value = " ".join(match.group(1).split()).strip(" .,-")
            if key in _CAMPOS_DE_TEXTO and _parece_ruido(value):
                # Melhor campo ausente do que valor inventado: quem revisa
                # preenche o que falta, mas nao desconfia do que ja veio.
                logger.debug("valor descartado por ruido em %s: %r", key, value)
                continue
            if value:
                fields.append(ParsedField(key, label, value, round(base_confidence - 0.05, 2)))
                seen.add(key)

    # Fabricante nao rotulado: 1a linha com cara de nome de empresa.
    if "manufacturer" not in seen:
        for line in (ln.strip() for ln in text.splitlines()):
            if not (3 <= len(line) <= 48) or _LINHA_DESCRITIVA.search(line):
                continue
            if _COMPANY_HINT.search(line):
                fields.append(
                    ParsedField("manufacturer", "Fabricante", line, round(base_confidence - 0.2, 2))
                )
                break

    return fields


def merge_fields(*groups: list[ParsedField]) -> list[ParsedField]:
    """Combina grupos de campos, mantendo a primeira ocorrencia de cada chave."""
    out: list[ParsedField] = []
    seen: set[str] = set()
    for group in groups:
        for field in group:
            if field.field not in seen:
                out.append(field)
                seen.add(field.field)
    return out


# --------------------------- Motor de OCR --------------------------------
class PaddleOcrEngine:
    """Motor de OCR baseado em PaddleOCR (extra opcional ``ocr``)."""

    def __init__(self) -> None:
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

    def read_text(self, image: Image.Image) -> tuple[str, float]:
        import numpy as np

        result = self._ocr.ocr(np.array(image), cls=True)
        lines: list[str] = []
        confidences: list[float] = []
        for page in result or []:
            for entry in page or []:
                text, conf = entry[1]
                lines.append(str(text))
                confidences.append(float(conf))
        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return "\n".join(lines), mean


class TesseractEngine:
    """Motor de OCR baseado no Tesseract (pytesseract + binario do sistema)."""

    def __init__(self) -> None:
        import pytesseract

        self._pt = pytesseract
        # Falha aqui (binario ausente) faz get_ocr_engine cair para None.
        pytesseract.get_tesseract_version()

    def _read(self, image: "Image.Image", config: str) -> tuple[str, float]:
        """Uma passada do tesseract, reconstruindo o texto por linha."""
        # Portugues + ingles; falha de idioma recai para o default do sistema.
        try:
            data = self._pt.image_to_data(
                image, lang="por+eng", config=config, output_type=self._pt.Output.DICT
            )
        except Exception:
            data = self._pt.image_to_data(
                image, config=config, output_type=self._pt.Output.DICT
            )

        lines: dict[tuple[int, int, int], list[str]] = {}
        confidences: list[float] = []
        for i, word in enumerate(data["text"]):
            token = word.strip()
            conf = float(data["conf"][i])
            if not token or conf < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            lines.setdefault(key, []).append(token)
            confidences.append(conf / 100.0)

        text = "\n".join(" ".join(words) for words in lines.values())
        mean = sum(confidences) / len(confidences) if confidences else 0.0
        return text, mean

    def read_text(self, image: "Image.Image") -> tuple[str, float]:
        """Le a placa, com uma segunda tentativa quando a primeira vem vazia.

        O modo padrao (PSM 3, analise de layout de PAGINA) as vezes conclui que
        uma placa muito degradada - girada, desfocada - nao tem bloco de texto
        valido e devolve ZERO palavras, o que vira "cobertura 0%" na tela. Nesses
        casos o PSM 6 ("um unico bloco uniforme de texto"), que descreve melhor
        uma placa, ainda consegue ler.

        O PSM 6 entra so como SEGUNDA tentativa, nunca como padrao: medido sobre
        as placas de assets/nameplates_samples em variantes giradas e desfocadas,
        troca-lo por padrao resgata os casos vazios mas PIORA varios que hoje
        acertam. Como fallback, o caminho que ja funciona fica intacto.
        """
        text, mean = self._read(image, config="")
        if text.strip():
            return text, mean
        return self._read(image, config="--psm 6")


@lru_cache(maxsize=1)
def get_ocr_engine() -> TesseractEngine | PaddleOcrEngine | None:
    """Carrega o motor de OCR uma unica vez; ``None`` se nenhum disponivel."""
    try:
        return TesseractEngine()
    except Exception as exc:
        logger.info("Tesseract indisponivel (%s); tentando PaddleOCR", exc)
    try:
        return PaddleOcrEngine()
    except Exception as exc:
        logger.warning("Nenhum motor de OCR disponivel (%s)", exc)
        return None


def extract_nameplate(raw: bytes) -> ExtractionResult:
    """Executa o pipeline completo: pre-processa, faz OCR e parseia a placa.

    Sem motor de OCR disponivel, devolve um resultado vazio e honesto
    (engine ``indisponivel``) - nunca preenche com dados fabricados.
    """
    image = preprocess_image(raw)  # valida que os bytes sao uma imagem
    engine = get_ocr_engine()
    if engine is None:
        return ExtractionResult(engine="indisponivel", raw_text="", fields=[], coverage=0.0)

    engine_name = "tesseract" if isinstance(engine, TesseractEngine) else "paddleocr"

    def _tentar(imagem: Image.Image) -> ExtractionResult:
        text, mean_conf = engine.read_text(imagem)
        base = round(max(mean_conf, 0.3), 2)
        fields = conferir_coerencia_eletrica(
            merge_fields(
                parse_nameplate_text(text, base_confidence=base),
                parse_generic_fields(text, base_confidence=base),
            )
        )
        return ExtractionResult(
            engine=engine_name, raw_text=text, fields=fields, coverage=_coverage(fields)
        )

    resultado = _tentar(image)
    if resultado.coverage >= _COBERTURA_ACEITAVEL:
        return resultado

    # Leitura fraca: pode ser iluminacao desigual. Uma segunda passada com
    # limiar adaptativo, ficando com a melhor das duas — assim o caminho que ja
    # funcionava nunca piora, e so a foto ruim paga o tempo extra.
    alternativa = _tentar(preprocess_adaptativo(raw))
    return alternativa if alternativa.coverage > resultado.coverage else resultado
