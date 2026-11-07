"""Carrega `preenchimento/saida` (trabalho do time) como SUGESTÕES por material.

Nunca alimenta a chave de identidade: boa parte foi inferida por modelo (fabricante de 12.909 itens
veio de LLM, com acerto medido de 84%), e inferência não prova que dois itens são o mesmo.
"""
from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import Connection, text

from ..config import RAIZ_REPO

SAIDA = RAIZ_REPO / "preenchimento" / "saida"
ARQUIVOS = {"FABRICANTE": "preenchido_FABRICANTE.csv", "NCM": "preenchido_NCM.csv",
            "REFERENCIA_FABRICANTE": "preenchido_REFERENCIA_FABRICANTE.csv"}


def _le(caminho: Path, campo: str) -> list[dict]:
    out = []
    with open(caminho, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            v = (r.get("y_pred") or "").strip()
            if not v or v == "PENDENTE":
                continue
            if campo == "NCM" and len(v) == 8 and v.isdigit():
                v = f"{v[:4]}.{v[4:6]}.{v[6:]}"
            out.append({"c": r["CODIGO_MATERIAL"], "ca": campo, "v": v, "co": float(r["conf"] or 0), "m": r.get("metodo")})
    return out


def importa(conn: Connection) -> dict:
    conn.execute(text("delete from material_sugestao"))
    linhas: list[dict] = []
    for campo, nome in ARQUIVOS.items():
        linhas += _le(SAIDA / nome, campo)
    with open(SAIDA / "grupo_suspeitos.csv", encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            linhas.append({"c": r["CODIGO_MATERIAL"], "ca": "GRUPO_MERCADORIA", "v": r["grupo_sugerido"], "co": float(r["conf"] or 0), "m": "tfidf_lr"})
    existentes = {r[0] for r in conn.execute(text("select codigo from material"))}
    linhas = [x for x in linhas if x["c"] in existentes]
    if linhas:
        conn.execute(text("insert into material_sugestao (codigo, campo, valor, conf, metodo) values (:c, :ca, :v, :co, :m) on conflict do nothing"), linhas)
    n = conn.execute(text("select campo, count(*) from material_sugestao group by 1 order by 1")).all()
    return {campo: q for campo, q in n}
