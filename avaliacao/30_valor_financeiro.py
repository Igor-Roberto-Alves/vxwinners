"""Valor financeiro da duplicidade como FAIXA, descontando as juncoes erradas (docs/13, V4).

O capital em codigo redundante soma o estoque de todos os codigos que o
pipeline bloqueou, como se toda juncao estivesse certa. Aqui cada cluster e
pesado pela precisao medida da juncao no seu estrato:

  estrato = (classe de referencia | especificacao tecnica)
          x (depende de conclusao do LLM | nao depende)
          x (2 codigos | 3 ou mais)

  capital ajustado = soma por estrato (capital do estrato x precisao do estrato)
  faixa            = mesma conta com os limites do IC 95% de Wilson

Precisao: de avaliacao/gold_juncao.csv quando existir (rotulos MESMO_ITEM /
ITENS_DIFERENTES do gabarito das caracteristicas); senao, do plano B,
avaliacao/amostra_juncao_v4.csv (clusters conferidos um a um: CORRETO /
ERRADO / INDETERMINADO). Estrato com menos de 15 rotulos herda a precisao do
estrato-pai (tipo x LLM) e fica marcado.

Uso: python avaliacao/30_valor_financeiro.py [--artefatos artefatos]
Saida: avaliacao/valor_financeiro.md
"""

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from saneamento import Pdm, ler_base  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--amostra", default=str(RAIZ / "avaliacao/amostra_juncao_v4.csv"))
p.add_argument("--gold", default=str(RAIZ / "avaliacao/gold_juncao.csv"))
p.add_argument("--saida", default=str(RAIZ / "avaliacao/valor_financeiro.md"))
a = p.parse_args()
ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")


def num(s):
    try:
        return float(str(s).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    pp = k / n
    den = 1 + z * z / n
    c = (pp + z * z / (2 * n)) / den
    m = z * math.sqrt(pp * (1 - pp) / n + z * z / (4 * n * n)) / den
    return pp, max(0.0, c - m), min(1.0, c + m)


def brl(v):
    return f"R$ {v / 1e6:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")


base = {str(r["CODIGO_MATERIAL"]): r for r in ler_base(RAIZ / "dados/01_base_materiais.xlsx")}
plano = list(csv.DictReader((ART / "plano_juncao.csv").open(encoding="utf-8")))

# ------------------------------------------------------------------ clusters
clusters = defaultdict(list)
for r in plano:
    clusters[r["CHAVE"]].append(r)


def estrato(chave, membros):
    cid = membros[0]["ID_PDM"]
    tipo = "referencia" if cid and pdm.classes[cid].por_referencia else "tecnica"
    llm = "com_llm" if any(m.get("DEPENDE_DE_LLM") == "1" for m in membros) else "sem_llm"
    tam = "2" if len(membros) == 2 else "3+"
    return (tipo, llm, tam)


cap = {}                       # chave -> capital redundante (codigos bloqueados)
est_de = {}
for chave, membros in clusters.items():
    v = 0.0
    for m in membros:
        if m["ACAO"] == "BLOQUEADO":
            o = base.get(m["CODIGO"], {})
            v += num(o.get("ESTOQUE_ATUAL")) * num(o.get("PRECO_MEDIO_UNITARIO"))
    cap[chave] = v
    est_de[chave] = estrato(chave, membros)

# ------------------------------------------------------------------ rotulos
rotulos = defaultdict(lambda: [0, 0])     # estrato -> [corretos, rotulados]
fonte_rotulos = ""
gold = Path(a.gold)
if gold.exists():
    fonte_rotulos = f"gabarito da juncao ({gold.name})"
    chave_de = {r["CODIGO"]: r["CHAVE"] for r in plano}
    # gold_juncao.csv identifica o par pelo id (CODIGO_MATERIAL = P001...); os
    # codigos estao em pares_juncao_candidatos.csv (codigo_1, codigo_2)
    pares = {}
    arq_pares = gold.parent / "pares_juncao_candidatos.csv"
    if arq_pares.exists():
        for r in csv.DictReader(arq_pares.open(encoding="utf-8")):
            pares[r["par_id"]] = (r["codigo_1"], r["codigo_2"])
    for r in csv.DictReader(gold.open(encoding="utf-8")):
        rot = (r.get("rotulo") or r.get("y_gold") or "").upper()
        c1, c2 = pares.get(r.get("CODIGO_MATERIAL", ""), (r.get("CODIGO_A", ""), r.get("CODIGO_B", "")))
        ca, cb = chave_de.get(c1), chave_de.get(c2)
        if rot not in ("MESMO_ITEM", "ITENS_DIFERENTES") or not ca or ca != cb:
            continue                     # so pares que o pipeline juntou medem precisao
        e = est_de[ca]
        rotulos[e][1] += 1
        rotulos[e][0] += int(rot == "MESMO_ITEM")
elif Path(a.amostra).exists():
    fonte_rotulos = f"amostra interna de clusters conferidos um a um ({Path(a.amostra).name})"
    for r in csv.DictReader(Path(a.amostra).open(encoding="utf-8")):
        rot = r["rotulo"].upper()
        if rot not in ("CORRETO", "ERRADO") or r["chave"] not in est_de:
            continue
        e = est_de[r["chave"]]
        rotulos[e][1] += 1
        rotulos[e][0] += int(rot == "CORRETO")
else:
    sys.exit("sem rotulos: crie avaliacao/gold_juncao.csv ou avaliacao/amostra_juncao_v4.csv")


def precisao(e):
    """Precisao do estrato, ou do estrato-pai (tipo x llm) se houver poucos rotulos."""
    k, n = rotulos[e]
    if n >= 15:
        return wilson(k, n), n, ""
    pai = [x for x in rotulos if x[:2] == e[:2]]
    k, n = sum(rotulos[x][0] for x in pai), sum(rotulos[x][1] for x in pai)
    if n >= 15:
        return wilson(k, n), n, "herdada de " + "/".join(e[:2])
    k, n = sum(v[0] for v in rotulos.values()), sum(v[1] for v in rotulos.values())
    return wilson(k, n), n, "herdada do total"


por_estrato = defaultdict(lambda: {"clusters": 0, "capital": 0.0})
for chave, e in est_de.items():
    por_estrato[e]["clusters"] += 1
    por_estrato[e]["capital"] += cap[chave]

linhas, tot, lo, hi = [], 0.0, 0.0, 0.0
sem_llm = [0.0, 0.0, 0.0]
for e in sorted(por_estrato):
    (pp, plo, phi), n, nota = precisao(e)
    c = por_estrato[e]["capital"]
    tot += c * pp
    lo += c * plo
    hi += c * phi
    if e[1] == "sem_llm":
        sem_llm = [sem_llm[0] + c * pp, sem_llm[1] + c * plo, sem_llm[2] + c * phi]
    linhas.append((e, por_estrato[e]["clusters"], c, rotulos[e][1], pp, plo, phi, nota))

bruto = sum(cap.values())
cap_llm = sum(c for ch, c in cap.items() if est_de[ch][1] == "com_llm")
out = [
    "# Valor financeiro da duplicidade, como faixa",
    "",
    f"Gerado por `avaliacao/30_valor_financeiro.py` sobre `{ART}/plano_juncao.csv`.",
    f"Precisão da junção: {fonte_rotulos}.",
    "",
    "| | Valor |",
    "|---|---|",
    f"| Capital em código redundante, somando todas as junções | {brl(bruto)} |",
    f"| **Capital ajustado pela precisão medida** | **{brl(tot)}** |",
    f"| **Faixa (IC 95%)** | **{brl(lo)} a {brl(hi)}** |",
    f"| Parte que não depende de nenhuma conclusão do LLM | {brl(sem_llm[0])} ({brl(sem_llm[1])} a {brl(sem_llm[2])}) |",
    f"| Capital em clusters que dependem do LLM (bruto) | {brl(cap_llm)} |",
    "",
    "## Por estrato",
    "",
    "| Tipo | LLM | Tamanho | Clusters | Capital bruto | Rótulos | Precisão | IC 95% | Nota |",
    "|---|---|---|---|---|---|---|---|---|",
]
for e, ncl, c, nrot, pp, plo, phi, nota in linhas:
    out.append(f"| {e[0]} | {e[1]} | {e[2]} | {ncl:,} | {brl(c)} | {nrot} | {100 * pp:.1f}% | "
               f"{100 * plo:.1f}–{100 * phi:.1f}% | {nota} |")
out += [
    "",
    "## Frase para o pitch",
    "",
    f"> Entre {brl(lo)} e {brl(hi)} em capital parado em código duplicado (IC 95%), "
    f"dos quais {brl(sem_llm[0])} vêm de junções que não dependem de nenhum modelo de linguagem.",
    "",
    "## Limites",
    "",
    "- A conta usa a precisão da junção, não o recall: duplicidade que o pipeline não achou não está aqui.",
    "- O capital é estoque × preço médio do ERP, sem ajuste de obsolescência.",
    "- Estrato com poucos rótulos herda a precisão do estrato-pai (coluna Nota).",
]
Path(a.saida).write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out[:14]))
print(f"\nGravado: {a.saida}")
