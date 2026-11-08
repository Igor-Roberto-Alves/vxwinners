"""Grava o resultado da estruturação nas tabelas de leitura (a base legada não é alterada)."""
from __future__ import annotations

from sqlalchemy import Connection, text

from ..identidade.chave import chave_identidade
from ..normalizacao.texto import normaliza, tokens
from ..pdm.modelo import Pdm
from .modelo import Extracao

CONFIANCA_ALTA = 0.9  # só valores com esta confiança fecham chave e alimentam sugestões


def grava(conn: Connection, pdm: Pdm, itens: list[tuple[dict, Extracao]], extrator: str, lote: int = 1000) -> None:
    for i in range(0, len(itens), lote):
        _grava_lote(conn, pdm, itens[i:i + lote], extrator)


def _grava_lote(conn: Connection, pdm: Pdm, itens: list[tuple[dict, Extracao]], extrator: str) -> None:
    codigos = [m["codigo"] for m, _ in itens]
    conn.execute(text("delete from material_atributo where codigo = any(:c)"), {"c": codigos})
    conn.execute(text("delete from material_identidade where codigo = any(:c)"), {"c": codigos})

    classif, atributos, identidades = [], [], []
    for m, ex in itens:
        classif.append({"c": m["codigo"], "i": ex.id_pdm, "n": ex.nome, "conf": ex.confianca_classe,
                        "met": ex.metodo, "v": pdm.versao_id, "e": extrator})
        for nome, v in ex.valores.items():
            if v.valor is None and not v.bruto:
                continue
            atributos.append({"c": m["codigo"], "a": nome, "vb": v.bruto, "v": v.valor, "o": v.origem,
                              "t": v.trecho, "conf": v.confianca})
        if ex.id_pdm and (ex.nome or pdm.classes[ex.id_pdm].por_referencia):
            plano = ex.valores_planos(CONFIANCA_ALTA)
            ch = chave_identidade(pdm, ex.id_pdm, ex.nome or "", plano)
            texto = normaliza(m.get("descricao_longa") or m.get("descricao_curta") or "")
            import json
            identidades.append({"c": m["codigo"], "i": ex.id_pdm, "n": ex.nome, "ativo": m.get("status") == "ATIVO",
                                "ch": ch.texto, "comp": ch.completa, "val": json.dumps(plano, ensure_ascii=False),
                                "tx": texto, "tk": sorted(set(tokens(texto)))})
    conn.execute(text("""
        insert into material_classificacao (codigo, id_pdm, nome, confianca, metodo, pdm_versao_id, extrator, atualizado_em)
        values (:c, :i, :n, :conf, :met, :v, :e, now())
        on conflict (codigo) do update set id_pdm = excluded.id_pdm, nome = excluded.nome,
            confianca = excluded.confianca, metodo = excluded.metodo, pdm_versao_id = excluded.pdm_versao_id,
            extrator = excluded.extrator, atualizado_em = now()"""), classif)
    if atributos:
        conn.execute(text("""insert into material_atributo (codigo, atributo, valor_bruto, valor, origem, trecho, confianca)
            values (:c, :a, :vb, :v, :o, :t, :conf)"""), atributos)
    if identidades:
        conn.execute(text("""insert into material_identidade (codigo, id_pdm, nome, ativo, chave, completa, valores, texto_norm, tokens)
            values (:c, :i, :n, :ativo, :ch, :comp, cast(:val as jsonb), :tx, :tk)"""), identidades)


def atualiza_estatisticas(conn: Connection) -> None:
    conn.execute(text("refresh materialized view estatistica_valor"))
