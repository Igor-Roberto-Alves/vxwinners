"""NCM esperado por classe (regra 12 do PDM), guiado pela aba NCM_REFERENCIA.

`ncm_esperado` devolve (ncm, regra). ncm=None significa "ainda não dá para decidir"
(falta um atributo que define o NCM): nunca se escolhe um NCM por palpite.
"""
from __future__ import annotations

import re

from ..pdm.modelo import Pdm

_NCM = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


def formata_ncm(bruto: str | None) -> str | None:
    """`73181500`, `7318.1500` e `7318.15.00` viram `7318.15.00`; o resto é inválido (None)."""
    if not bruto:
        return None
    d = re.sub(r"\D", "", str(bruto))
    if len(d) != 8:
        return None
    return f"{d[:4]}.{d[4:6]}.{d[6:]}"


def _u(v: dict[str, str | None], k: str) -> str:
    return (v.get(k) or "").upper()


def _referencia_unica(pdm: Pdm, id_pdm: str) -> str | None:
    c = pdm.classes[id_pdm]
    if _NCM.match(c.ncm):
        return c.ncm
    regras = pdm.ncm_regras.get(id_pdm, [])
    if len(regras) == 1 and _NCM.match(regras[0]["ncm"]):
        return regras[0]["ncm"]
    return None


def _conexoes(nome: str, v: dict) -> tuple[str | None, str]:
    material = _u(v, "MATERIAL")
    if not material:
        return None, "PDM050: falta MATERIAL"
    if "MALEAVEL" in material:
        return "7307.19.90", "ferro maleavel"
    inox = "INOX" in material
    if nome == "FLANGE":
        return ("7307.21.00" if inox else "7307.91.00"), "flange"
    conexao = _u(v, "CONEXAO")
    if not conexao:
        return None, "PDM050: falta CONEXAO"
    if conexao.startswith("ROSCA"):
        if nome.startswith("COTOVELO") or nome in ("LUVA", "LUVA REDUCAO"):
            return ("7307.22.00" if inox else "7307.92.00"), "roscada: cotovelo e luva"
        return ("7307.29.00" if inox else "7307.99.00"), "roscada: demais"
    if "ENCAIXE" in conexao:
        return ("7307.29.00" if inox else "7307.99.00"), "solda de encaixe (SW)"
    if "TOPO" in conexao:
        return ("7307.23.00" if inox else "7307.93.00"), "solda de topo (BW)"
    return None, "PDM050: conexao desconhecida"


def _tubo(nome: str, v: dict) -> tuple[str | None, str]:
    m = _u(v, "MATERIAL")
    if not m:
        return None, "PDM051: falta MATERIAL"
    if "API 5L" in m:
        return "7304.19.00", "API 5L"
    if "GALVANIZADO" in m:
        return "7306.30.00", "galvanizado NBR 5580"
    if "A312" in m:
        return "7306.40.00", "inox A312 com costura"
    if "A106" in m:
        dn = _u(v, "DIAMETRO NOMINAL")
        mm = re.match(r"^(?:(\d+)\.)?(\d+)(?:/(\d+))?POL$", dn)
        if not mm:
            return None, "PDM051: falta DIAMETRO NOMINAL"
        pol = int(mm.group(2)) / int(mm.group(3)) if mm.group(3) else int(mm.group(2))
        pol += int(mm.group(1) or 0)
        return ("7304.39.10" if pol <= 8 else "7304.39.90"), "A106 sem costura"
    return None, "PDM051: material sem regra"


def _mangueira_industrial(nome: str, v: dict) -> tuple[str | None, str]:
    if _u(v, "MATERIAL") == "PVC":
        return "3917.39.00", "PVC"
    reforco = _u(v, "REFORCO")
    if "ESPIRAL" in reforco:
        return "4009.41.00", "borracha com espiral de aco"
    if reforco:
        return "4009.31.00", "borracha com lonas texteis"
    return None, "PDM012: falta REFORCO"


def _mangote(nome: str, v: dict) -> tuple[str | None, str]:
    m = _u(v, "MATERIAL")
    if not m:
        return None, "PDM014: falta MATERIAL"
    return ("3917.39.00" if m.startswith("PVC") else "4009.41.00"), "material do mangote"


def _correia(nome: str, v: dict) -> tuple[str | None, str]:
    mm = re.match(r"^(\d+(?:,\d+)?)MM$", _u(v, "COMPRIMENTO EXTERNO"))
    if not mm:
        return None, "PDM030: falta COMPRIMENTO EXTERNO (circunferencia externa)"
    cm = float(mm.group(1).replace(",", ".")) / 10
    if cm <= 60 or cm > 240:
        return "4010.39.00", "circunferencia ate 60 cm ou acima de 240 cm"
    return ("4010.32.00" if cm <= 180 else "4010.34.00"), "circunferencia entre 60 e 240 cm"


def _junta_plana(nome: str, v: dict) -> tuple[str | None, str]:
    m = _u(v, "MATERIAL")
    if not m:
        return None, "PDM034: falta MATERIAL"
    return ("3926.90.90" if "PTFE" in m else "4016.93.00"), "PTFE ou borracha"


def _luva_seguranca(nome: str, v: dict) -> tuple[str | None, str]:
    m = _u(v, "MATERIAL")
    if m in ("VAQUETA", "RASPA"):
        return "4203.29.00", "couro"
    if m in ("NITRILICA", "LATEX"):
        return "4015.19.00", "borracha"
    if m.startswith("MALHA"):
        return "6116.10.00", "malha revestida"
    return None, "PDM070: material sem regra" if m else "PDM070: falta MATERIAL"


def _calcado(nome: str, v: dict) -> tuple[str | None, str]:
    b = _u(v, "BIQUEIRA")
    if b == "ACO":
        return "6403.40.00", "biqueira de aco"
    if b == "COMPOSITE":
        return "6403.99.90", "biqueira composite"
    return None, "PDM071: falta BIQUEIRA"


def _disco(nome: str, v: dict) -> tuple[str | None, str]:
    t = _u(v, "TIPO")
    if t == "FLAP":
        return "6805.10.00", "flap"
    if t in ("CORTE", "DESBASTE"):
        return "6804.22.11", "corte e desbaste"
    return None, "PDM081: falta TIPO"


def _filtro(nome: str, v: dict) -> tuple[str | None, str]:
    if "SEPARADOR" in nome:
        return "8421.39.90", "separador ar/oleo"
    if nome.endswith(" AR"):
        return "8421.31.00", "filtro de ar"
    if "HIDRAULICO" in nome:
        return "8421.29.90", "filtro hidraulico"
    return "8421.23.00", "filtro de oleo ou combustivel"


def _sobressalente(pdm: Pdm):
    por_equipamento: dict[str, str] = {}
    por_nome: dict[str, str] = {}
    for r in pdm.ncm_regras.get("PDM110", []):
        reg = r["regra"]
        if reg.startswith("sobressalente de "):
            por_equipamento[reg[len("sobressalente de "):].strip().upper()] = r["ncm"]
        elif reg.startswith("exceção: substantivo "):
            por_nome[reg[len("exceção: substantivo "):].strip().upper()] = r["ncm"]

    def f(nome: str, v: dict) -> tuple[str | None, str]:
        if nome in por_nome:
            return por_nome[nome], f"excecao por substantivo {nome}"
        eq = _u(v, "APLICACAO")
        if not eq:
            return None, "PDM110: falta APLICACAO (equipamento)"
        if eq in por_equipamento:
            return por_equipamento[eq], f"segue o equipamento {eq}"
        return None, f"PDM110: equipamento {eq} sem NCM"
    return f


def ncm_esperado(pdm: Pdm, id_pdm: str, nome: str, valores: dict[str, str | None]) -> tuple[str | None, str]:
    unico = _referencia_unica(pdm, id_pdm)
    if unico:
        return unico, "unico para a classe"
    fn = {
        "PDM012": _mangueira_industrial, "PDM014": _mangote, "PDM030": _correia, "PDM034": _junta_plana,
        "PDM050": _conexoes, "PDM051": _tubo, "PDM070": _luva_seguranca, "PDM071": _calcado,
        "PDM081": _disco, "PDM100": _filtro, "PDM110": _sobressalente(pdm),
    }.get(id_pdm)
    if fn is None:
        return None, "sem regra de NCM para a classe"
    return fn(nome.upper(), valores)
