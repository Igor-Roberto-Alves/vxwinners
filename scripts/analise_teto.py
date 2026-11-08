"""Mede o TETO da duplicidade: o que o casamento de texto nao alcanca.

Testa o casamento de texto contra os casos de duplicidade conhecidos
(os 15 produtos reais no fim da base) e estima o teto por chave de atributo.

Uso:  uv run --with openpyxl python -I scripts/analise_teto.py
      (opcional) ... <base_materiais.xlsx>

Sem argumentos, le os arquivos de dados/ na raiz do repositorio.
"""

import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl

DADOS = Path(__file__).resolve().parent.parent / "dados"
BASE_XLSX = sys.argv[1] if len(sys.argv) > 1 else DADOS / "01_base_materiais.xlsx"


def le_xlsx(caminho, aba):
    """Le uma aba do xlsx como lista de dicts, tudo em texto."""
    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    it = wb[aba].iter_rows(values_only=True)
    cab = [str(c).strip() if c is not None else "" for c in next(it)]
    linhas = [
        {k: ("" if v is None else str(v)) for k, v in zip(cab, row)}
        for row in it
        if any(c is not None for c in row)
    ]
    wb.close()
    return linhas


def sa(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


linhas = le_xlsx(BASE_XLSX, "BASE_MATERIAIS")
for r in linhas:
    r["_valor"] = float(r["ESTOQUE_ATUAL"] or 0) * float(r["PRECO_MEDIO_UNITARIO"] or 0)


def brl(v):
    return f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


print("=" * 78)
print("OS 15 PRODUTOS REAIS NO FIM DA BASE (caso-teste do briefing)".center(78))
print("=" * 78)
for r in linhas[-15:]:
    print(f"  {r['CODIGO_MATERIAL']} | {r['GRUPO_MERCADORIA']} | {r['FABRICANTE']:<14} | {r['REFERENCIA_FABRICANTE']:<22} | {brl(r['_valor']):>14}")
    print(f"           {r['DESCRICAO_LONGA'][:95]}")

# ---- o casamento de texto encontra esses pares? ----
PONT = re.compile(r"[^A-Z0-9]+")


def bow(d):
    return frozenset(PONT.sub(" ", sa(d).upper()).split())


cl = defaultdict(list)
for r in linhas:
    cl[(r["GRUPO_MERCADORIA"], bow(r["DESCRICAO_LONGA"]))].append(r)

ultimos = {r["CODIGO_MATERIAL"] for r in linhas[-15:]}
achados = 0
for v in cl.values():
    if len(v) > 1 and any(r["CODIGO_MATERIAL"] in ultimos for r in v):
        achados += 1

print()
print(f"  >> clusters de duplicidade que o casamento de texto encontra entre os 15: {achados}")
print("     (o briefing afirma que ha 2 clusters deliberados: rolamentos 6205 e 6310, e filtros)")

# ---- teto por chave de atributo: identidade = fabricante + part number ----
# Para SOB01/FIL01 o PDM define identidade = FABRICANTE + REFERENCIA (regra 9/10).
# Essa chave e computavel HOJE, sem LLM, nos registros que tem os dois campos.
print()
print("=" * 78)
print("TETO 1: identidade por FABRICANTE + PART NUMBER (regra 10 do PDM)".center(78))
print("=" * 78)

ref_norm = lambda s: re.sub(r"[^A-Z0-9]", "", sa(s or "").upper())

grp = defaultdict(list)
for r in linhas:
    if r["GRUPO_MERCADORIA"] in ("SOB01", "FIL01"):
        f, p = r["FABRICANTE"].strip().upper(), ref_norm(r["REFERENCIA_FABRICANTE"])
        if f and p:
            grp[(f, p)].append(r)

dup_fp = {k: v for k, v in grp.items() if len(v) > 1}
red_fp = sum(len(v) - 1 for v in dup_fp.values())
cap_fp = 0.0
for v in dup_fp.values():
    o = sorted(v, key=lambda r: (r["STATUS"] != "ATIVO", -r["_valor"]))
    cap_fp += sum(r["_valor"] for r in o[1:])

elegiveis = sum(len(v) for v in grp.values())
print(f"  Registros SOB01+FIL01 com fabricante E part number ... {elegiveis:,}")
print(f"  Chaves (fabricante+part#) com mais de um codigo ...... {len(dup_fp):,}")
print(f"  Codigos redundantes por essa chave ................... {red_fp:,}")
print(f"  Capital parado .......................................  {brl(cap_fp)}")
print(f"  Taxa de duplicidade nessa fatia ...................... {100.0 * red_fp / elegiveis:.1f}%")

print()
print("  Os 5 maiores clusters por valor:")
for k, v in sorted(dup_fp.items(), key=lambda kv: -sum(r["_valor"] for r in kv[1]))[:5]:
    print(f"    {k[0]} {k[1]} | {len(v)} codigos | {brl(sum(r['_valor'] for r in v))}")
    for r in v:
        print(f"        {r['CODIGO_MATERIAL']} {r['STATUS']:<9} {r['CENTRO'][:28]:<28} {r['DESCRICAO_LONGA'][:52]}")

# ---- extrapolacao honesta ----
print()
print("=" * 78)
print("EXTRAPOLACAO".center(78))
print("=" * 78)
taxa = red_fp / elegiveis if elegiveis else 0
print(f"  Taxa de duplicidade medida onde a chave do PDM E computavel: {100 * taxa:.1f}%")
print(f"  Registros SOB01+FIL01 SEM fabricante ou part number ........ {8610 - elegiveis:,}")
print("  Nesses, a chave so fecha depois da extracao de atributos (o MVP).")
print(f"  Se a mesma taxa se mantiver nos {8610 - elegiveis:,} registros cegos:")
print(f"     codigos redundantes adicionais ......... ~{round((8610 - elegiveis) * taxa):,}")
val_cego = sum(
    r["_valor"] for r in linhas
    if r["GRUPO_MERCADORIA"] in ("SOB01", "FIL01")
    and (not r["FABRICANTE"].strip() or not ref_norm(r["REFERENCIA_FABRICANTE"]))
)
print(f"     valor em estoque nesses registros ...... {brl(val_cego)}")
print(f"     capital parado estimado ................ ~{brl(val_cego * taxa)}")
