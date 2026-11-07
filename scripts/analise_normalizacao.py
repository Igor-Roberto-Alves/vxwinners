"""Mede o ganho da camada de normalizacao na deteccao de duplicidade.

Compara: casamento ingenuo de texto  vs  casamento apos normalizacao.
E a prova quantitativa da tese do projeto.

Uso:  uv run --with openpyxl python -I scripts/analise_normalizacao.py
      (opcional) ... <base_materiais.xlsx> <pedidos.xlsx>

Sem argumentos, le os arquivos de dados/ na raiz do repositorio.
"""

import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

DADOS = Path(__file__).resolve().parent.parent / "dados"
BASE_XLSX = sys.argv[1] if len(sys.argv) > 1 else DADOS / "01_base_materiais.xlsx"
PEDIDOS_XLSX = sys.argv[2] if len(sys.argv) > 2 else DADOS / "02_pedidos_cadastro.xlsx"


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


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# ---- dicionarios de normalizacao (o "conhecimento de dominio" do projeto) ----

ABREV = {
    "PARAF": "PARAFUSO", "SEXT": "SEXTAVADO", "HIDR": "HIDRAULICA", "INT": "INTERNO",
    "MANG": "MANGUEIRA", "DIAM": "DIAMETRO", "MONT": "MONTADA", "REF": "REFERENCIA",
    "APLIC": "APLICACAO", "MOD": "MODELO", "MAT": "MATERIAL", "INOX": "ACOINOX",
    "ROL": "ROLAMENTO", "COMP": "COMPRIMENTO", "LUBR": "LUBRIFICANTE",
    "FABR": "FABRICANTE", "EXT": "EXTERNO", "RET": "RETENTOR", "VALV": "VALVULA",
    "ESF": "ESFERA", "CONEX": "CONEXAO", "VED": "VEDACAO", "ELET": "ELETRICO",
    "PNEUM": "PNEUMATICO", "GALV": "GALVANIZADO", "ZINC": "ZINCADO",
    "CIL": "CILINDRICO", "QUAD": "QUADRADO", "RED": "REDUCAO", "FLG": "FLANGE",
}

# aco inox: AISI 316 == INOX 316 == A4 == SS316
SINONIMOS = {
    "AISI316": "ACOINOX316", "SS316": "ACOINOX316", "A4": "ACOINOX316",
    "INOX316": "ACOINOX316", "ACOINOX316": "ACOINOX316", "CF8M": "ACOINOX316",
    "AISI304": "ACOINOX304", "SS304": "ACOINOX304", "A2": "ACOINOX304",
    "INOX304": "ACOINOX304",
    "BUNAN": "NBR", "NITRILICA": "NBR", "NITRILICO": "NBR",
    "VITON": "FKM", "TEFLON": "PTFE",
    "2RSH": "VEDBORRACHA", "2RS": "VEDBORRACHA", "DDU": "VEDBORRACHA",
    "2HRS": "VEDBORRACHA", "RS": "VEDBORRACHA",
    "2Z": "VEDMETAL", "ZZ": "VEDMETAL", "Z": "VEDMETAL",
    "HDG": "GALVANIZADOAFOGO",
    "WCB": "ACOCARBONOFUNDIDO", "A216": "ACOCARBONOFUNDIDO",
    "A105": "ACOCARBONOFORJADO",
}

# tabela DN <-> polegada: a duplicidade-exemplo do briefing (2POL == DN 50)
DN_POL = {
    "6": "1/4POL", "8": "5/16POL", "10": "3/8POL", "15": "1/2POL", "20": "3/4POL",
    "25": "1POL", "32": "1.1/4POL", "40": "1.1/2POL", "50": "2POL", "65": "2.1/2POL",
    "80": "3POL", "100": "4POL", "125": "5POL", "150": "6POL", "200": "8POL",
    "250": "10POL", "300": "12POL",
}
POL_CANON = {
    "1/4": "1/4POL", "5/16": "5/16POL", "3/8": "3/8POL", "1/2": "1/2POL",
    "3/4": "3/4POL", "1": "1POL", "1.1/4": "1.1/4POL", "1 1/4": "1.1/4POL",
    "1.1/2": "1.1/2POL", "1 1/2": "1.1/2POL", "2": "2POL", "2.1/2": "2.1/2POL",
    "3": "3POL", "4": "4POL", "5": "5POL", "6": "6POL", "8": "8POL",
}

RUIDO = {
    "DE", "DO", "DA", "COM", "SEM", "PARA", "EM", "E", "A", "O", "TIPO", "C",
    "POR", "NA", "NO", "AO", "UM", "UMA", "QUE", "SE",
}


def normaliza(desc):
    """Normalizacao determinista: texto -> saco de tokens canonicos."""
    s = sem_acento(desc).upper()

    # DN 50 -> 2POL  (antes de quebrar em tokens)
    def _dn(m):
        return " " + DN_POL.get(m.group(1), m.group(0)) + " "

    s = re.sub(r"\bDN\s*(\d+)\b", _dn, s)

    # 2" / 3/4" / 1-1/4" -> forma canonica em POL
    def _pol(m):
        return " " + POL_CANON.get(m.group(1).replace("-", ".").strip(), m.group(0)) + " "

    s = re.sub(r"\b(\d+(?:[ .-]\d+/\d+)?|\d+/\d+)\s*(?:\"|POL\b|POLEGADAS?\b)", _pol, s)

    # psi -> bar (inteiro), tratando ponto como separador de milhar
    def _psi(m):
        v = float(m.group(1).replace(".", "").replace(",", "."))
        return f" {round(v / 14.5038)}BAR "

    s = re.sub(r"\b([\d.,]+)\s*PSI\b", _psi, s)

    # junta "ACO INOX 316" / "AISI 316" num token antes do dicionario
    s = re.sub(r"\bACO\s+INOX\s*", " ACOINOX", s)
    s = re.sub(r"\bAISI\s*", " AISI", s)
    s = re.sub(r"\bINOX\s*(\d{3})", r" ACOINOX\1", s)

    # M12X50 -> M12 50MM  (regra 2 do PDM)
    s = re.sub(r"\bM\s*-?\s*(\d+)\s*[X*]\s*(\d+)\b", r" M\1 \2MM ", s)
    s = re.sub(r"\bM\s*-\s*(\d+)\b", r" M\1 ", s)

    # unifica notacao de milimetro
    s = re.sub(r"(\d+)[.,](\d+)\s*MM\b", r"\1,\2MM", s)
    s = re.sub(r"(\d+)\s+MM\b", r"\1MM", s)

    toks = re.sub(r"[^A-Z0-9/.,]+", " ", s).split()

    out = set()
    for t in toks:
        t = t.strip(".,")
        if not t or t in RUIDO:
            continue
        t = ABREV.get(t, t)
        t = SINONIMOS.get(t, t)
        out.add(t)
    return frozenset(out)


PONT = re.compile(r"[^A-Z0-9]+")


def ingenuo(desc):
    return frozenset(PONT.sub(" ", sem_acento(desc).upper()).split())


# ---------------------------------------------------------------- carga

linhas = le_xlsx(BASE_XLSX, "BASE_MATERIAIS")
for r in linhas:
    est = float(r["ESTOQUE_ATUAL"] or 0)
    pr = float(r["PRECO_MEDIO_UNITARIO"] or 0)
    r["_valor"] = est * pr
    r["_estoque"] = est
    r["_preco"] = pr


def agrupa(fn):
    cl = defaultdict(list)
    for r in linhas:
        cl[(r["GRUPO_MERCADORIA"], fn(r["DESCRICAO_LONGA"]))].append(r)
    return {k: v for k, v in cl.items() if len(v) > 1}


def mede(cl):
    redundantes, capital, disp = 0, 0.0, 0.0
    for v in cl.values():
        o = sorted(v, key=lambda r: (r["STATUS"] != "ATIVO", -r["_valor"]))
        redundantes += len(o) - 1
        capital += sum(r["_valor"] for r in o[1:])
        pp = [r["_preco"] for r in v if r["_preco"] > 0]
        if len(pp) > 1:
            menor = min(pp)
            disp += sum((r["_preco"] - menor) * r["_estoque"] for r in v)
    return redundantes, capital, disp


def brl(v):
    return f"R$ {v:>14,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


cl_a = agrupa(ingenuo)
cl_b = agrupa(normaliza)
ra, ca, da = mede(cl_a)
rb, cb, db = mede(cl_b)

print("=" * 78)
print("GANHO DA CAMADA DE NORMALIZACAO".center(78))
print("=" * 78)
print(f"{'':38} {'ingenuo':>16} {'normalizado':>16}")
print("-" * 78)
print(f"{'Clusters de duplicidade':38} {len(cl_a):>16,} {len(cl_b):>16,}")
print(f"{'Codigos envolvidos':38} {sum(len(v) for v in cl_a.values()):>16,} {sum(len(v) for v in cl_b.values()):>16,}")
print(f"{'Codigos redundantes':38} {ra:>16,} {rb:>16,}")
print(f"{'Capital parado detectado':38} {brl(ca):>16} {brl(cb):>16}")
print(f"{'Dispersao de preco detectada':38} {brl(da):>16} {brl(db):>16}")
print("-" * 78)
if ra:
    print(f"{'GANHO EM DETECCAO':38} {'base':>16} {f'+{100.0 * (rb - ra) / ra:.0f}%':>16}")
print(f"{'Capital adicional revelado':38} {'':>16} {brl(cb - ca):>16}")

# exemplos novos que a normalizacao capturou
novos = []
for k, v in cl_b.items():
    ks = {ingenuo(r["DESCRICAO_LONGA"]) for r in v}
    if len(ks) > 1:  # cluster que o ingenuo tinha separado
        novos.append(v)

print()
print(f"Clusters que SO a normalizacao encontrou: {len(novos):,}")
print()
print("EXEMPLOS (duplicidade invisivel ao casamento de texto):")
print("-" * 78)
for v in sorted(novos, key=lambda v: -sum(r["_valor"] for r in v))[:8]:
    print(f"  grupo {v[0]['GRUPO_MERCADORIA']} | {len(v)} codigos | valor {brl(sum(r['_valor'] for r in v))}")
    for r in v[:3]:
        print(f"     {r['CODIGO_MATERIAL']}  {r['DESCRICAO_LONGA'][:66]}")
    print()

# ---------------------------------------------------------------- pedidos

pedidos = le_xlsx(PEDIDOS_XLSX, "PEDIDOS")

chaves_base = set(cl_b.keys()) | {(r["GRUPO_MERCADORIA"], normaliza(r["DESCRICAO_LONGA"])) for r in linhas}

print("=" * 78)
print("FLUXO DE CADASTRO (operacao continua)".center(78))
print("=" * 78)
print(f"Pedidos no periodo .................... {len(pedidos):>12,}")
print(f"Com anexo a ler manualmente ........... {sum(1 for p in pedidos if p.get('TIPO_ANEXO', '').strip()):>12,}")
print(f"Urgencia ALTA ou EMERGENCIAL .......... {sum(1 for p in pedidos if p.get('URGENCIA') in ('ALTA', 'EMERGENCIAL')):>12,}")
for canal, n in Counter(p.get("CANAL", "") for p in pedidos).most_common():
    print(f"  canal {canal:<14} ................. {n:>12,}")
print(f"Areas solicitantes distintas .......... {len({p.get('AREA_SOLICITANTE') for p in pedidos}):>12,}")
print(f"Centros solicitantes .................. {len({p.get('CENTRO') for p in pedidos}):>12,}")
