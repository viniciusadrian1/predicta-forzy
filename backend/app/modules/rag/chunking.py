"""Fragmentacao (chunking) de documentos para indexacao no RAG.

O chunker e consciente de paragrafos: agrupa paragrafos inteiros ate o
limite de tamanho e mantem o ultimo paragrafo como sobreposicao com o
proximo chunk, preservando contexto nas fronteiras.
"""

from __future__ import annotations

import re

_PARAGRAPH_RE = re.compile(r"\n\s*\n")


def _split_paragraphs(text: str) -> list[str]:
    """Separa o texto em paragrafos nao vazios."""
    return [block.strip() for block in _PARAGRAPH_RE.split(text.strip()) if block.strip()]


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Fragmenta o texto em chunks de ate ``chunk_size`` caracteres.

    Paragrafos maiores que o limite sao fatiados diretamente com
    sobreposicao; os demais sao agrupados preservando a unidade de
    paragrafo.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size deve ser positivo.")
    overlap = max(0, min(overlap, chunk_size // 2))

    chunks: list[str] = []
    buffer: list[str] = []
    length = 0

    def flush() -> None:
        nonlocal buffer, length
        if buffer:
            chunks.append("\n\n".join(buffer).strip())
            buffer, length = [], 0

    for paragraph in _split_paragraphs(text):
        if len(paragraph) > chunk_size:
            flush()
            step = max(chunk_size - overlap, 1)
            for start in range(0, len(paragraph), step):
                chunks.append(paragraph[start : start + chunk_size].strip())
            continue

        if buffer and length + len(paragraph) > chunk_size:
            tail = buffer[-1]
            flush()
            # mantem o ultimo paragrafo curto como contexto de sobreposicao
            if len(tail) <= overlap * 2:
                buffer, length = [tail], len(tail)

        buffer.append(paragraph)
        length += len(paragraph) + 2

    flush()
    return [chunk for chunk in chunks if chunk]
