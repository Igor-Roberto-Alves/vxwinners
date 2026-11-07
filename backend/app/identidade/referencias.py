"""Normalização de fabricante e referência para a chave de identidade (regra 10).

Duas formas de identidade:
 - especificação técnica: a referência do rolamento 6205 é reduzida a série + vedação + folga,
   então SKF 6205-2RSH/C3, FAG 6205-C-2HRS-C3 e NSK 6205DDUC3 viram a mesma referência;
 - referência do fabricante (filtros, sobressalentes): fabricante + part number, sem separadores,
   então 1R-1808 e 1R1808 são iguais. Equivalência entre fabricantes NÃO junta (regra 13).
"""
from __future__ import annotations

import re

from ..normalizacao.texto import normaliza

ALIAS_FABRICANTE = {
    "CAT": "CATERPILLAR", "CATERPILLAR INC": "CATERPILLAR", "FLEETGUARD": "FLEETGUARD",
    "CUMMINS FILTRATION": "FLEETGUARD", "MANN FILTER": "MANN", "MANN HUMMEL": "MANN",
    "MANN+HUMMEL": "MANN", "DONALDSON FILTRATION": "DONALDSON", "SKF AB": "SKF", "FLSMIDTH": "FLSMIDTH",
    "KOMATSU LTD": "KOMATSU", "METSO OUTOTEC": "METSO", "OUTOTEC": "METSO",
}


def fabricante_canonico(texto: str | None, permitidos: tuple[str, ...] = ()) -> str | None:
    n = normaliza(texto)
    if not n:
        return None
    n = ALIAS_FABRICANTE.get(n, n)
    if permitidos:
        mapa = {normaliza(p): p for p in permitidos}
        if n in mapa:
            return mapa[n]
        for tok in n.replace("-", " ").split():
            if tok in mapa:
                return mapa[tok]
        return n  # fora da lista: segue normalizado, a validação acusa
    return n


def referencia_generica(texto: str | None) -> str | None:
    """Maiúsculas e sem separadores: `1R-1808`, `1R 1808` e `1R1808` são a mesma referência."""
    n = re.sub(r"[\s\-/\.\\_]+", "", normaliza(texto))
    return n or None


_SERIE = re.compile(r"(?<![A-Z0-9])(\d{4,5})([A-Z0-9\-/]*)")
_VEDACAO_BORRACHA = re.compile(r"2RS1|2RSH|2RS2|2RS|DDU|2HRS|LLU")
_VEDACAO_METAL = re.compile(r"2ZR|2Z|ZZ")
_FOLGA = re.compile(r"C([2-5])")


def referencia_rolamento(texto: str | None) -> str | None:
    """`SKF 6205-2RSH/C3` → `6205-2RS/C3`; `6310-2Z/C3` → `6310-ZZ/C3` (notação do PDM).
    Sem série reconhecível devolve a referência genérica."""
    n = normaliza(texto)
    m = _SERIE.search(n)
    if not m:
        return referencia_generica(texto)
    serie, resto = m.group(1), re.sub(r"[\-/]", "", m.group(2))
    vedacao = None
    if (mv := _VEDACAO_BORRACHA.search(resto)):
        vedacao, resto = "2RS", resto.replace(mv.group(0), "", 1)
    elif (mv := _VEDACAO_METAL.search(resto)):
        vedacao, resto = "ZZ", resto.replace(mv.group(0), "", 1)
    folga = None
    if (mf := _FOLGA.search(resto)):
        folga = "C" + mf.group(1)
    out = serie
    if vedacao:
        out += f"-{vedacao}"
    if folga:
        out += f"/{folga}"
    return out


def deduz_vedacao_folga(texto: str | None) -> dict[str, str]:
    """A partir do sufixo da referência do rolamento. Sem sufixo: aberto e folga normal,
    com confiança menor (quem chama decide)."""
    ref = referencia_rolamento(texto) or ""
    out = {}
    if "-2RS" in ref:
        out["VEDACAO"] = "BORRACHA AMBOS LADOS"
    elif "-ZZ" in ref:
        out["VEDACAO"] = "METALICA AMBOS LADOS"
    if "/C" in ref:
        out["FOLGA"] = ref.split("/")[-1]
    return out


def fabricante_no_texto(texto: str, permitidos: tuple[str, ...]) -> str | None:
    """Fabricante da lista (ou apelido conhecido, como CAT) presente no texto, com fronteira de palavra.
    Mais de um fabricante distinto no texto → None (não escolhe)."""
    import re as _re

    nt = " " + normaliza(texto) + " "
    mapa = {normaliza(p): p for p in permitidos}
    achados = set()
    for chave, canon in list(mapa.items()) + [(a, mapa.get(normaliza(c))) for a, c in ALIAS_FABRICANTE.items()]:
        if canon and len(chave) >= 3 and _re.search(rf"(?<![A-Z0-9]){_re.escape(chave)}(?![A-Z0-9])", nt):
            achados.add(canon)
    return next(iter(achados)) if len(achados) == 1 else None
