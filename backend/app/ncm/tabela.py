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
    """Baixa a tabela oficial, e só grava se o que veio FOR a tabela.

    O Portal Único fica em parada programada todo dia entre 01:00 e 03:00 e,
    nessa janela, responde 200 com um JSON de erro:

        {"message": "...parada programada...", "code": "PUCX-ER0014",
         "tag": "[static]", "severity": "ERROR"}

    Gravando isso no cache, o `ingerir` seguinte quebrava ao ler o cache - e
    continuava quebrando depois das 03:00, porque o arquivo ruim já existia e
    `_ingerir` só baixa quando o cache não existe. Agora o erro do portal falha
    na hora, com a mensagem dele, e o cache antigo (ou o arquivo versionado em
    dados/referencia/) continua valendo.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(URL_SISCOMEX, timeout=timeout) as r:  # noqa: S310 - URL fixa e pública
        bruto = r.read()
    try:
        doc = json.loads(bruto)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"resposta do Siscomex não é JSON: {bruto[:200]!r}") from e
    if not isinstance(doc, dict) or not (doc.get("Nomenclaturas") or doc.get("codigos")):
        raise RuntimeError(
            "o Siscomex não devolveu a tabela NCM: "
            + str(doc.get("message") or doc)[:200]
            + " — use a tabela versionada em dados/referencia/ncm_siscomex.json")
    destino.write_bytes(bruto)
    return destino


def _data(s: str) -> date:
    return datetime.strptime(s, "%d/%m/%Y").date()


def _le(doc: dict) -> tuple[str | None, str | None, list[dict]]:
    """Aceita os DOIS formatos da tabela NCM que existem no repositorio.

    bruto do Siscomex, como a API devolve:
        {"Ato": ..., "Data_Ultima_Atualizacao_NCM": ...,
         "Nomenclaturas": [{"Codigo", "Descricao", "Data_Inicio", "Data_Fim"}, ...]}

    normalizado, que e o que esta versionado em dados/referencia/ncm_siscomex.json
    (baixado e compactado pelo pipeline de saneamento, com a vigencia e o ato nos
    metadados):
        {"meta": {"ato", "vigencia_declarada", "data_download", ...},
         "codigos": {"01012100": {"descricao", "inicio", "fim"}, ...}}

    As duas leituras existiam em ramos separados e se encontraram no merge: o
    backend lia so o bruto e quebrava com KeyError 'Nomenclaturas' no arquivo
    versionado, que e justamente o que o ./rodar.sh usa.

    Devolve (ato, vigente_em, linhas sem o numero da versao).
    """
    if "Nomenclaturas" in doc:
        itens = [
            {"c": i["Codigo"], "d": i["Descricao"],
             "i": _data(i["Data_Inicio"]), "f": _data(i["Data_Fim"])}
            for i in doc["Nomenclaturas"] if _OITO.match(i["Codigo"])
        ]
        return doc.get("Ato"), doc.get("Data_Ultima_Atualizacao_NCM"), itens

    meta = doc.get("meta") or {}
    itens = []
    for codigo, v in (doc.get("codigos") or {}).items():
        # o arquivo normalizado guarda 8 digitos sem ponto ('01012100'); o resto
        # do backend (valida(), _tabela()) trabalha no formato do PDM, com ponto
        so_digitos = re.sub(r"\D", "", codigo)
        if len(so_digitos) != 8:
            continue
        pontuado = f"{so_digitos[:4]}.{so_digitos[4:6]}.{so_digitos[6:]}"
        itens.append({"c": pontuado, "d": v["descricao"],
                      "i": _data(v["inicio"]), "f": _data(v["fim"])})
    if not itens:
        raise ValueError("tabela NCM sem codigos de 8 digitos reconheciveis: "
                         f"chaves do arquivo = {sorted(doc)[:6]}")
    return meta.get("ato"), meta.get("vigencia_declarada") or meta.get("data_download"), itens


def importa(conn: Connection, arquivo: Path, *, ativar: bool = True) -> int:
    bruto = arquivo.read_bytes()
    sha = hashlib.sha256(bruto).hexdigest()
    existente = conn.execute(text("select id from ncm_versao where sha256 = :s"), {"s": sha}).scalar()
    if existente:
        versao = existente
    else:
        ato, vigente_em, itens = _le(json.loads(bruto))
        versao = conn.execute(
            text("insert into ncm_versao (fonte, ato, vigente_em, sha256) values (:f, :a, :v, :s) returning id"),
            {"f": URL_SISCOMEX, "a": ato, "v": vigente_em, "s": sha},
        ).scalar_one()
        linhas = [{"v": versao, **i} for i in itens]
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
        return Validacao(False, "formato inválido (esperado 0000.00.00)")
    tab = _tabela(conn)
    if not tab:
        return Validacao(True, "tabela oficial não carregada: só o formato foi conferido")
    hoje = em or date.today()
    item = tab.get(ncm)
    if item is None:
        prefixo = ncm[:7]  # 0000.00 → sucessores do desdobramento
        suc = tuple(sorted(c for c, (_, i, f) in tab.items() if c.startswith(prefixo) and i <= hoje <= f))
        return Validacao(False, "código inexistente na tabela oficial vigente", sucessores=suc)
    desc, ini, fim = item
    if not (ini <= hoje <= fim):
        return Validacao(False, f"código fora de vigência ({ini:%d/%m/%Y} a {fim:%d/%m/%Y})", desc)
    return Validacao(True, "", desc)
