"""Junta os codigos que a chave de identidade prova serem o mesmo item (regra 10).

Nao usa semelhanca de texto em nenhum ponto. Dois codigos entram no mesmo
cluster quando tem a MESMA CHAVE: mesma classe, mesmo substantivo e mesmos
valores em todos os atributos obrigatorios; ou, nas classes de referencia do
fabricante, mesmo fabricante e mesmo part number.

Isso torna cada juncao explicavel numa frase e auditavel linha por linha - que
e a diferenca entre um resultado que a banca aceita e um que ela questiona.

Uso: python 06_juntar.py [--saneado artefatos/saneado_base.csv]
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, ler_base  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--saneado", default=None)
p.add_argument("--exemplos", type=int, default=6)
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")
SANEADO = Path(a.saneado or ART / "saneado_base.csv")
if not SANEADO.exists():
    sys.exit(f"{SANEADO} nao existe: rode scripts/04_extrair.py primeiro")


def num(s):
    try:
        return float(str(s or "0").strip() or 0)
    except ValueError:
        return 0.0


def brl(v):
    return f"R$ {v:>15,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, y):
    return f"{100 * x / y:.1f}%" if y else "-"


# ------------------------------------------------------------------ carga

orig = {r["CODIGO_MATERIAL"]: r for r in ler_base(a.base)}
with SANEADO.open(encoding="utf-8") as fh:
    san = list(csv.DictReader(fh))

for r in san:
    o = orig.get(r["CODIGO_MATERIAL"], {})
    r["_status"] = o.get("STATUS", "")
    r["_estoque"] = num(o.get("ESTOQUE_ATUAL"))
    r["_preco"] = num(o.get("PRECO_MEDIO_UNITARIO"))
    r["_valor"] = r["_estoque"] * r["_preco"]
    r["_mov"] = o.get("DATA_ULTIMA_MOVIMENTACAO", "") or ""
    r["_criacao"] = o.get("DATA_CRIACAO", "") or ""
    r["_centro"] = (o.get("CENTRO", "") or "").split(" - ")[0].strip()

N = len(san)
VALOR_TOTAL = sum(r["_valor"] for r in san)

# ------------------------------------------------------------------ clusters

clusters = defaultdict(list)
for r in san:
    if r["CHAVE_IDENTIDADE"]:
        clusters[r["CHAVE_IDENTIDADE"]].append(r)

multi = {k: v for k, v in clusters.items() if len(v) > 1}


def sobrevivente(grupo):
    """Regra explicita de escolha, na ordem: ativo, completude, movimentacao,
    valor em estoque, codigo mais antigo. Nenhum criterio subjetivo."""
    return sorted(grupo, key=lambda r: (
        r["_status"] != "ATIVO",
        -num(r["COMPLETUDE"]),
        r["_mov"] == "",
        [-ord(c) for c in r["_mov"]] if r["_mov"] else [],
        -r["_valor"],
        r["_criacao"],
    ))[0]


capital = 0.0
dispersao = 0.0
redundantes = 0
multicentro = 0
valor_multicentro = 0.0
risco_parada = 0
plano = []

for chave, grupo in multi.items():
    s = sobrevivente(grupo)
    outros = [r for r in grupo if r is not s]
    redundantes += len(outros)
    capital += sum(r["_valor"] for r in outros)

    precos = [r["_preco"] for r in grupo if r["_preco"] > 0]
    if len(precos) > 1:
        menor = min(precos)
        dispersao += sum((r["_preco"] - menor) * r["_estoque"] for r in grupo)

    if len({r["_centro"] for r in grupo}) > 1:
        multicentro += 1
        valor_multicentro += sum(r["_valor"] for r in grupo)

    if any(r["_estoque"] > 0 for r in grupo) and any(r["_estoque"] == 0 for r in grupo):
        risco_parada += 1

    plano.append({"CODIGO": s["CODIGO_MATERIAL"], "ACAO": "MANTER ATIVO",
                  "USAR": "", "CHAVE": chave, "ID_PDM": s["ID_PDM"],
                  "DESCRICAO_PDM": s["DESCRICAO_PDM"],
                  "ESTOQUE_CONSOLIDADO": sum(r["_estoque"] for r in grupo)})
    for r in outros:
        plano.append({"CODIGO": r["CODIGO_MATERIAL"], "ACAO": "BLOQUEADO",
                      "USAR": s["CODIGO_MATERIAL"], "CHAVE": chave,
                      "ID_PDM": r["ID_PDM"], "DESCRICAO_PDM": r["DESCRICAO_PDM"],
                      "ESTOQUE_CONSOLIDADO": ""})

# ------------------------------------------------------------------ relatorio

com_chave = sum(len(v) for v in clusters.values())
print("=" * 82)
print("JUNCAO POR CHAVE DE IDENTIDADE (REGRA 10)".center(82))
print("=" * 82)
print(f"Registros na base ..................... {N:>9,}")
print(f"Com chave de identidade fechada ....... {com_chave:>9,}  {pct(com_chave, N)}")
print(f"  -> chaves distintas ................. {len(clusters):>9,}")
print(f"  -> chaves com mais de um codigo ..... {len(multi):>9,}")
print(f"  -> CODIGOS REDUNDANTES .............. {redundantes:>9,}  {pct(redundantes, N)} da base")
print(f"Sem chave (falta obrigatorio) ......... {N - com_chave:>9,}  {pct(N - com_chave, N)}")

print()
print("=" * 82)
print("O QUE A JUNCAO LIBERA".center(82))
print("=" * 82)
print(f"CAPITAL em codigo redundante .......... {brl(capital)}  {pct(capital, VALOR_TOTAL)} do estoque")
print(f"DISPERSAO DE PRECO do mesmo item ...... {brl(dispersao)}")
print(f"Clusters em 2+ centros ................ {multicentro:>9,}  (compra fragmentada)")
print(f"  valor negociavel em conjunto ........ {brl(valor_multicentro)}")
print(f"Clusters com risco de parada .......... {risco_parada:>9,}  (um com saldo, outro zerado)")
print(f"Estoque total da base ................. {brl(VALOR_TOTAL)}")

# ---- por criterio de identidade: onde a juncao esta travada
print()
print("=" * 82)
print("ONDE A JUNCAO FUNCIONA E ONDE ESTA TRAVADA".center(82))
print("=" * 82)
por_criterio = defaultdict(lambda: {"total": 0, "com_chave": 0, "redundantes": 0})
redund_por_classe = Counter()
for chave, grupo in multi.items():
    s = sobrevivente(grupo)
    for r in grupo:
        if r is not s:
            redund_por_classe[r["ID_PDM"]] += 1
for r in san:
    cid = r["ID_PDM"]
    if not cid:
        crit = "SEM CLASSE"
    else:
        crit = "REFERENCIA FABRICANTE" if pdm.classes[cid].por_referencia else "ESPECIFICACAO TECNICA"
    por_criterio[crit]["total"] += 1
    if r["CHAVE_IDENTIDADE"]:
        por_criterio[crit]["com_chave"] += 1
for crit, d in sorted(por_criterio.items(), key=lambda x: -x[1]["total"]):
    print(f"{crit:24s} registros {d['total']:>7,}   chave fechada {d['com_chave']:>7,}  "
          f"{pct(d['com_chave'], d['total']):>6}")

print()
print("Classes com mais codigos redundantes encontrados:")
for cid, n in redund_por_classe.most_common(10):
    print(f"   {cid}  {pdm.classes[cid].rotulo():34s} {n:>6,}")

# ---- exemplos
print()
print("=" * 82)
print("EXEMPLOS DE JUNCAO".center(82))
print("=" * 82)
mostrados = 0
for chave, grupo in sorted(multi.items(), key=lambda x: -sum(r["_valor"] for r in x[1])):
    if mostrados >= a.exemplos:
        break
    s = sobrevivente(grupo)
    print("-" * 82)
    print(f"  {len(grupo)} codigos | classe {s['ID_PDM']} | "
          f"capital redundante {brl(sum(r['_valor'] for r in grupo if r is not s)).strip()}")
    print(f"  ANTES:")
    for r in grupo:
        print(f"    {r['CODIGO_MATERIAL']}  {r['_status']:<10} centro {r['_centro']}  "
              f"est {r['_estoque']:>6.0f} x {r['_preco']:>10.2f}  {r['DESCRICAO_ORIGINAL'][:72]}")
    print(f"  DEPOIS:")
    print(f"    {s['CODIGO_MATERIAL']}  ATIVO  {s['DESCRICAO_PDM'][:130]}")
    for r in grupo:
        if r is not s:
            print(f"    {r['CODIGO_MATERIAL']}  BLOQUEADO - USAR {s['CODIGO_MATERIAL']}")
    print(f"  POR QUE: mesma chave -> {chave[:110]}")
    mostrados += 1

# ---- saida
saida = ART / "plano_juncao.csv"
with saida.open("w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["CODIGO", "ACAO", "USAR", "ID_PDM",
                                       "DESCRICAO_PDM", "ESTOQUE_CONSOLIDADO", "CHAVE"])
    w.writeheader()
    for linha in plano:
        w.writerow(linha)
print(f"\nGravado: {saida}  ({len(plano)} linhas de plano de juncao)")
