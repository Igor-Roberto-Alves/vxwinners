"""Leitura das planilhas do desafio.

Le xlsx direto (openpyxl) ou csv, e devolve lista de dict com as colunas como
texto. NCM permanece string para nao perder zero a esquerda, e numero fica como
veio para a analise financeira decidir o tipo.
"""

from __future__ import annotations

import csv
from pathlib import Path


def _de_xlsx(caminho: Path, aba: str) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    ws = wb[aba]
    linhas = ws.iter_rows(values_only=True)
    cab = [str(c).strip() if c is not None else "" for c in next(linhas)]
    out = []
    for linha in linhas:
        if all(c is None for c in linha):
            continue
        out.append({k: ("" if v is None else str(v)) for k, v in zip(cab, linha)})
    wb.close()
    return out


def _de_csv(caminho: Path) -> list[dict]:
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def _ler(caminho: str | Path, aba: str) -> list[dict]:
    p = Path(caminho)
    if p.suffix.lower() in (".xlsx", ".xlsm"):
        return _de_xlsx(p, aba)
    return _de_csv(p)


def ler_base(caminho: str | Path) -> list[dict]:
    """01_base_materiais.xlsx, aba BASE_MATERIAIS (23.554 registros)."""
    return _ler(caminho, "BASE_MATERIAIS")


def ler_pedidos(caminho: str | Path) -> list[dict]:
    """02_pedidos_cadastro.xlsx, aba PEDIDOS (520 pedidos).

    Junta TEXTO_SOLICITACAO com CONTEUDO_ANEXO: em 136 pedidos o texto e so
    "Segue ficha tecnica em anexo." e a informacao esta no anexo.
    """
    pedidos = _ler(caminho, "PEDIDOS")
    for p in pedidos:
        partes = [p.get("TEXTO_SOLICITACAO", ""), p.get("CONTEUDO_ANEXO", "")]
        p["TEXTO_COMPLETO"] = "\n".join(x for x in partes if x).strip()
        # o pipeline espera o vocabulario da base
        p["CODIGO_MATERIAL"] = p.get("ID_PEDIDO", "")
        p["DESCRICAO_LONGA"] = p["TEXTO_COMPLETO"]
        p["DESCRICAO_CURTA"] = p.get("TEXTO_SOLICITACAO", "")[:40]
        p.setdefault("GRUPO_MERCADORIA", "")
        p.setdefault("UNIDADE_MEDIDA", "")
        p.setdefault("NCM", "")
        p.setdefault("FABRICANTE", "")
        p.setdefault("REFERENCIA_FABRICANTE", "")
    return pedidos
