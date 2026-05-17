"""Embeddings deterministicos por hashing para o RAG.

Implementa o *hashing trick*: cada token (e bigrama) e projetado em um
vetor de dimensao fixa via hash criptografico, com peso TF sublinear e
sinal derivado do proprio hash. O vetor resultante e L2-normalizado, de
modo que a similaridade de cosseno se reduz ao produto escalar.

Escolha deliberada do MVP (ver ADR 0006): nao exige modelo externo nem
download de pesos, e totalmente offline, reproduzivel e leve. Para
producao recomenda-se um modelo semantico (sentence-transformers / ONNX).
"""

from __future__ import annotations

import hashlib
import math
import re
import unicodedata
from collections.abc import Iterable

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Stopwords PT/EN de alta frequencia - reduzem ruido sem NLP pesado.
_STOPWORDS = frozenset(
    {
        "a",
        "o",
        "as",
        "os",
        "um",
        "uma",
        "de",
        "da",
        "do",
        "das",
        "dos",
        "e",
        "ou",
        "em",
        "no",
        "na",
        "nos",
        "nas",
        "para",
        "por",
        "com",
        "sem",
        "que",
        "se",
        "ao",
        "aos",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "is",
        "are",
        "be",
        "at",
        "an",
        "este",
        "esta",
        "isso",
        "seu",
        "sua",
        "mais",
        "como",
        "foi",
        "ser",
        "tem",
    }
)


def _strip_accents(text: str) -> str:
    """Remove acentos para tornar o casamento de tokens robusto."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str) -> list[str]:
    """Normaliza e tokeniza o texto, descartando stopwords e tokens curtos."""
    tokens = _TOKEN_RE.findall(_strip_accents(text).lower())
    return [token for token in tokens if len(token) > 2 and token not in _STOPWORDS]


class HashingEmbedder:
    """Gera embeddings deterministicos por hashing de tokens e bigramas."""

    def __init__(self, dim: int = 384) -> None:
        if dim < 16:
            raise ValueError("A dimensao do embedding deve ser >= 16.")
        self.dim = dim

    def _project(self, term: str) -> tuple[int, float]:
        """Projeta um termo em (indice, sinal) de forma deterministica."""
        digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
        value = int.from_bytes(digest, "big")
        index = value % self.dim
        sign = 1.0 if (value >> 1) & 1 else -1.0
        return index, sign

    def embed(self, text: str) -> list[float]:
        """Devolve o embedding L2-normalizado do texto."""
        vector = [0.0] * self.dim
        tokens = tokenize(text)
        if not tokens:
            return vector

        # Termos unitarios com peso TF sublinear (1 + log(frequencia)).
        counts: dict[str, int] = {}
        for token in tokens:
            counts[token] = counts.get(token, 0) + 1
        for token, count in counts.items():
            index, sign = self._project(token)
            vector[index] += sign * (1.0 + math.log(count))

        # Bigramas dao um pouco de contexto de frase, com peso menor.
        for left, right in zip(tokens, tokens[1:], strict=False):
            index, sign = self._project(f"{left}_{right}")
            vector[index] += sign * 0.5

        norm = math.sqrt(sum(component * component for component in vector))
        if norm > 0.0:
            vector = [component / norm for component in vector]
        return vector

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        """Embeddings de uma colecao de textos."""
        return [self.embed(text) for text in texts]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Similaridade de cosseno entre vetores ja L2-normalizados."""
    return sum(x * y for x, y in zip(left, right, strict=False))
