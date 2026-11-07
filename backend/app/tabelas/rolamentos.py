"""Dimensões de rolamentos rígidos de esferas, por série (tabela técnica local, com fonte registrada).

Fonte: ISO 15 (rolamentos radiais, séries de dimensão 60, 62 e 63): diâmetro interno d, externo D e
largura B, em mm. Conferida em 2026-11-07 contra os rolamentos já estruturados na base da empresa:
38 medidas da série 62/63 e todas as 35 da série 60 batem; a única divergência encontrada (6218)
era um registro da base com o diâmetro interno errado, não a tabela.

Serve só para os atributos OPCIONAIS da classe (a regra 7 do PDM permite deduzi-los da referência).
A identidade do item nunca depende deste arquivo.
"""
from __future__ import annotations

import re

from ..identidade.referencias import referencia_rolamento

FONTE = "ISO 15, serie {serie} (tabela local)"

#            d    D    B
_S60 = {"6000": (10, 26, 8), "6001": (12, 28, 8), "6002": (15, 32, 9), "6003": (17, 35, 10), "6004": (20, 42, 12),
        "6005": (25, 47, 12), "6006": (30, 55, 13), "6007": (35, 62, 14), "6008": (40, 68, 15), "6009": (45, 75, 16),
        "6010": (50, 80, 16), "6011": (55, 90, 18), "6012": (60, 95, 18), "6013": (65, 100, 18), "6014": (70, 110, 20),
        "6015": (75, 115, 20), "6016": (80, 125, 22)}
_S62 = {"6200": (10, 30, 9), "6201": (12, 32, 10), "6202": (15, 35, 11), "6203": (17, 40, 12), "6204": (20, 47, 14),
        "6205": (25, 52, 15), "6206": (30, 62, 16), "6207": (35, 72, 17), "6208": (40, 80, 18), "6209": (45, 85, 19),
        "6210": (50, 90, 20), "6211": (55, 100, 21), "6212": (60, 110, 22), "6213": (65, 120, 23), "6214": (70, 125, 24),
        "6215": (75, 130, 25), "6216": (80, 140, 26), "6217": (85, 150, 28), "6218": (90, 160, 30), "6219": (95, 170, 32),
        "6220": (100, 180, 34)}
_S63 = {"6300": (10, 35, 11), "6301": (12, 37, 12), "6302": (15, 42, 13), "6303": (17, 47, 14), "6304": (20, 52, 15),
        "6305": (25, 62, 17), "6306": (30, 72, 19), "6307": (35, 80, 21), "6308": (40, 90, 23), "6309": (45, 100, 25),
        "6310": (50, 110, 27), "6311": (55, 120, 29), "6312": (60, 130, 31), "6313": (65, 140, 33), "6314": (70, 150, 35),
        "6315": (75, 160, 37), "6316": (80, 170, 39)}
SERIES = {**_S60, **_S62, **_S63}


def dimensoes(referencia: str | None) -> dict[str, tuple[str, str]]:
    """`6205-2RS/C3` → {DIAMETRO INTERNO: ("25MM", fonte), DIAMETRO EXTERNO: ..., LARGURA: ...}. Série
    desconhecida devolve vazio: nada é adivinhado."""
    ref = referencia_rolamento(referencia) if referencia else None
    m = re.match(r"^(\d{4})(?!\d)", ref or "")
    if not m or m.group(1) not in SERIES:
        return {}
    serie = m.group(1)
    d, D, B = SERIES[serie]
    fonte = FONTE.format(serie=serie)
    return {"DIAMETRO INTERNO": (f"{d}MM", fonte), "DIAMETRO EXTERNO": (f"{D}MM", fonte), "LARGURA": (f"{B}MM", fonte)}
