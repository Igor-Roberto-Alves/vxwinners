"""Normalização de texto (regra 3 do PDM): maiúsculas, sem acento, sem cedilha."""
from __future__ import annotations

import re
import unicodedata

_NAO_ALNUM = re.compile(r"[^A-Z0-9]+")
_ESPACOS = re.compile(r"\s+")


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normaliza(s: str | None) -> str:
    if not s:
        return ""
    return _ESPACOS.sub(" ", sem_acento(s).upper()).strip()


def tokens(s: str | None) -> list[str]:
    return [t for t in _NAO_ALNUM.split(normaliza(s)) if t]


# Abreviações mais frequentes da base legada (docs/01-dados.md). Usadas só para
# achar a classe e ler rótulos; nunca para reescrever o valor gravado.
ABREVIACOES = {
    "PARAF": "PARAFUSO", "SEXT": "SEXTAVADO", "HIDR": "HIDRAULICO", "MANG": "MANGUEIRA",
    "RET": "RETENTOR", "ROL": "ROLAMENTO", "DIAM": "DIAMETRO", "COMP": "COMPRIMENTO",
    "MAT": "MATERIAL", "APLIC": "APLICACAO", "MOD": "MODELO", "FABR": "FABRICANTE",
    "REF": "REFERENCIA", "INT": "INTERNO", "EXT": "EXTERNO", "MONT": "MONTADA",
    "LUBR": "LUBRIFICANTE", "VALV": "VALVULA", "ESF": "ESFERA", "RIG": "RIGIDO",
    "ESFERAS": "ESFERAS", "CONT": "CONTATOR", "DISJ": "DISJUNTOR", "TERM": "TERMINAL",
    "ELET": "ELETRICO", "PNEUM": "PNEUMATICA", "FLEX": "FLEXIVEL",
}


def expande_abreviacoes(toks: list[str]) -> list[str]:
    return [ABREVIACOES.get(t, t) for t in toks]
