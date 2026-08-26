"""Geracao do PDF inteligente da planta (reportlab).

Produz um PDF de uma pagina com a planta esquematica, um marcador por ativo
com o snapshot da telemetria e um link clicavel que abre o ativo no frontend.
"""

from __future__ import annotations

import io
from typing import Any

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.modules.assets.models import Asset, Plant

# Fallback se o chamador nao informar a URL do frontend.
_DEFAULT_FRONTEND_BASE_URL = "http://localhost:3000"


def build_plant_pdf(
    plant: Plant,
    assets: list[Asset],
    latest_by_tag: dict[str, list[dict[str, Any]]],
    frontend_base_url: str = _DEFAULT_FRONTEND_BASE_URL,
) -> bytes:
    """Gera o PDF interativo da planta e devolve os bytes.

    ``frontend_base_url`` e a base dos links clicaveis (abrem o ativo no
    frontend real); vem da config (``resolved_frontend_base_url``).
    """
    base_url = (frontend_base_url or _DEFAULT_FRONTEND_BASE_URL).rstrip("/")
    buffer = io.BytesIO()
    page = landscape(A4)
    width, height = page
    pdf = canvas.Canvas(buffer, pagesize=page)
    pdf.setTitle(f"Predicta - Planta {plant.name}")

    # Cabecalho.
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(20 * mm, height - 20 * mm, f"Planta {plant.name} ({plant.code})")
    pdf.setFont("Helvetica", 9)
    pdf.drawString(
        20 * mm,
        height - 26 * mm,
        "PDF interativo - clique em um equipamento para abrir o ativo no sistema.",
    )

    # Area da planta.
    plan_x, plan_y = 20 * mm, 18 * mm
    plan_w, plan_h = width - 40 * mm, height - 52 * mm
    pdf.setStrokeColorRGB(0.40, 0.45, 0.52)
    pdf.setLineWidth(1.2)
    pdf.rect(plan_x, plan_y, plan_w, plan_h)
    pdf.setFillColorRGB(0.45, 0.48, 0.55)
    pdf.setFont("Helvetica-Oblique", 9)
    pdf.drawString(plan_x + 3 * mm, plan_y + plan_h - 6 * mm, "Sala de Bombas")

    # Marcadores de ativos.
    for asset in assets:
        pos_x = asset.position_x if asset.position_x is not None else 0.5
        pos_y = asset.position_y if asset.position_y is not None else 0.5
        center_x = plan_x + pos_x * plan_w
        center_y = plan_y + (1.0 - pos_y) * plan_h  # position_y e top-down

        box_w, box_h = 48 * mm, 28 * mm
        box_x, box_y = center_x - box_w / 2, center_y - box_h / 2
        pdf.setFillColorRGB(0.10, 0.14, 0.22)
        pdf.setStrokeColorRGB(0.30, 0.78, 0.85)
        pdf.setLineWidth(1.0)
        pdf.rect(box_x, box_y, box_w, box_h, stroke=1, fill=1)

        pdf.setFillColorRGB(0.92, 0.94, 0.96)
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawCentredString(center_x, box_y + box_h - 7 * mm, asset.tag)

        # Snapshot da telemetria (anotacoes com valores instantaneos).
        pdf.setFont("Helvetica", 7)
        pdf.setFillColorRGB(0.66, 0.72, 0.80)
        text_y = box_y + box_h - 12 * mm
        for reading in latest_by_tag.get(asset.tag, [])[:4]:
            label = f"{reading['variable']}: {reading['value']} {reading['unit']}"
            pdf.drawCentredString(center_x, text_y, label)
            text_y -= 3.8 * mm

        # Link clicavel sobre o equipamento.
        pdf.linkURL(
            f"{base_url}/asset/{asset.tag}",
            (box_x, box_y, box_x + box_w, box_y + box_h),
            relative=0,
            thickness=0,
        )

    pdf.setFillColorRGB(0.45, 0.48, 0.55)
    pdf.setFont("Helvetica", 7)
    pdf.drawString(20 * mm, 10 * mm, "Gerado por Predicta - Sprint 2")

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
