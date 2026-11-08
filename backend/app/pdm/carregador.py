"""Lê a planilha do PDM e produz o documento (dict JSON) que fica versionado no banco.

Os schemas nunca são digitados à mão: se o PDM mudar, uma nova versão é publicada e o
resto do sistema segue valendo (docs/02-plano-projeto.md, E0).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import openpyxl

from ..normalizacao.formatos import classifica
from ..normalizacao.texto import normaliza


def _linhas(wb, aba: str) -> list[dict]:
    it = wb[aba].iter_rows(values_only=True)
    cab = [str(c).strip() if c is not None else "" for c in next(it)]
    return [dict(zip(cab, r)) for r in it if any(c is not None for c in r)]


def _s(v) -> str:
    return "" if v is None else str(v).strip()


def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def carrega(caminho: Path) -> dict:
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)

    classes: dict[str, dict] = {}
    for r in _linhas(wb, "CLASSES"):
        idp = _s(r["ID_PDM"])
        guarda_chuva = _s(r["SUBSTANTIVO"]).startswith("(ver")
        criterio = "REFERENCIA" if _s(r["CRITERIO_IDENTIDADE"]).startswith("REFERENCIA") else "ESPECIFICACAO"
        classes[idp] = {
            "id_pdm": idp,
            "substantivo": "" if guarda_chuva else _s(r["SUBSTANTIVO"]),
            "qualificador": "" if guarda_chuva else _s(r["QUALIFICADOR"]),
            "grupo": _s(r["GRUPO_MERCADORIA"]),
            "unidade": _s(r["UNIDADE_PADRAO"]),
            "ncm": _s(r["NCM"]),
            "criterio": criterio,
            "guarda_chuva": guarda_chuva,
            "atributos": [],
            "nomes": [],
        }

    for r in _linhas(wb, "ATRIBUTOS"):
        valores = [v.strip() for v in _s(r["VALORES_PERMITIDOS"]).split("|") if v.strip()]
        formato = _s(r["FORMATO"])
        classes[_s(r["ID_PDM"])]["atributos"].append({
            "ordem": int(r["ORDEM"]),
            "nome": _s(r["ATRIBUTO"]),
            "obrigatorio": _s(r["OBRIGATORIO"]) == "S",
            "quando": _s(r["QUANDO_SE_APLICA"]) or "sempre",
            "formato": formato,
            "valores": valores,
            "tipo": classifica(formato, bool(valores)),
        })
    for c in classes.values():
        c["atributos"].sort(key=lambda a: a["ordem"])

    # Nomes de material: cada um aponta para uma classe.
    def nomes_da_aba(aba: str) -> list[str]:
        return [_s(r["SUBSTANTIVO_E_QUALIFICADOR"]) for r in _linhas(wb, aba)]

    for idp, c in classes.items():
        if idp == "PDM110":
            c["nomes"] = nomes_da_aba("SUBSTANTIVOS_SOBRESSALENTES")
        elif idp == "PDM050":
            c["nomes"] = nomes_da_aba("SUBSTANTIVOS_CONEXOES")
        elif "|" in c["qualificador"]:  # PDM100: FILTRO AR | COMBUSTIVEL | ...
            c["nomes"] = [f'{c["substantivo"]} {q.strip()}' for q in c["qualificador"].split("|")]
        else:
            c["nomes"] = [f'{c["substantivo"]} {c["qualificador"]}'.strip()]

    ncm_regras: dict[str, list[dict]] = {}
    for r in _linhas(wb, "NCM_REFERENCIA"):
        ncm_regras.setdefault(_s(r["ID_PDM"]), []).append({"ncm": _s(r["NCM"]), "regra": _s(r["REGRA"])})

    return {
        "classes": classes,
        "grupos": {_s(r["GRUPO_MERCADORIA"]): _s(r["DESCRICAO"]) for r in _linhas(wb, "GRUPOS_MERCADORIA")},
        "unidades": {_s(r["UNIDADE"] if "UNIDADE" in r else list(r.values())[0]): _s(list(r.values())[1])
                     for r in _linhas(wb, "UNIDADES")},
        "ncm_regras": ncm_regras,
        "regras_gerais": [_s(list(r.values())[0]) for r in _linhas(wb, "REGRAS_GERAIS")],
    }
