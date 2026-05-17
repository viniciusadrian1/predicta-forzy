"""Carga da base de conhecimento do RAG.

O corpus curado vive em ``corpus/`` dentro deste pacote (markdown), o que
garante que o assistente funcione em qualquer ambiente sem montagem de
volumes. Documentos adicionais (``.md``, ``.txt``, ``.pdf``) podem ser
deixados no diretorio ``RAG_DOCUMENTS_DIR`` e sao ingeridos quando presentes.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("forzy.rag.knowledge_base")

_CORPUS_DIR = Path(__file__).parent / "corpus"
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)


@dataclass
class Document:
    """Documento da base de conhecimento."""

    id: str
    title: str
    text: str
    source: str  # "corpus" (empacotado) | "documents" (externo)


def _title_of(text: str, fallback: str) -> str:
    """Extrai o titulo do primeiro cabecalho markdown, ou usa o fallback."""
    match = _HEADING_RE.search(text)
    return match.group(1).strip() if match else fallback


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _load_text_file(path: Path, source: str) -> Document | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Falha ao ler %s: %s", path.name, exc)
        return None
    if not text.strip():
        return None
    return Document(id=_slug(path.stem), title=_title_of(text, path.stem), text=text, source=source)


def _load_pdf_file(path: Path) -> Document | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.info("pypdf indisponivel; PDF %s ignorado.", path.name)
        return None
    try:
        reader = PdfReader(str(path))
        text = "\n\n".join((page.extract_text() or "").strip() for page in reader.pages)
    except Exception as exc:  # pragma: no cover - depende do PDF
        logger.warning("Falha ao extrair texto de %s: %s", path.name, exc)
        return None
    if not text.strip():
        logger.info("PDF %s sem texto extraivel; ignorado.", path.name)
        return None
    return Document(id=_slug(path.stem), title=path.stem, text=text, source="documents")


def load_documents(documents_dir: str | None = None) -> list[Document]:
    """Carrega o corpus empacotado e, se houver, os documentos externos."""
    documents: list[Document] = []

    for path in sorted(_CORPUS_DIR.glob("*.md")):
        document = _load_text_file(path, source="corpus")
        if document is not None:
            documents.append(document)

    if documents_dir:
        external = Path(documents_dir)
        if external.is_dir():
            for path in sorted(external.iterdir()):
                suffix = path.suffix.lower()
                if suffix in {".md", ".txt"}:
                    document = _load_text_file(path, source="documents")
                elif suffix == ".pdf":
                    document = _load_pdf_file(path)
                else:
                    continue
                if document is not None:
                    documents.append(document)

    logger.info("RAG: %d documento(s) carregado(s) na base de conhecimento.", len(documents))
    return documents
