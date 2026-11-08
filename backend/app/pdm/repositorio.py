from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import Connection, text

from . import carregador
from .modelo import Pdm


def publica(conn: Connection, xlsx: Path, *, ativar: bool = True) -> int:
    """Publica o PDM de uma planilha como nova versão (idempotente pelo hash do arquivo)."""
    sha = carregador.sha256_arquivo(xlsx)
    existente = conn.execute(text("select id from pdm_versao where sha256 = :s"), {"s": sha}).scalar()
    if existente:
        versao = existente
    else:
        doc = carregador.carrega(xlsx)
        versao = conn.execute(
            text("insert into pdm_versao (arquivo, sha256, conteudo) values (:a, :s, cast(:c as jsonb)) returning id"),
            {"a": xlsx.name, "s": sha, "c": json.dumps(doc, ensure_ascii=False)},
        ).scalar_one()
    if ativar:
        conn.execute(text("update pdm_versao set ativa = false where ativa"))
        conn.execute(text("update pdm_versao set ativa = true where id = :i"), {"i": versao})
    ativo.cache_clear()
    return versao


def carrega_versao(conn: Connection, versao_id: int) -> Pdm:
    doc = conn.execute(text("select conteudo from pdm_versao where id = :i"), {"i": versao_id}).scalar_one()
    return Pdm.de_dict(doc, versao_id)


def versao_ativa_id(conn: Connection) -> int:
    v = conn.execute(text("select id from pdm_versao where ativa")).scalar()
    if v is None:
        raise RuntimeError("nenhuma versão do PDM ativa; rode scripts/ingerir.py")
    return v




def ativo(conn: Connection | None = None) -> Pdm:
    """PDM ativo, em cache de processo. `ativo.cache_clear()` após publicar outra versão."""
    return _ativo(conn)


_cache: dict[str, Pdm] = {}


def _ativo(conn: Connection | None) -> Pdm:
    from ..db import engine

    def ler(c: Connection) -> Pdm:
        vid = versao_ativa_id(c)
        if "pdm" not in _cache or _cache["pdm"].versao_id != vid:
            _cache["pdm"] = carrega_versao(c, vid)
        return _cache["pdm"]

    if conn is not None:
        return ler(conn)
    with engine().connect() as c:
        return ler(c)


def _limpa() -> None:
    _cache.clear()


ativo.cache_clear = _limpa  # type: ignore[attr-defined]
