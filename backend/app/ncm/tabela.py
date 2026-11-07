"""Tabela oficial da NCM: importação e validação (regra 12 do PDM).

Fonte: Portal Único Siscomex, módulo Classif (público). A validação confere que o código
existe e está vigente na data da consulta; se não estiver, aponta os sucessores prováveis.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Connection, text

URL_SISCOMEX = "https://portalunico.siscomex.gov.br/classif/api/publico/nomenclatura/download/json"
_OITO = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


def baixa(destino: Path, timeout: float = 120.0) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL_SISCOMEX, timeout=timeout) as r:  # noqa: S310 - URL fixa e pública
        destino.write_bytes(r.read())
    return destino


def _data(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%Y").date()


def importa(conn: Connection, arquivo: Path, *, ativar: bool = True) -> int:
    bruto = arquivo.read_bytes()
    sha = hashlib.sha256(bruto).hexdigest()
    existente = conn.execute(text("select id from ncm_versao where sha256 = :s"), {"s": sha}).scalar()
    if existente:
        versao = existente
    else:
        doc = json.loads(bruto)
        versao = conn.execute(
            text("insert into ncm_versao (fonte, ato, vigente_em, sha256) values (:f, :a, :v, :s) returning id"),
            {"f": URL_SISCOMEX, "a": doc.get("Ato"), "v": doc.get("Data_Ultima_Atualizacao_NCM"), "s": sha},
        ).scalar_one()
        linhas = [
            {"v": versao, "c": i["Codigo"], "d": i["Descricao"], "i": _data(i["Data_Inicio"]), "f": _data(i["Data_Fim"])}
            for i in doc["Nomenclaturas"] if _OITO.match(i["Codigo"])
        ]
        conn.execute(
            text("insert into ncm_tabela (versao_id, codigo, descricao, data_inicio, data_fim) "
                 "values (:v, :c, :d, :i, :f)"), linhas)
    if ativar:
        conn.execute(text("update ncm_versao set ativa = false where ativa"))
        conn.execute(text("update ncm_versao set ativa = true where id = :i"), {"i": versao})
    _cache.clear()
    return versao


@dataclass(frozen=True)
class Validacao:
    ok: bool
    motivo: str = ""
    descricao: str = ""
    sucessores: tuple[str, ...] = ()


_cache: dict[str, dict] = {}


def _tabela(conn: Connection) -> dict[str, tuple[str, date, date]]:
    if "t" not in _cache:
        rows = conn.execute(text(
            "select t.codigo, t.descricao, t.data_inicio, t.data_fim from ncm_tabela t "
            "join ncm_versao v on v.id = t.versao_id where v.ativa")).all()
        _cache["t"] = {r[0]: (r[1], r[2], r[3]) for r in rows}
    return _cache["t"]


def valida(conn: Connection, ncm: str | None, *, em: date | None = None) -> Validacao:
    if not ncm or not _OITO.match(ncm):
        return Validacao(False, "formato invalido (esperado 0000.00.00)")
    tab = _tabela(conn)
    if not tab:
        return Validacao(True, "tabela oficial nao carregada: so o formato foi conferido")
    hoje = em or date.today()
    item = tab.get(ncm)
    if item is None:
        prefixo = ncm[:7]  # 0000.00 → sucessores do desdobramento
        suc = tuple(sorted(c for c, (_, i, f) in tab.items() if c.startswith(prefixo) and i <= hoje <= f))
        return Validacao(False, "codigo inexistente na tabela oficial vigente", sucessores=suc)
    desc, ini, fim = item
    if not (ini <= hoje <= fim):
        return Validacao(False, f"codigo fora de vigencia ({ini:%d/%m/%Y} a {fim:%d/%m/%Y})", desc)
    return Validacao(True, "", desc)
