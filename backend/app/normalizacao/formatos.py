"""Interpreta a coluna FORMATO do PDM e valida/normaliza valores de atributos sem lista."""
from __future__ import annotations

import re

from . import grandezas as g
from .texto import normaliza

# tipo → regex do valor canônico
_VALIDADORES = {
    "MM": r"\d+(,\d+)?MM",
    "POL": r"(\d+\.)?\d+/\d+POL|\d+POL",
    "BAR": r"\d+(,\d+)?BAR",
    "MM2": r"\d+(,\d+)?MM2",
    "A": r"\d+(,\d+)?A",
    "W": r"\d+(,\d+)?W",
    "M": r"\d+(,\d+)?M",
    "INTEIRO": r"\d+",
    "CA": r"\d{5}",
    "FAIXA_BAR": r"0-\d+(,\d+)?BAR",
    "ROSCA_BITOLA": r"M\d+(X\d+(,\d+)?)?|(\d+\.)?\d+/\d+POL|\d+POL",
    "MM_OU_POL": r"\d+(,\d+)?MM|(\d+\.)?\d+/\d+POL|\d+POL",
}


def classifica(formato: str | None, tem_lista: bool) -> str:
    """Devolve o tipo do atributo: LISTA, MM, POL, BAR, ... ou LIVRE."""
    if tem_lista:
        return "LISTA"
    f = (formato or "").lower()
    if "rosca métrica: m +" in f or "bitola do parafuso" in f:
        return "ROSCA_BITOLA"
    if "rosca métrica: número + mm" in f:
        return "MM_OU_POL"
    if "polegada em fração" in f:
        return "POL"
    if "número + mm2" in f:
        return "MM2"
    if "número + mm" in f:
        return "MM"
    if "número + bar" in f:
        return "BAR"
    if "faixa de medição" in f:
        return "FAIXA_BAR"
    if "número + a" == f.strip() or f.strip() == "número + a":
        return "A"
    if f.strip() == "número + w":
        return "W"
    if f.strip() == "número + m":
        return "M"
    if f.strip() == "inteiro":
        return "INTEIRO"
    if "certificado de aprovação" in f:
        return "CA"
    return "LIVRE"  # código, referência do fabricante, perfil + comprimento...


def valida(tipo: str, valor: str) -> bool:
    if tipo == "LISTA":
        return True  # quem chama confere contra a lista
    if tipo == "LIVRE":
        return bool(valor and valor.strip())
    return re.fullmatch(_VALIDADORES[tipo], valor or "") is not None


def _sem_zero_decimal(v: str) -> str:
    """`7,0MM` → `7MM` e `16,250MM` → `16,25MM`: a mesma medida precisa fechar a mesma chave."""
    return re.sub(r"(,\d*?)0+(?=[A-Z])", r"\1", v).replace(",MM", "MM").replace(",BAR", "BAR").replace(",A", "A").replace(",W", "W").replace(",M", "M")


def normaliza_valor(tipo: str, texto: str, *, atributo: str = "") -> g.Norm:
    """Converte um texto qualquer para o formato do tipo. Texto já canônico passa direto."""
    t = normaliza(texto)
    if tipo == "LIVRE":
        return g.Norm(t or None, 0.9 if t else 0.0, "livre")
    # "já no formato" confere o texto como veio: remover espaços antes faria `1 1/2 POL` virar `11/2POL`
    if tipo != "LISTA" and valida(tipo, t):
        return g.Norm(_sem_zero_decimal(t), 1.0, "ja no formato")
    t = t.replace(" ", "")
    if tipo == "MM":
        return g.mm(texto, aceita_metro="COMPRIMENTO" in atributo)
    if tipo == "POL":
        return g.polegada(texto)
    if tipo == "BAR":
        return g.pressao_bar(texto)
    if tipo == "MM2":
        return g.secao_mm2(texto)
    if tipo == "A":
        return g.com_sufixo(texto, "A", aceita_sem_unidade=True)
    if tipo == "M":
        return g.com_sufixo(texto, "M", aceita_sem_unidade=True)
    if tipo == "W":
        return g.com_sufixo(texto, "W", aceita_sem_unidade=True)
    if tipo == "INTEIRO":
        return g.Norm(t, 0.9, "inteiro") if re.fullmatch(r"\d+", t) else g.NAO
    if tipo == "CA":
        return g.Norm(t, 0.9, "CA") if re.fullmatch(r"\d{5}", t) else g.NAO
    if tipo == "FAIXA_BAR":
        n = g.pressao_bar(texto)
        return g.Norm(f"0-{n.valor}", n.confianca, n.motivo) if n.valor else g.NAO
    if tipo == "ROSCA_BITOLA":
        r = g.rosca_composta(texto)
        if "BITOLA" in r:
            return r["BITOLA"]
        return g.polegada(texto)
    if tipo == "MM_OU_POL":
        n = g.mm(texto)
        return n if n.valor else g.polegada(texto)
    return g.NAO
