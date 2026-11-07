"""As condicionais da coluna QUANDO_SE_APLICA, convertidas em predicados.

`aplica(...)` devolve True, False ou None (None = ainda depende de um atributo que não
foi preenchido). Cada condição do PDM tem de ter regra aqui; `lacunas()` acusa as que
faltam quando uma nova versão do PDM traz condição desconhecida.
"""
from __future__ import annotations

from typing import Callable

Valores = dict[str, str | None]
Predicado = Callable[[str, Valores], bool | None]


def _tem(v: Valores, atr: str) -> str | None:
    x = v.get(atr)
    return x if x else None


def _um_de(atr: str, *termos: str, parcial: bool = False) -> Predicado:
    def p(nome: str, v: Valores) -> bool | None:
        x = _tem(v, atr)
        if x is None:
            return None
        return any(t in x for t in termos) if parcial else x in termos
    return p


def _nome_em(*nomes: str) -> Predicado:
    return lambda nome, v: nome in nomes


def _classe_pressao_flange(nome: str, v: Valores) -> bool | None:  # todas, exceto solda de topo
    if nome == "FLANGE":
        return True
    c = _tem(v, "CONEXAO")
    return None if c is None else c != "SOLDA TOPO BW"


def _schedule(nome: str, v: Valores) -> bool | None:  # somente conexões para solda de topo
    if nome == "FLANGE":
        return False
    c = _tem(v, "CONEXAO")
    return None if c is None else c == "SOLDA TOPO BW"


REGRAS: dict[tuple[str, str], Predicado] = {
    ("PDM050", "TIPO"): _nome_em("FLANGE"),
    ("PDM050", "DIAMETRO REDUZIDO"): _nome_em("TE REDUCAO", "LUVA REDUCAO", "BUCHA REDUCAO"),
    ("PDM050", "CLASSE PRESSAO"): _classe_pressao_flange,
    ("PDM050", "SCHEDULE"): _schedule,
    ("PDM050", "FACE"): _nome_em("FLANGE"),
    ("PDM050", "CONEXAO"): lambda nome, v: nome != "FLANGE",
    ("PDM060", "COR"): _um_de("NUMERO CONDUTORES", "1"),
    ("PDM061", "FURO"): _um_de("TIPO", "OLHAL", "FORQUILHA", parcial=True),
    ("PDM062", "CORRENTE NOMINAL"): _um_de("TIPO", "MINIDISJUNTOR DIN", "CAIXA MOLDADA"),
    ("PDM062", "FAIXA AJUSTE"): _um_de("TIPO", "MOTOR"),
    ("PDM062", "CURVA"): _um_de("TIPO", "MINIDISJUNTOR DIN"),
    ("PDM062", "CAPACIDADE INTERRUPCAO"): _um_de("TIPO", "MINIDISJUNTOR DIN", "CAIXA MOLDADA"),
    ("PDM070", "CANO"): _um_de("MATERIAL", "VAQUETA", "RASPA"),
    ("PDM081", "ESPESSURA"): _um_de("TIPO", "CORTE", "DESBASTE"),
    ("PDM081", "GRAO"): _um_de("TIPO", "FLAP"),
}


def condicional_conhecida(quando: str) -> bool:
    q = quando.strip().lower()
    return q == "sempre" or q.startswith("quando informado")


def aplica(id_pdm: str, atributo: str, quando: str, nome: str, valores: Valores) -> bool | None:
    if condicional_conhecida(quando):
        return True
    regra = REGRAS.get((id_pdm, atributo))
    if regra is None:
        return True  # condição desconhecida: trata como aplicável (lacunas() avisa)
    return regra(nome, valores)


def lacunas(classes: dict) -> list[tuple[str, str, str]]:
    """Condições do PDM sem predicado: (classe, atributo, texto da condição)."""
    out = []
    for idp, c in classes.items():
        for a in c["atributos"]:
            if not condicional_conhecida(a["quando"]) and (idp, a["nome"]) not in REGRAS:
                out.append((idp, a["nome"], a["quando"]))
    return out
