"""Gera placas de identificacao sinteticas para demonstracao e teste do OCR.

As imagens sao renderizadas com texto limpo e servem de entrada para o
pipeline de OCR da Sprint 2 (ver app/modules/vision/plate_ocr.py).

Executar:  python assets/nameplates_samples/generate_samples.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(__file__).parent

NAMEPLATES: list[dict[str, object]] = [
    {
        "file": "placa_weg_w22.png",
        "title": "WEG",
        "subtitle": "MOTOR DE INDUCAO TRIFASICO",
        "lines": [
            "MOD  W22 IR3 PREMIUM",
            "7,5 kW          10 CV",
            "220/380 V       25,4/14,7 A",
            "60 Hz           1755 RPM",
            "IP55            ISOL F",
            "FS 1.15         FP 0,83",
        ],
    },
    {
        "file": "placa_siemens_1la7.png",
        "title": "SIEMENS",
        "subtitle": "MOTOR TRIFASICO DE INDUCAO",
        "lines": [
            "TIPO  1LA7 130-4AA60",
            "5,5 kW          380 V",
            "11,8 A          60 Hz",
            "1745 RPM        IP55",
            "ISOL F          FS 1.15",
        ],
    },
    {
        "file": "placa_dutchi_dm1.png",
        "title": "DUTCHI MOTORS",
        "subtitle": "MOTOR ELETRICO TRIFASICO",
        "lines": [
            "MOD  DM1 132M",
            "7,5 kW          220 V",
            "26 A            60 Hz",
            "1760 RPM        IP55",
            "CL F            FP 0,82",
        ],
    },
    {
        "file": "placa_metalcorte_mc.png",
        "title": "METALCORTE",
        "subtitle": "MOTOR ELETRICO INDUSTRIAL",
        "lines": [
            "MOD  MC-100L4",
            "3,0 kW          220/380 V",
            "11,5/6,6 A      60 Hz",
            "1740 RPM        IP54",
            "ISOL B          FS 1,0",
        ],
    },
]


def _font(size: int):
    """Devolve a fonte padrao escalavel do Pillow (>= 11)."""
    return ImageFont.load_default(size=size)


def render(spec: dict[str, object]) -> Path:
    """Renderiza uma placa de identificacao sintetica e devolve o caminho."""
    width, height = 780, 470
    image = Image.new("RGB", (width, height), (216, 214, 208))
    draw = ImageDraw.Draw(image)

    draw.rectangle([8, 8, width - 8, height - 8], outline=(70, 70, 66), width=4)
    draw.rectangle([22, 22, width - 22, height - 22], outline=(120, 120, 116), width=1)

    draw.text((44, 40), str(spec["title"]), fill=(20, 20, 18), font=_font(48))
    draw.text((44, 104), str(spec["subtitle"]), fill=(55, 55, 50), font=_font(20))
    draw.line([44, 138, width - 44, 138], fill=(120, 120, 116), width=2)

    y = 164
    for line in spec["lines"]:  # type: ignore[union-attr]
        draw.text((52, y), str(line), fill=(25, 25, 22), font=_font(27))
        y += 46

    path = OUTPUT_DIR / str(spec["file"])
    image.save(path)
    return path


def main() -> None:
    for spec in NAMEPLATES:
        path = render(spec)
        print(f"gerada: {path.name}")


if __name__ == "__main__":
    main()
