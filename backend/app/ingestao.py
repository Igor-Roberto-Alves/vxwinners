"""Fase 0: importa a base legada, os pedidos, o PDM e a tabela oficial da NCM.

A base entra como cópia fiel do ERP: nada é corrigido aqui. Reexecutar é seguro
(upsert pela chave), e não apaga classificação nem atributos já extraídos.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import openpyxl
from sqlalchemy import Connection, text


def _txt(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _data(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def _linhas(caminho: Path, aba: str):
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    it = wb[aba].iter_rows(values_only=True)
    cab = [str(c).strip() for c in next(it)]
    for r in it:
        if any(c is not None for c in r):
            yield dict(zip(cab, r))


def importa_base(conn: Connection, xlsx: Path, lote: int = 2000) -> int:
    sql = text("""
        insert into material (codigo, descricao_curta, descricao_longa, unidade, ncm, grupo, fabricante,
            referencia_fabricante, centro, status, data_criacao, usuario_criacao,
            data_ultima_movimentacao, estoque, preco_medio)
        values (:codigo, :curta, :longa, :un, :ncm, :grupo, :fab, :ref, :centro, :status, :criacao,
            :usuario, :mov, :estoque, :preco)
        on conflict (codigo) do update set
            descricao_curta = excluded.descricao_curta, descricao_longa = excluded.descricao_longa,
            unidade = excluded.unidade, ncm = excluded.ncm, grupo = excluded.grupo, fabricante = excluded.fabricante,
            referencia_fabricante = excluded.referencia_fabricante, centro = excluded.centro,
            status = excluded.status, data_criacao = excluded.data_criacao, usuario_criacao = excluded.usuario_criacao,
            data_ultima_movimentacao = excluded.data_ultima_movimentacao, estoque = excluded.estoque,
            preco_medio = excluded.preco_medio""")
    buf, total = [], 0
    for r in _linhas(xlsx, "BASE_MATERIAIS"):
        buf.append({
            "codigo": _txt(r["CODIGO_MATERIAL"]), "curta": _txt(r["DESCRICAO_CURTA"]),
            "longa": _txt(r["DESCRICAO_LONGA"]), "un": _txt(r["UNIDADE_MEDIDA"]), "ncm": _txt(r["NCM"]),
            "grupo": _txt(r["GRUPO_MERCADORIA"]), "fab": _txt(r["FABRICANTE"]),
            "ref": _txt(r["REFERENCIA_FABRICANTE"]), "centro": _txt(r["CENTRO"]), "status": _txt(r["STATUS"]),
            "criacao": _data(r["DATA_CRIACAO"]), "usuario": _txt(r["USUARIO_CRIACAO"]),
            "mov": _data(r["DATA_ULTIMA_MOVIMENTACAO"]), "estoque": _num(r["ESTOQUE_ATUAL"]),
            "preco": _num(r["PRECO_MEDIO_UNITARIO"]),
        })
        if len(buf) >= lote:
            conn.execute(sql, buf)
            total += len(buf)
            buf = []
    if buf:
        conn.execute(sql, buf)
        total += len(buf)
    return total


def importa_pedidos(conn: Connection, xlsx: Path) -> int:
    sql = text("""
        insert into pedido (id, data_solicitacao, centro, area, canal, urgencia, texto, tipo_anexo, conteudo_anexo)
        values (:id, :data, :centro, :area, :canal, :urg, :texto, :tipo, :anexo)
        on conflict (id) do update set data_solicitacao = excluded.data_solicitacao, centro = excluded.centro,
            area = excluded.area, canal = excluded.canal, urgencia = excluded.urgencia, texto = excluded.texto,
            tipo_anexo = excluded.tipo_anexo, conteudo_anexo = excluded.conteudo_anexo""")
    linhas = [{
        "id": _txt(r["ID_PEDIDO"]), "data": _data(r["DATA_SOLICITACAO"]), "centro": _txt(r["CENTRO"]),
        "area": _txt(r["AREA_SOLICITANTE"]), "canal": _txt(r["CANAL"]), "urg": _txt(r["URGENCIA"]),
        "texto": _txt(r["TEXTO_SOLICITACAO"]), "tipo": _txt(r["TIPO_ANEXO"]), "anexo": _txt(r["CONTEUDO_ANEXO"]),
    } for r in _linhas(xlsx, "PEDIDOS")]
    conn.execute(sql, linhas)
    return len(linhas)


# Equivalências documentadas no briefing/dados (regra 13): registradas, nunca usadas para unir códigos.
EQUIVALENCIAS_SEMENTE = [
    ("CATERPILLAR", "1R1808", "DONALDSON", "P551808", "docs/01-dados.md: filtros intercambiaveis do conjunto real"),
]


def semeia_equivalencias(conn: Connection) -> None:
    for a_f, a_r, b_f, b_r, fonte in EQUIVALENCIAS_SEMENTE:
        conn.execute(text("""
            insert into equivalencia (a_fabricante, a_referencia, b_fabricante, b_referencia, fonte)
            values (:af, :ar, :bf, :br, :fonte) on conflict do nothing"""),
            {"af": a_f, "ar": a_r, "bf": b_f, "br": b_r, "fonte": fonte})
