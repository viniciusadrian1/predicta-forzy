"""Logging estruturado em JSON para toda a aplicacao.

Cada registro vira uma linha JSON em stdout, pronto para coleta por Loki /
ELK. Campos adicionais podem ser anexados via ``logger.info(..., extra={...})``.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

# Campos extras reconhecidos e promovidos ao corpo do log.
_EXTRA_KEYS = frozenset(
    {
        "request_id",
        "method",
        "path",
        "status_code",
        "duration_ms",
        "actor",
        "resource_type",
        "resource_id",
        "event",
        "asset_tag",
    }
)


class JsonFormatter(logging.Formatter):
    """Formata cada ``LogRecord`` como uma unica linha JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _EXTRA_KEYS:
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Configura o root logger para emitir JSON estruturado em stdout."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Reduz o ruido de bibliotecas verbosas.
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
