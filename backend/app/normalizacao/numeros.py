"""Números no padrão brasileiro: ponto separa milhar, vírgula separa decimal.

`6.000 psi` é seis mil, não seis (armadilha plantada nos pedidos).
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_MILHAR = re.compile(r"^\d{1,3}(\.\d{3})+$")


def parse_numero(txt: str, *, ponto_decimal: bool = False) -> Decimal | None:
    """`ponto_decimal=True` força o ponto como decimal (usado em polegadas: 1.25")."""
    s = (txt or "").strip().replace(" ", "")
    if not s or not re.fullmatch(r"[\d.,]+", s):
        return None
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", "") if s.count(",") > 1 else s.replace(",", ".")
    elif "." in s:
        if not ponto_decimal and _MILHAR.match(s) and not s.startswith("0."):
            s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def formata(d: Decimal, casas: int | None = None) -> str:
    """Decimal com vírgula e sem zeros à direita (16,25 / 25)."""
    if casas is not None:
        d = d.quantize(Decimal(1).scaleb(-casas))
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")
