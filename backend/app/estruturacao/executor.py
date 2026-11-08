"""Executa a estruturação da base: regras primeiro (barato), LLM só no resíduo."""
from __future__ import annotations

import time

from sqlalchemy import text

from ..classes.resolver import IndiceClasses
from ..db import engine, transacao
from ..pdm import repositorio
from . import persistir
from .regras import extrai_por_regras

COLUNAS = "codigo, descricao_curta, descricao_longa, grupo, fabricante, referencia_fabricante, status, unidade, ncm"


def materiais(filtro_sql: str = "true", limite: int | None = None) -> list[dict]:
    sql = f"select {COLUNAS} from material m where {filtro_sql} order by codigo" + (f" limit {int(limite)}" if limite else "")
    with engine().connect() as c:
        return [dict(r._mapping) for r in c.execute(text(sql))]


def etapa_regras(limite: int | None = None) -> dict:
    t0 = time.time()
    pdm = repositorio.ativo()
    indice = IndiceClasses(pdm)
    itens = []
    for m in materiais(limite=limite):
        itens.append((m, extrai_por_regras(pdm, indice, m)))
    with transacao() as c:
        persistir.grava(c, pdm, itens, "regras-v1")
        persistir.atualiza_estatisticas(c)
    return {"registros": len(itens), "segundos": round(time.time() - t0, 1)}
