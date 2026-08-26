"""Workflow de RPA: cadastro de ativo a partir da foto da placa.

Etapas: OCR da placa -> pre-preenchimento do rascunho -> deduplicacao por
TAG -> (opcional) criacao automatica -> evento de auditoria.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.modules.assets.models import Asset
from app.modules.assets.repository import AssetRepository
from app.modules.automation.schemas import AssetDraft, RpaRegisterResult
from app.modules.vision.plate_ocr import ParsedField, extract_nameplate
from app.modules.vision.schemas import NameplateField

logger = logging.getLogger("forzy.automation.rpa")


def _to_float(value: str | None) -> float | None:
    """Converte um valor textual da placa em float (usa o primeiro de '220/380')."""
    if not value:
        return None
    token = value.replace(" ", "").split("/")[0].replace(",", ".")
    try:
        return float(token)
    except ValueError:
        return None


def _to_int(value: str | None) -> int | None:
    parsed = _to_float(value)
    return int(parsed) if parsed is not None else None


def _build_draft(tag: str | None, fields: list[ParsedField]) -> AssetDraft:
    """Mapeia os campos extraidos pelo OCR para um rascunho de ativo."""
    by_key = {field.field: field.value for field in fields}
    return AssetDraft(
        tag=tag,
        manufacturer=by_key.get("manufacturer"),
        model=by_key.get("model"),
        power_kw=_to_float(by_key.get("power_kw")),
        voltage_v=_to_float(by_key.get("voltage_v")),
        nominal_current_a=_to_float(by_key.get("nominal_current_a")),
        nominal_rpm=_to_int(by_key.get("nominal_rpm")),
        ip_rating=by_key.get("ip_rating"),
        insulation_class=by_key.get("insulation_class"),
    )


class RpaService:
    """Orquestra o fluxo de cadastro automatizado a partir de imagem."""

    def __init__(self, repository: AssetRepository) -> None:
        self._repo = repository

    async def register_from_image(
        self,
        raw: bytes,
        tag: str | None,
        auto_create: bool,
        actor: str,
        image_source: str | None = None,
        visual_condition: str | None = None,
    ) -> RpaRegisterResult:
        # 1. OCR da placa.
        extraction = extract_nameplate(raw)
        fields = [
            NameplateField(
                field=field.field,
                label=field.label,
                value=field.value,
                confidence=field.confidence,
            )
            for field in extraction.fields
        ]

        # 2. Pre-preenche o rascunho de cadastro.
        draft = _build_draft(tag, extraction.fields)

        # 3. Deduplicacao por TAG.
        duplicate = False
        created = False
        if extraction.engine == "indisponivel":
            message = (
                "OCR indisponível no servidor - nenhum dado extraído. "
                "Preencha os campos manualmente."
            )
        elif not extraction.fields:
            message = (
                "Nenhum campo reconhecido na imagem. Revise a foto ou "
                "preencha os campos manualmente."
            )
        else:
            message = "Rascunho gerado a partir do OCR; revise antes de cadastrar."
        if tag:
            existing = await self._repo.get_asset_by_tag(tag)
            if existing is not None:
                duplicate = True
                message = f"Já existe um ativo com a TAG '{tag}' (cadastro ignorado)."
            elif auto_create:
                # Metadados de rastreabilidade (governanca): o cadastro nasce como
                # 'ia_gerado' e PENDENTE de validacao humana (validated_by nulo) -
                # sinaliza revisao quando o score do OCR e baixo.
                await self._repo.add_asset(
                    Asset(
                        tag=tag,
                        asset_type="motor",
                        manufacturer=draft.manufacturer,
                        model=draft.model,
                        power_kw=draft.power_kw,
                        voltage_v=draft.voltage_v,
                        nominal_current_a=draft.nominal_current_a,
                        nominal_rpm=draft.nominal_rpm,
                        ip_rating=draft.ip_rating,
                        insulation_class=draft.insulation_class,
                        status="unknown",
                        data_origin="ia_gerado",
                        registration_photo_at=datetime.now(UTC),
                        ocr_engine_version=extraction.engine,
                        ocr_confidence=round(extraction.coverage, 2),
                        image_source=image_source,
                        visual_condition=visual_condition,
                    )
                )
                created = True
                message = f"Ativo '{tag}' cadastrado automaticamente via RPA."

        # 4. Evento de auditoria (log estruturado).
        logger.info(
            "rpa_register",
            extra={
                "event": "rpa_register",
                "actor": actor,
                "asset_tag": tag or "-",
                "resource_type": "assets",
            },
        )

        return RpaRegisterResult(
            ocr_engine=extraction.engine,
            ocr_coverage=extraction.coverage,
            fields=fields,
            draft=draft,
            duplicate=duplicate,
            created=created,
            message=message,
        )
