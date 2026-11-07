"""Conversão de grandezas para o formato do PDM (regras 5 e 6).

Cada função é pura: texto → Norm(valor, confianca, motivo). Valor None significa que
não foi possível converter com segurança; nunca se inventa valor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction

from .numeros import formata, parse_numero
from .texto import normaliza


@dataclass(frozen=True)
class Norm:
    valor: str | None
    confianca: float = 0.0
    motivo: str = ""


NAO = Norm(None, 0.0, "nao reconhecido")

# ------------------------------------------------------------------ polegada
# DN (diâmetro nominal, ISO 6708) → polegada nominal (ASME B36.10M).
DN_POL = {
    6: "1/8", 8: "1/4", 10: "3/8", 15: "1/2", 20: "3/4", 25: "1", 32: "1.1/4", 40: "1.1/2",
    50: "2", 65: "2.1/2", 80: "3", 90: "3.1/2", 100: "4", 125: "5", 150: "6", 200: "8",
    250: "10", 300: "12", 350: "14", 400: "16", 450: "18", 500: "20", 600: "24",
}
_UN_POL = r"(?:\"|''|”|POL(?:EGADAS?)?|IN(?:CH)?|PL)"
_FRAC = re.compile(rf"(?<![\d/])(?:(\d+)[\s\-\.]+)?(\d+)/(\d+)\s*{_UN_POL}?(?![\d/])")
_DEC_POL = re.compile(rf"(?<![\d.,/])(\d+(?:[.,]\d+)?)\s*{_UN_POL}(?![A-Z0-9])")
_DN = re.compile(r"\bDN\s*-?\s*(\d+)\b")


def _monta_pol(inteiro: int, frac: Fraction) -> str:
    if frac == 0:
        return f"{inteiro}POL"
    f = f"{frac.numerator}/{frac.denominator}"
    return f"{inteiro}.{f}POL" if inteiro else f"{f}POL"


def polegada(texto: str) -> Norm:
    t = normaliza(texto)
    m = _DN.search(t)
    if m and int(m.group(1)) in DN_POL:
        v = DN_POL[int(m.group(1))]
        return Norm(v + "POL", 0.9, f"DN {m.group(1)} = {v} pol")
    m = _FRAC.search(t)
    if m:
        inteiro = int(m.group(1) or 0)
        frac = Fraction(int(m.group(2)), int(m.group(3)))
        if frac.denominator and frac < 1:
            return Norm(_monta_pol(inteiro, frac), 0.98, "fracao")
        if frac >= 1:
            inteiro += int(frac)
            return Norm(_monta_pol(inteiro, frac - int(frac)), 0.95, "fracao impropria")
    m = _DEC_POL.search(t)
    if m:
        d = parse_numero(m.group(1), ponto_decimal=True)
        if d is not None:
            inteiro = int(d)
            resto = Fraction(d - inteiro).limit_denominator(64)
            if abs(float(d - inteiro) - float(resto)) < 0.002:
                return Norm(_monta_pol(inteiro, resto), 0.95, "decimal em polegada")
    return NAO


# ------------------------------------------------------------------ milímetro
_MM = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)*)\s*(MM|CM|M|\"|''|POL|IN)(?![A-Z0-9])")


def mm(texto: str, *, aceita_metro: bool = False) -> Norm:
    """Converte medida linear para `NNMM` (decimal com vírgula). `M` só quando
    `aceita_metro` (comprimento de mangueira montada, regra 6)."""
    t = normaliza(texto)
    for m in _MM.finditer(t):
        un = m.group(2)
        if un == "M" and not aceita_metro:
            continue
        d = parse_numero(m.group(1), ponto_decimal=un in ('"', "''", "POL", "IN"))
        if d is None:
            continue
        fator = {"MM": 1, "CM": 10, "M": 1000, '"': Decimal("25.4"), "''": Decimal("25.4"),
                 "POL": Decimal("25.4"), "IN": Decimal("25.4")}[un]
        v = d * Decimal(fator)
        if un in ('"', "''", "POL", "IN"):
            v = v.quantize(Decimal("0.01"))
            if abs(v - v.to_integral_value()) <= Decimal("0.05"):
                v = v.to_integral_value()
        conf = 0.98 if un == "MM" else 0.9
        return Norm(formata(v) + "MM", conf, f"{m.group(1)} {un}")
    return NAO


# ------------------------------------------------------------------ pressão
_PRESSAO = re.compile(
    r"(?<![\d.,])(\d+(?:[.,]\d+)*)\s*(BAR|PSI|MPA|KPA|KGF\s*/\s*CM2|KGF\s*/\s*CM²|KG\s*/\s*CM2|KGF|ATM)(?![A-Z0-9])"
)
_PARA_BAR = {
    "BAR": Decimal(1), "PSI": Decimal("0.0689476"), "MPA": Decimal(10), "KPA": Decimal("0.01"),
    "KGF": Decimal("0.980665"), "ATM": Decimal("1.01325"),
}


def pressao_bar(texto: str) -> Norm:
    """Pressão sempre em BAR. `3.650 psi` (ponto = milhar) → 252BAR."""
    t = normaliza(texto)
    m = _PRESSAO.search(t)
    if not m:
        return NAO
    un = m.group(2)
    chave = "KGF" if un.startswith("KG") else un
    d = parse_numero(m.group(1))
    if d is None:
        return NAO
    bar = d * _PARA_BAR[chave]
    bar = bar.quantize(Decimal(1)) if bar >= 10 else bar.quantize(Decimal("0.1"))
    return Norm(formata(bar) + "BAR", 0.98 if un == "BAR" else 0.93, f"{m.group(1)} {un}")


# ------------------------------------------------------------------ seção de cabo
# Aproximação AWG → seção comercial (mm²). Marcada com confiança menor.
AWG_MM2 = {"18": "0,75", "16": "1,5", "14": "2,5", "12": "4", "10": "6", "8": "10", "6": "16",
           "4": "25", "2": "35", "1": "50", "1/0": "50", "2/0": "70", "3/0": "95", "4/0": "120"}
_SECAO = re.compile(r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:MM2|MM²|MMQ|MM\^2|SQMM)")
_AWG = re.compile(r"\bAWG\s*#?\s*(\d+(?:/0)?)\b")


def secao_mm2(texto: str) -> Norm:
    t = normaliza(texto)
    m = _SECAO.search(t)
    if m:
        d = parse_numero(m.group(1), ponto_decimal=True)
        if d is not None:
            return Norm(formata(d) + "MM2", 0.97, "secao")
    m = _AWG.search(t)
    if m and m.group(1) in AWG_MM2:
        return Norm(AWG_MM2[m.group(1)] + "MM2", 0.7, f"AWG {m.group(1)} aproximado")
    return NAO


# ------------------------------------------------------------------ simples
def com_sufixo(texto: str, sufixo: str, *, aceita_sem_unidade: bool = False) -> Norm:
    """`63A`, `12M`: número seguido do sufixo do formato."""
    t = normaliza(texto).replace(" ", "")
    m = re.fullmatch(rf"(\d+(?:[.,]\d+)?)\s*{sufixo}", t)
    if m:
        d = parse_numero(m.group(1), ponto_decimal=True)
        if d is not None:
            return Norm(formata(d) + sufixo, 0.95, "sufixo")
    if aceita_sem_unidade and re.fullmatch(r"\d+(?:[.,]\d+)?", t):
        d = parse_numero(t, ponto_decimal=True)
        return Norm(formata(d) + sufixo, 0.6, "unidade assumida")
    return NAO


# ------------------------------------------------------------------ rosca composta
_ROSCA = re.compile(
    r"(?<![A-Z0-9])M\s*-?\s*(\d{1,3})(?:\s*[X×]\s*(\d+(?:[.,]\d+)?))?(?:\s*[X×]\s*(\d+(?:[.,]\d+)?))?(?![A-Z0-9])"
)


def rosca_composta(texto: str) -> dict[str, Norm]:
    """`M12X50` → BITOLA M12 + COMPRIMENTO 50MM (regra 2 do PDM); sem passo = métrica grossa.
    `M12X1,5X50` → BITOLA M12X1,5 (passo fino) + COMPRIMENTO 50MM."""
    t = normaliza(texto)
    m = _ROSCA.search(t)
    if not m:
        return {}
    d, b, c = m.group(1), m.group(2), m.group(3)

    def eh_passo(x: str, tem_terceiro: bool) -> bool:
        v = parse_numero(x, ponto_decimal=True)
        return v is not None and (tem_terceiro or "," in x or "." in x or v <= 3)

    out: dict[str, Norm] = {}
    passo = comprimento = None
    if b and c:
        passo, comprimento = b, c
    elif b:
        if eh_passo(b, False):
            passo = b
        else:
            comprimento = b
    if passo:
        p = formata(parse_numero(passo, ponto_decimal=True))
        out["BITOLA"] = Norm(f"M{d}X{p}", 0.95, "rosca fina")
        out["ROSCA"] = Norm("METRICA FINA", 0.9, "passo informado")
    else:
        out["BITOLA"] = Norm(f"M{d}", 0.97, "rosca metrica")
        if b or c:  # só afirma métrica grossa quando há medida composta (M12X50)
            out["ROSCA"] = Norm("METRICA GROSSA", 0.85, "regra 2 do PDM: sem passo = metrica grossa")
    if comprimento:
        v = parse_numero(comprimento, ponto_decimal=True)
        out["COMPRIMENTO"] = Norm(formata(v) + "MM", 0.95, "comprimento da notacao composta")
    return out
