# -*- coding: utf-8 -*-
"""V2: sorteia os candidatos do gabarito curto de unidade, descricao e sobrevivente.

Independencia: a saida do pipeline (saneado_base.csv, plano_juncao.csv) e lida
AQUI e SO AQUI, e apenas para decidir QUAIS casos entram (estrato). Nenhuma
coluna de saida do pipeline (UNIDADE_PDM, DESCRICAO_PDM, ID_PDM, CHAVE,
ACAO/USAR, ESTOQUE_CONSOLIDADO) e gravada no candidatos_cadastro.csv: o arquivo
leva so a linha crua da base (dados/01_base_materiais.xlsx), o estrato e,
nos clusters, um identificador neutro do cluster. O anotador ve so isso.

Regra de sorteio (semente fixa SEED, numpy RandomState, uma unica sequencia,
na ordem abaixo; um codigo nunca entra em dois itens de unidade/descricao):

V2.1 UNIDADE (60)
  sinonimo   15  pela UNIDADE_MEDIDA crua: UN 3, PCA 3, PÇ 3, PAR 2, MTS 1, MT 1, LT 2
  embalagem  20  pela UNIDADE_MEDIDA crua: CX 4, JG 4, CT 4, RL 3, BR 3, GL 1, BD 1
  incompativel 15 registros em que o pipeline acusou "classe X exige U"
                 (UNIDADE_MOTIVO), por padrao (crua -> padrao da classe):
                 KG->PC 4, PC->L 2, PC->M 2, UN->M 1, M->PC 1, UN->PR 1,
                 PC->PR 1, PR->PC 1, KG->M 1, UN->L 1
  ja_correta 10  unidade crua basica que o pipeline manteve sem motivo:
                 PC 3, M 2, PR 2, KG 2, L 1
V2.2 DESCRICAO (40)
  10 familias de classe (pelo ID_PDM do pipeline, so para estratificar) x
  (3 SANEADO + 1 PENDENTE). Familias: fixadores, vedacao, rolamentos,
  valvulas, conexoes_tubo, eletricos, mangueiras, filtros (PDM100),
  sobressalentes (PDM110), outras.
V2.3 SOBREVIVENTE (30 clusters do plano_juncao.csv, agrupados por CHAVE)
  multicentro 10  codigos em 2+ centros (CENTRO cru)
  dois        10  2 codigos, um centro so
  tres_a_cinco 10 3 a 5 codigos, um centro so

Uso: uv run --no-project --with pandas --with openpyxl python \
       avaliacao/20_candidatos_cadastro.py [--artefatos DIR]
Saida: avaliacao/candidatos_cadastro.csv
"""
import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
SEED = 20261107

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(REPO / "artefatos"))
a = p.parse_args()
ART = Path(a.artefatos)

base = pd.read_excel(REPO / "dados/01_base_materiais.xlsx",
                     sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
CRUAS = list(base.columns)
base = base.set_index("CODIGO_MATERIAL", drop=False)

san = pd.read_csv(ART / "saneado_base.csv", dtype=str, keep_default_na=False)
plano = pd.read_csv(ART / "plano_juncao.csv", dtype=str, keep_default_na=False)

rng = np.random.RandomState(SEED)
usados = set()
linhas = []


def sorteia(codigos, n):
    codigos = sorted(c for c in set(codigos) if c not in usados and c in base.index)
    if len(codigos) < n:
        raise SystemExit(f"estrato pequeno: {len(codigos)} < {n}")
    return list(rng.choice(codigos, n, replace=False))


def grava(tarefa, item_id, estrato, sub, cod, cluster=""):
    r = base.loc[cod]
    linhas.append({"tarefa": tarefa, "item_id": item_id, "estrato": estrato,
                   "subestrato": sub, "cluster_id": cluster,
                   **{c: r[c] for c in CRUAS}})


# ---------------------------------------------------------------- V2.1 unidade
n_item = 0
um = base["UNIDADE_MEDIDA"].str.strip()
for estrato, alocacao in (
        ("sinonimo", [("UN", 3), ("PCA", 3), ("PÇ", 3), ("PAR", 2), ("MTS", 1),
                      ("MT", 1), ("LT", 2)]),
        ("embalagem", [("CX", 4), ("JG", 4), ("CT", 4), ("RL", 3), ("BR", 3),
                       ("GL", 1), ("BD", 1)])):
    for u, n in alocacao:
        for cod in sorteia(base.index[um == u], n):
            usados.add(cod)
            n_item += 1
            grava("unidade", f"U{n_item:03d}", estrato, u, cod)

incomp = san[san["UNIDADE_MOTIVO"].str.contains(r"^classe PDM\d+ exige", regex=True)]
padrao = incomp["UNIDADE_ORIGINAL"].str.replace("Ç", "C") + "->" + incomp["UNIDADE_PDM"]
for pad, n in [("KG->PC", 4), ("PC->L", 2), ("PC->M", 2), ("UN->M", 1), ("M->PC", 1),
               ("UN->PR", 1), ("PC->PR", 1), ("PR->PC", 1), ("KG->M", 1), ("UN->L", 1)]:
    for cod in sorteia(incomp.loc[padrao == pad, "CODIGO_MATERIAL"], n):
        usados.add(cod)
        n_item += 1
        grava("unidade", f"U{n_item:03d}", "incompativel", pad, cod)

ok = san[(san["UNIDADE_MOTIVO"] == "") & (san["UNIDADE_ORIGINAL"] == san["UNIDADE_PDM"])]
for u, n in [("PC", 3), ("M", 2), ("PR", 2), ("KG", 2), ("L", 1)]:
    for cod in sorteia(ok.loc[ok["UNIDADE_ORIGINAL"] == u, "CODIGO_MATERIAL"], n):
        usados.add(cod)
        n_item += 1
        grava("unidade", f"U{n_item:03d}", "ja_correta", u, cod)

# -------------------------------------------------------------- V2.2 descricao
FAMILIAS = {
    "fixadores": {"PDM001", "PDM002", "PDM003", "PDM004", "PDM005", "PDM006"},
    "vedacao": {"PDM031", "PDM032", "PDM033", "PDM034"},
    "rolamentos": {"PDM020", "PDM021", "PDM022", "PDM023"},
    "valvulas": {"PDM040", "PDM041", "PDM042", "PDM043", "PDM044"},
    "conexoes_tubo": {"PDM050", "PDM051"},
    "eletricos": {"PDM060", "PDM061", "PDM062", "PDM063", "PDM064", "PDM065", "PDM066"},
    "mangueiras": {"PDM010", "PDM011", "PDM012", "PDM013", "PDM014"},
    "filtros": {"PDM100"},
    "sobressalentes": {"PDM110"},
}
ja = set().union(*FAMILIAS.values())


def familia(cid):
    for f, s in FAMILIAS.items():
        if cid in s:
            return f
    return "outras"


d = san[(san["DESCRICAO_PDM"] != "") & (san["ID_PDM"] != "")].copy()
d["_fam"] = d["ID_PDM"].map(familia)
n_item = 0
for fam in list(FAMILIAS) + ["outras"]:
    for estado, n in (("SANEADO", 3), ("PENDENTE", 1)):
        pool = d.loc[(d["_fam"] == fam) & (d["ESTADO"] == estado), "CODIGO_MATERIAL"]
        for cod in sorteia(pool, n):
            usados.add(cod)
            n_item += 1
            grava("descricao", f"D{n_item:03d}", fam, estado, cod)

# ----------------------------------------------------------- V2.3 sobrevivente
centro = base["CENTRO"].str.split(" - ").str[0].str.strip()
grupos = plano.groupby("CHAVE")["CODIGO"].apply(list)
info = []
for chave, cods in grupos.items():
    cods = [c for c in cods if c in base.index]
    nc = len({centro[c] for c in cods})
    info.append((chave, cods, len(cods), nc))
pools = {
    "multicentro": [i for i in info if i[3] > 1],
    "dois": [i for i in info if i[3] == 1 and i[2] == 2],
    "tres_a_cinco": [i for i in info if i[3] == 1 and 3 <= i[2] <= 5],
}
n_cl = 0
for estrato, pool in pools.items():
    pool = sorted(pool, key=lambda i: i[0])
    idx = rng.choice(len(pool), 10, replace=False)
    for j in idx:
        chave, cods, n, nc = pool[j]
        n_cl += 1
        cid = f"S{n_cl:03d}"
        # ordem dos codigos dentro do cluster: embaralhada, para o anotador
        # nao herdar a ordem do plano (o plano lista o sobrevivente primeiro)
        for cod in rng.permutation(sorted(cods)):
            grava("sobrevivente", cid, estrato, f"{n} codigos/{nc} centros", cod, cid)

out = pd.DataFrame(linhas)
out.to_csv(RAIZ / "candidatos_cadastro.csv", index=False, encoding="utf-8")
print(out.groupby(["tarefa", "estrato"]).item_id.nunique().to_string())
print(f"gravado: {RAIZ / 'candidatos_cadastro.csv'} ({len(out)} linhas, semente {SEED})")
