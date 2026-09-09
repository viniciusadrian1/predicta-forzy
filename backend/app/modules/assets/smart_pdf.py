"""Geracao do PDF inteligente da planta (reportlab).

Uma pagina paisagem com a planta esquematica, um cartao por EQUIPAMENTO com o
snapshot da telemetria e um link clicavel que abre o ativo no frontend.

O visual segue a identidade do produto (fundo escuro, cartoes, trilho de status
colorido) para o PDF nao parecer de outro sistema quando impresso ou
compartilhado ao lado das telas.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any

from reportlab.lib.colors import Color, HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.modules.assets.models import Asset, Plant

# Fallback se o chamador nao informar a URL do frontend.
_DEFAULT_FRONTEND_BASE_URL = "http://localhost:3000"

# Paleta do produto (mesma do frontend: slate-950/900/800 + ciano de acento).
BG = HexColor("#0B1220")
PANEL = HexColor("#0F172A")
CARD = HexColor("#131D30")
BORDER = HexColor("#1E293B")
TEXT = HexColor("#E2E8F0")
MUTED = HexColor("#94A3B8")
FAINT = HexColor("#64748B")
ACCENT = HexColor("#22D3EE")

STATUS_COLOR: dict[str, Color] = {
    "ok": HexColor("#22C55E"),
    "warning": HexColor("#F59E0B"),
    "critical": HexColor("#EF4444"),
    "unknown": HexColor("#64748B"),
}
STATUS_LABEL = {
    "ok": "Operacional",
    "warning": "Atencao",
    "critical": "Critico",
    "unknown": "Sem dados",
}

# Rotulos curtos: o nome cru da variavel nao cabe no cartao.
VARIABLE_LABEL = {
    "Vibracao_Velocidade_RMS": "Vibracao",
    "Vibracao_Aceleracao_RMS": "Aceleracao",
    "Temperatura": "Temperatura",
    "Corrente": "Corrente",
    "Tensao": "Tensao",
    "Rotacao": "Rotacao",
}


def _fmt_reading(reading: dict[str, Any]) -> str:
    """Uma leitura em uma linha curta: 'Vibracao 1,23 mm/s'."""
    label = VARIABLE_LABEL.get(reading["variable"], reading["variable"])
    value = reading["value"]
    text = f"{value:.2f}".rstrip("0").rstrip(".") if isinstance(value, float) else str(value)
    return f"{label} {text.replace('.', ',')} {reading.get('unit', '')}".strip()


def _card(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    w: float,
    h: float,
    status: str,
) -> None:
    """Cartao do equipamento: fundo, borda e trilho de status a esquerda."""
    pdf.setFillColor(CARD)
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(0.8)
    pdf.roundRect(x, y, w, h, 2.2 * mm, stroke=1, fill=1)
    # Trilho de status (o mesmo recurso visual dos cartoes do app).
    pdf.setFillColor(STATUS_COLOR.get(status, STATUS_COLOR["unknown"]))
    pdf.roundRect(x, y, 1.6 * mm, h, 0.8 * mm, stroke=0, fill=1)


def build_plant_pdf(
    plant: Plant,
    assets: list[Asset],
    latest_by_tag: dict[str, list[dict[str, Any]]],
    frontend_base_url: str = _DEFAULT_FRONTEND_BASE_URL,
) -> bytes:
    """Gera o PDF interativo da planta e devolve os bytes.

    ``assets`` pode conter pontos de medicao (``parent_tag`` preenchido). Eles
    NAO viram cartao proprio: entram no cartao do equipamento que os agrupa,
    exatamente como na planta da tela - senao o PDF mostraria dois "motores"
    onde existe um conjunto com dois mancais.
    """
    base_url = (frontend_base_url or _DEFAULT_FRONTEND_BASE_URL).rstrip("/")
    buffer = io.BytesIO()
    page = landscape(A4)
    width, height = page
    pdf = canvas.Canvas(buffer, pagesize=page)
    pdf.setTitle(f"Predicta - Planta {plant.name}")

    # --- Fundo -------------------------------------------------------------
    pdf.setFillColor(BG)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)

    # --- Cabecalho ---------------------------------------------------------
    cursor_h = 18 * mm
    pdf.setFillColor(ACCENT)
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(cursor_h, height - 16 * mm, "PREDICTA")
    # Avanca pela largura MEDIDA do wordmark: offset fixo sobrepunha o nome.
    cursor_h += pdf.stringWidth("PREDICTA", "Helvetica-Bold", 15) + 4 * mm
    pdf.setFillColor(TEXT)
    pdf.drawString(cursor_h, height - 16 * mm, plant.name)
    cursor_h += pdf.stringWidth(plant.name, "Helvetica-Bold", 15) + 3 * mm
    pdf.setFillColor(FAINT)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(cursor_h, height - 16 * mm, plant.code)
    pdf.setFillColor(MUTED)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(
        18 * mm,
        height - 21 * mm,
        "Planta interativa - clique em um equipamento para abri-lo no sistema.",
    )
    gerado = datetime.now(UTC).strftime("%d/%m/%Y %H:%M UTC")
    pdf.setFillColor(FAINT)
    pdf.setFont("Helvetica", 8)
    pdf.drawRightString(width - 18 * mm, height - 16 * mm, f"Gerado em {gerado}")

    # Regua fina de acento sob o cabecalho.
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(0.8)
    pdf.line(18 * mm, height - 25 * mm, width - 18 * mm, height - 25 * mm)

    # --- Area da planta ----------------------------------------------------
    side_w = 72 * mm
    plan_x, plan_y = 18 * mm, 22 * mm
    plan_w = width - 36 * mm - side_w - 6 * mm
    plan_h = height - 53 * mm
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(1.0)
    pdf.roundRect(plan_x, plan_y, plan_w, plan_h, 3 * mm, stroke=1, fill=1)

    # Malha discreta: sem ela a area de planta le como caixa vazia.
    pdf.setStrokeColor(HexColor("#16233A"))
    pdf.setLineWidth(0.4)
    passo = 12 * mm
    coluna = plan_x + passo
    while coluna < plan_x + plan_w - 1 * mm:
        pdf.line(coluna, plan_y + 1 * mm, coluna, plan_y + plan_h - 1 * mm)
        coluna += passo
    linha_y = plan_y + passo
    while linha_y < plan_y + plan_h - 1 * mm:
        pdf.line(plan_x + 1 * mm, linha_y, plan_x + plan_w - 1 * mm, linha_y)
        linha_y += passo

    pdf.setFillColor(FAINT)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(plan_x + 5 * mm, plan_y + plan_h - 7 * mm, "SALA DE BOMBAS")

    # --- Um cartao por EQUIPAMENTO ----------------------------------------
    points_by_parent: dict[str, list[Asset]] = {}
    for asset in assets:
        if asset.parent_tag:
            points_by_parent.setdefault(asset.parent_tag, []).append(asset)
    equipamentos = [a for a in assets if not a.parent_tag]

    for asset in equipamentos:
        points = points_by_parent.get(asset.tag, [])
        # Sem posicao propria (conjunto), fica no meio dos seus pontos.
        located = [asset] if asset.position_x is not None else points
        with_pos = [a for a in located if a.position_x is not None and a.position_y is not None]
        if not with_pos:
            continue
        pos_x = sum(a.position_x or 0 for a in with_pos) / len(with_pos)
        pos_y = sum(a.position_y or 0 for a in with_pos) / len(with_pos)
        center_x = plan_x + pos_x * plan_w
        center_y = plan_y + (1.0 - pos_y) * plan_h  # position_y e top-down

        # As leituras vem dos pontos de medicao quando eles existem.
        sources = points or [asset]
        linhas: list[tuple[str | None, list[str]]] = []
        for source in sources:
            leituras = [_fmt_reading(r) for r in latest_by_tag.get(source.tag, [])[:3]]
            if leituras:
                rotulo = source.name if len(sources) > 1 else None
                linhas.append((rotulo, leituras))

        n_linhas = sum(len(v) + (1 if r else 0) for r, v in linhas)
        box_w = 58 * mm
        box_h = max(24 * mm, (16 + 4.4 * n_linhas) * mm)
        box_x = max(plan_x + 2 * mm, min(center_x - box_w / 2, plan_x + plan_w - box_w - 2 * mm))
        box_y = max(plan_y + 2 * mm, min(center_y - box_h / 2, plan_y + plan_h - box_h - 8 * mm))

        _card(pdf, box_x, box_y, box_w, box_h, asset.status)

        text_x = box_x + 5 * mm
        cursor = box_y + box_h - 6.5 * mm

        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(text_x, cursor, asset.tag)
        # Pastilha de status a direita do titulo.
        cor = STATUS_COLOR.get(asset.status, STATUS_COLOR["unknown"])
        rotulo = STATUS_LABEL.get(asset.status, asset.status)
        pill_w = pdf.stringWidth(rotulo, "Helvetica-Bold", 6.5) + 4 * mm
        pdf.setFillColor(cor)
        pdf.roundRect(
            box_x + box_w - pill_w - 4 * mm, cursor - 0.8 * mm, pill_w, 4.2 * mm,
            2.1 * mm, stroke=0, fill=1,
        )
        pdf.setFillColor(BG)
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawCentredString(
            box_x + box_w - pill_w / 2 - 4 * mm, cursor + 0.6 * mm, rotulo
        )
        cursor -= 4.6 * mm

        if asset.name:
            pdf.setFillColor(MUTED)
            pdf.setFont("Helvetica", 7.5)
            nome = asset.name if len(asset.name) <= 46 else asset.name[:45] + "…"
            pdf.drawString(text_x, cursor, nome)
            cursor -= 4.6 * mm

        for rotulo_ponto, leituras in linhas:
            if rotulo_ponto:
                pdf.setFillColor(FAINT)
                pdf.setFont("Helvetica-Bold", 6.5)
                curto = rotulo_ponto.split("—")[-1].strip()
                pdf.drawString(text_x, cursor, curto.upper()[:38])
                cursor -= 4 * mm
            pdf.setFillColor(TEXT)
            pdf.setFont("Helvetica", 7.5)
            for linha in leituras:
                pdf.drawString(text_x, cursor, linha)
                cursor -= 4.2 * mm

        # Link clicavel sobre o cartao inteiro.
        pdf.linkURL(
            f"{base_url}/asset/{asset.tag}",
            (box_x, box_y, box_x + box_w, box_y + box_h),
            relative=0,
            thickness=0,
        )

    # --- Painel lateral: resumo da planta ----------------------------------
    side_x = plan_x + plan_w + 6 * mm
    pdf.setFillColor(PANEL)
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(1.0)
    pdf.roundRect(side_x, plan_y, side_w, plan_h, 3 * mm, stroke=1, fill=1)

    sy = plan_y + plan_h - 7 * mm
    pdf.setFillColor(FAINT)
    pdf.setFont("Helvetica-Bold", 8)
    pdf.drawString(side_x + 5 * mm, sy, "RESUMO DA PLANTA")
    sy -= 8 * mm

    pontos = [a for a in assets if a.parent_tag]
    por_status: dict[str, int] = {}
    for equipamento in equipamentos:
        por_status[equipamento.status] = por_status.get(equipamento.status, 0) + 1

    for rotulo, valor in (
        ("Equipamentos", len(equipamentos)),
        ("Pontos de medicao", len(pontos)),
    ):
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(side_x + 5 * mm, sy, rotulo)
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawRightString(side_x + side_w - 5 * mm, sy - 0.6 * mm, str(valor))
        sy -= 6.5 * mm

    sy -= 2 * mm
    pdf.setStrokeColor(BORDER)
    pdf.setLineWidth(0.6)
    pdf.line(side_x + 5 * mm, sy, side_x + side_w - 5 * mm, sy)
    sy -= 7 * mm

    for chave in ("critical", "warning", "ok", "unknown"):
        if not por_status.get(chave):
            continue
        pdf.setFillColor(STATUS_COLOR[chave])
        pdf.circle(side_x + 6 * mm, sy + 1 * mm, 1.3 * mm, stroke=0, fill=1)
        pdf.setFillColor(MUTED)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(side_x + 9.5 * mm, sy, STATUS_LABEL[chave])
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawRightString(side_x + side_w - 5 * mm, sy, str(por_status[chave]))
        sy -= 5.5 * mm

    sy -= 3 * mm
    pdf.setStrokeColor(BORDER)
    pdf.line(side_x + 5 * mm, sy, side_x + side_w - 5 * mm, sy)
    sy -= 7 * mm

    pdf.setFillColor(FAINT)
    pdf.setFont("Helvetica-Bold", 7.5)
    pdf.drawString(side_x + 5 * mm, sy, "EQUIPAMENTOS")
    sy -= 6 * mm

    for equipamento in equipamentos:
        if sy < plan_y + 6 * mm:
            break
        pdf.setFillColor(STATUS_COLOR.get(equipamento.status, STATUS_COLOR["unknown"]))
        pdf.circle(side_x + 6 * mm, sy + 1 * mm, 1.1 * mm, stroke=0, fill=1)
        pdf.setFillColor(TEXT)
        pdf.setFont("Helvetica-Bold", 8)
        pdf.drawString(side_x + 9.5 * mm, sy, equipamento.tag)
        seus_pontos = points_by_parent.get(equipamento.tag, [])
        if seus_pontos:
            pdf.setFillColor(FAINT)
            pdf.setFont("Helvetica", 7)
            pdf.drawRightString(
                side_x + side_w - 5 * mm, sy, f"{len(seus_pontos)} pontos"
            )
        sy -= 4.2 * mm
        if equipamento.name:
            pdf.setFillColor(FAINT)
            pdf.setFont("Helvetica", 7)
            nome = equipamento.name
            while pdf.stringWidth(nome, "Helvetica", 7) > side_w - 15 * mm and len(nome) > 4:
                nome = nome[:-2]
            pdf.drawString(side_x + 9.5 * mm, sy, nome)
            sy -= 4.6 * mm
        sy -= 1.5 * mm

    # --- Legenda de status -------------------------------------------------
    legend_y = 13 * mm
    cursor_x = 18 * mm
    pdf.setFont("Helvetica", 7.5)
    for chave in ("ok", "warning", "critical", "unknown"):
        pdf.setFillColor(STATUS_COLOR[chave])
        pdf.circle(cursor_x + 1.2 * mm, legend_y + 1 * mm, 1.2 * mm, stroke=0, fill=1)
        pdf.setFillColor(MUTED)
        texto = STATUS_LABEL[chave]
        pdf.drawString(cursor_x + 4 * mm, legend_y, texto)
        cursor_x += 4 * mm + pdf.stringWidth(texto, "Helvetica", 7.5) + 6 * mm

    pdf.setFillColor(FAINT)
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(
        width - 18 * mm, legend_y, "Predicta - gemeo digital para manutencao preditiva"
    )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
