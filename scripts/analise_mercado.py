"""Quantifica o custo da bagunça cadastral a partir da base real.

Uso:  uv run --with openpyxl python -I scripts/analise_mercado.py
      (opcional) ... <base_materiais.xlsx> <padrao_PDM.xlsx>

Sem argumentos, le os arquivos de dados/ na raiz do repositorio.

Todos os numeros deste script saem dos dados entregues no desafio.
Nada aqui e estimativa de mercado.
"""

import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

DADOS = Path(__file__).resolve().parent.parent / "dados"
BASE_XLSX = sys.argv[1] if len(sys.argv) > 1 else DADOS / "01_base_materiais.xlsx"
PDM_XLSX = sys.argv[2] if len(sys.argv) > 2 else DADOS / "03_padrao_cadastro_PDM.xlsx"

# ---------------------------------------------------------------- utilidades


def le_xlsx(caminho, aba):
    """Le uma aba do xlsx como lista de dicts, tudo em texto.

    Manter texto preserva zero a esquerda do NCM e o formato das datas.
    """
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


def sem_acento(s):
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


PONTUACAO = re.compile(r"[^A-Z0-9]+")


def tokens(desc):
    """Saco de palavras normalizado: upper, sem acento, sem pontuacao."""
    t = PONTUACAO.sub(" ", sem_acento(desc).upper()).split()
    return frozenset(t)


def num(s):
    s = (s or "").strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def brl(v):
    return f"R$ {v:>16,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(a, b):
    return f"{(100.0 * a / b):.1f}%" if b else "-"


# ---------------------------------------------------------------- carga

linhas = le_xlsx(BASE_XLSX, "BASE_MATERIAIS")
for r in linhas:
    r["_estoque"] = num(r["ESTOQUE_ATUAL"])
    r["_preco"] = num(r["PRECO_MEDIO_UNITARIO"])
    r["_valor"] = r["_estoque"] * r["_preco"]
    r["_centro"] = r["CENTRO"].split(" - ")[0].strip()
    r["_ncm"] = re.sub(r"\D", "", r["NCM"])

N = len(linhas)
VALOR_TOTAL = sum(r["_valor"] for r in linhas)

print("=" * 78)
print("BASE".center(78))
print("=" * 78)
print(f"Registros ............................. {N:>12,}")
print(f"Valor em estoque (estoque x preco) .... {brl(VALOR_TOTAL)}")
print(f"Registros com estoque > 0 ............. {sum(1 for r in linhas if r['_estoque'] > 0):>12,}")
print(f"Preco medio unitario (mediana) ........ {brl(sorted(r['_preco'] for r in linhas)[N // 2])}")

# ---------------------------------------------------------------- 1. duplicidade

# Cluster = mesmo saco de palavras + mesmo grupo de mercadoria.
# E o piso da duplicidade: nao captura 2POL == DN 50 nem VALV ESF == VALVULA ESFERA.
clusters = defaultdict(list)
for r in linhas:
    clusters[(r["GRUPO_MERCADORIA"], tokens(r["DESCRICAO_LONGA"]))].append(r)

multi = {k: v for k, v in clusters.items() if len(v) > 1}

capital_duplicado = 0.0  # valor nos codigos redundantes (todos menos o sobrevivente)
dispersao_preco = 0.0  # economia por comprar sempre no menor preco do cluster
codigos_redundantes = 0
clusters_multicentro = 0
valor_multicentro = 0.0
risco_parada = 0  # cluster onde um codigo tem estoque e outro, zerado, e o buscado

for v in multi.values():
    # sobrevivente: ATIVO, maior valor em estoque
    ordenado = sorted(v, key=lambda r: (r["STATUS"] != "ATIVO", -r["_valor"]))
    sobrevivente, redundantes = ordenado[0], ordenado[1:]
    codigos_redundantes += len(redundantes)
    capital_duplicado += sum(r["_valor"] for r in redundantes)

    precos = [r["_preco"] for r in v if r["_preco"] > 0]
    if len(precos) > 1:
        menor = min(precos)
        # mesmo item comprado a precos diferentes: o delta e economia direta
        dispersao_preco += sum((r["_preco"] - menor) * r["_estoque"] for r in v)

    if len({r["_centro"] for r in v}) > 1:
        clusters_multicentro += 1
        valor_multicentro += sum(r["_valor"] for r in v)

    com = [r for r in v if r["_estoque"] > 0]
    sem = [r for r in v if r["_estoque"] == 0]
    if com and sem:
        risco_parada += 1

print()
print("=" * 78)
print("1. DUPLICIDADE  (piso: mesmo saco de palavras + mesmo grupo)".center(78))
print("=" * 78)
print(f"Clusters com mais de um codigo ........ {len(multi):>12,}")
print(f"Codigos envolvidos .................... {sum(len(v) for v in multi.values()):>12,}")
print(f"Codigos redundantes (eliminaveis) ..... {codigos_redundantes:>12,}  ({pct(codigos_redundantes, N)} da base)")
print(f"CAPITAL PARADO em codigo redundante ... {brl(capital_duplicado)}  ({pct(capital_duplicado, VALOR_TOTAL)} do estoque)")
print(f"DISPERSAO DE PRECO do mesmo item ...... {brl(dispersao_preco)}")
print(f"Clusters em 2+ centros (fragmentacao) . {clusters_multicentro:>12,}")
print(f"  valor negociavel em conjunto ........ {brl(valor_multicentro)}")
print(f"Clusters com risco de parada .......... {risco_parada:>12,}  (um codigo com saldo, outro zerado)")

dup_exata = sum(1 for _, c in Counter(r["DESCRICAO_LONGA"] for r in linhas).items() if _ and c > 1)
print(f"Descricoes longas 100% identicas ...... {dup_exata:>12,} grupos")

# ---------------------------------------------------------------- 2. estoque travado

travado = [r for r in linhas if r["STATUS"] in ("BLOQUEADO", "OBSOLETO") and r["_estoque"] > 0]
valor_travado = sum(r["_valor"] for r in travado)

sem_mov = [r for r in linhas if not r["DATA_ULTIMA_MOVIMENTACAO"].strip() and r["_estoque"] > 0]
valor_sem_mov = sum(r["_valor"] for r in sem_mov)

print()
print("=" * 78)
print("2. ESTOQUE TRAVADO E MORTO".center(78))
print("=" * 78)
print(f"Itens BLOQUEADO/OBSOLETO com saldo .... {len(travado):>12,}")
print(f"  valor imobilizado ................... {brl(valor_travado)}  ({pct(valor_travado, VALOR_TOTAL)} do estoque)")
print(f"Itens com saldo e sem movimentacao .... {len(sem_mov):>12,}")
print(f"  valor imobilizado ................... {brl(valor_sem_mov)}")

# ---------------------------------------------------------------- 3. risco fiscal

# NCM valido por grupo, direto da aba CLASSES do PDM.
wb = openpyxl.load_workbook(PDM_XLSX, read_only=True, data_only=True)
ncm_por_grupo = defaultdict(set)
ws = wb["CLASSES"]
cab = [c.value for c in next(ws.iter_rows(max_row=1))]
i_grp, i_ncm = cab.index("GRUPO_MERCADORIA"), cab.index("NCM")
for row in ws.iter_rows(min_row=2, values_only=True):
    g, n = row[i_grp], row[i_ncm]
    if g and n:
        for parte in re.findall(r"\d{4}\.?\d{2}\.?\d{2}", str(n)):
            ncm_por_grupo[str(g).strip()].add(re.sub(r"\D", "", parte))
# NCM_REFERENCIA tambem lista NCMs condicionais por classe
todos_ref = set()
if "NCM_REFERENCIA" in wb.sheetnames:
    wsr = wb["NCM_REFERENCIA"]
    for row in wsr.iter_rows(min_row=2, values_only=True):
        for cel in row:
            if cel:
                todos_ref |= {re.sub(r"\D", "", m) for m in re.findall(r"\d{4}\.\d{2}\.\d{2}", str(cel))}

ncm_ausente = [r for r in linhas if not r["_ncm"]]
ncm_fora_formato = [r for r in linhas if r["_ncm"] and not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", r["NCM"].strip())]
ncm_divergente = [
    r for r in linhas
    if r["_ncm"] and ncm_por_grupo.get(r["GRUPO_MERCADORIA"]) and r["_ncm"] not in ncm_por_grupo[r["GRUPO_MERCADORIA"]] and r["_ncm"] not in todos_ref
]

val_aus = sum(r["_valor"] for r in ncm_ausente)
val_div = sum(r["_valor"] for r in ncm_divergente)

print()
print("=" * 78)
print("3. RISCO FISCAL (NCM)".center(78))
print("=" * 78)
print(f"NCM ausente ........................... {len(ncm_ausente):>12,}  valor {brl(val_aus)}")
print(f"NCM fora do formato 0000.00.00 ........ {len(ncm_fora_formato):>12,}")
print(f"NCM divergente da regra da classe ..... {len(ncm_divergente):>12,}  valor {brl(val_div)}")
print(f"BASE FISCAL EXPOSTA (ausente+divergente) {brl(val_aus + val_div)}  ({pct(val_aus + val_div, VALOR_TOTAL)} do estoque)")

# ---------------------------------------------------------------- 4. qualidade descritiva

fora_pdm = sum(1 for r in linhas if not (";" in r["DESCRICAO_LONGA"] and ":" in r["DESCRICAO_LONGA"]))
unidades = Counter(r["UNIDADE_MEDIDA"].strip() for r in linhas)
sem_fabricante = sum(1 for r in linhas if not r["FABRICANTE"].strip())
sem_ref = sum(1 for r in linhas if not r["REFERENCIA_FABRICANTE"].strip())
classes_ref = [r for r in linhas if r["GRUPO_MERCADORIA"] in ("SOB01", "FIL01")]
classes_ref_sem_id = [r for r in classes_ref if not r["FABRICANTE"].strip() or not r["REFERENCIA_FABRICANTE"].strip()]

print()
print("=" * 78)
print("4. QUALIDADE DESCRITIVA".center(78))
print("=" * 78)
print(f"Descricao fora do formato PDM ......... {fora_pdm:>12,}  ({pct(fora_pdm, N)})")
print(f"Unidades de medida distintas .......... {len(unidades):>12,}  (o padrao admite 5)")
print(f"Registros sem FABRICANTE .............. {sem_fabricante:>12,}  ({pct(sem_fabricante, N)})")
print(f"Registros sem REFERENCIA_FABRICANTE ... {sem_ref:>12,}  ({pct(sem_ref, N)})")
print(f"SOB01+FIL01 (identidade = fab+part#) .. {len(classes_ref):>12,}")
print(f"  ...sem fabricante ou sem part number  {len(classes_ref_sem_id):>12,}  ({pct(len(classes_ref_sem_id), len(classes_ref))} dessas classes)")
print(f"  valor nesses registros .............. {brl(sum(r['_valor'] for r in classes_ref_sem_id))}")

# ---------------------------------------------------------------- 5. deriva historica

por_ano = Counter(r["DATA_CRIACAO"][:4] for r in linhas if r["DATA_CRIACAO"])
usuarios = len({r["USUARIO_CRIACAO"] for r in linhas})
anos = sorted(por_ano)
print()
print("=" * 78)
print("5. DERIVA: O PROBLEMA CONTINUA ENTRANDO".center(78))
print("=" * 78)
print(f"Periodo de cadastro ................... {anos[0]} a {anos[-1]}  ({len(anos)} anos)")
print(f"Usuarios que cadastraram .............. {usuarios:>12,}")
print(f"Media de cadastros novos por ano ...... {N // len(anos):>12,}")
ult = [a for a in anos if a >= "2022"]
print(f"Cadastros de 2022 em diante ........... {sum(por_ano[a] for a in ult):>12,}")
for a in anos[-6:]:
    print(f"  {a} .............................. {por_ano[a]:>12,}")

# ---------------------------------------------------------------- resumo

print()
print("=" * 78)
print("RESUMO FINANCEIRO".center(78))
print("=" * 78)
print(f"  Capital parado em duplicidade ....... {brl(capital_duplicado)}")
print(f"  Estoque travado (bloq./obsoleto) .... {brl(valor_travado)}")
print(f"  Dispersao de preco do mesmo item .... {brl(dispersao_preco)}")
print("  " + "-" * 60)
print(f"  GANHO DIRETO ENDERECAVEL ............ {brl(capital_duplicado + valor_travado + dispersao_preco)}")
print(f"  Base fiscal exposta (risco) ......... {brl(val_aus + val_div)}")
print(f"  Valor negociavel em conjunto ........ {brl(valor_multicentro)}")
print()
print(f"  sobre um estoque total de ........... {brl(VALOR_TOTAL)}")
