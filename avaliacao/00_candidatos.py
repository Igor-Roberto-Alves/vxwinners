# -*- coding: utf-8 -*-
"""Seleciona os candidatos do conjunto-ouro, estratificados por dificuldade.

Le direto de dados/01_base_materiais.xlsx (independe de branch/artefatos).
Estratos:
  plantados   os 15 produtos reais do fim da base (verdade verificavel externamente)
  typo        erro de digitacao: token a distancia de edicao 1-2 de um fabricante
              canonico, ou marcador de campo digitado errado (REFERENIA, FABRCANTE...)
  ancora      texto com marcador explicito (PN:, COD FABRICANTE, REFERENCIA FABRICANTE:)
              metade com a coluna preenchida, metade com a coluna vazia (faltante-com-evidencia)
  faltante    fabricante E referencia vazios, sem marcador no texto (verdade esperada: AUSENTE)
  abreviacao  descricao telegrafica/cheia de abreviacao (PARAF SEXT, RET., MANG...)
Saida: avaliacao/candidatos.csv com a linha crua completa + estrato + campos_alvo.
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
SEED = 4242

base = pd.read_excel(REPO / "dados/01_base_materiais.xlsx",
                     sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
base["_txt"] = (base["DESCRICAO_CURTA"] + " " + base["DESCRICAO_LONGA"]).str.upper()

canonicos = [n for n in base.loc[base["FABRICANTE"].str.strip() != "", "FABRICANTE"]
             .str.upper().str.strip().unique() if len(n) >= 5]
MARCADORES = ["REFERENCIA", "FABRICANTE", "MARCA"]


def lev(a, b, cap=3):
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > cap:
            return cap + 1
        prev = cur
    return prev[-1]


rng = np.random.RandomState(SEED)
usados = set()
linhas = []


def adiciona(df, estrato, campos, n=None):
    df = df[~df["CODIGO_MATERIAL"].isin(usados)]
    if n is not None and len(df) > n:
        df = df.sample(n, random_state=rng)
    for _, r in df.iterrows():
        usados.add(r["CODIGO_MATERIAL"])
        linhas.append({**{c: r[c] for c in base.columns if not c.startswith("_")},
                       "estrato": estrato, "campos_alvo": campos})


# --- plantados: os 15 ultimos registros (produtos reais) ---
adiciona(base.tail(15), "plantados", "GRUPO_MERCADORIA|NCM|FABRICANTE|REFERENCIA_FABRICANTE")

# --- typo: marca com distancia de edicao 1-2 OU marcador digitado errado ---
def acha_typo(txt):
    toks = set(re.findall(r"[A-Z]{4,}", txt))
    for t in toks:
        for m in MARCADORES:
            if t != m and t[0] == m[0] and lev(t, m, 2) <= 2:
                return f"marcador~{m}:{t}"
        for c in canonicos:
            c0 = c.split()[0]
            if len(c0) >= 5 and t != c0 and t[0] == c0[0] and lev(t, c0, 2) <= 2 \
               and t not in canonicos:
                return f"marca~{c0}:{t}"
    return ""


cand_typo = base.copy()
cand_typo["_typo"] = cand_typo["_txt"].map(acha_typo)
cand_typo = cand_typo[cand_typo["_typo"] != ""]
print(f"typos encontrados na base: {len(cand_typo)}", file=sys.stderr)
adiciona(cand_typo, "typo", "GRUPO_MERCADORIA|FABRICANTE|REFERENCIA_FABRICANTE", n=36)

# --- ancora: marcador explicito no texto ---
marc = base["_txt"].str.contains(
    r"PN[:\s]|P/N|COD(?:IGO)? FAB|REF(?:ERENCIA)?[.:\s]+(?:FAB|DO FAB)|PART ?NUMBER", regex=True)
com_col = base[marc & (base["FABRICANTE"].str.strip() != "") &
               (base["REFERENCIA_FABRICANTE"].str.strip() != "")]
sem_col = base[marc & ((base["FABRICANTE"].str.strip() == "") |
                       (base["REFERENCIA_FABRICANTE"].str.strip() == ""))]
adiciona(com_col, "ancora_com_coluna", "FABRICANTE|REFERENCIA_FABRICANTE", n=20)
adiciona(sem_col, "ancora_coluna_vazia", "FABRICANTE|REFERENCIA_FABRICANTE", n=20)

# --- faltante puro: sem fabricante, sem referencia, sem marcador ---
falt = base[(base["FABRICANTE"].str.strip() == "") &
            (base["REFERENCIA_FABRICANTE"].str.strip() == "") & ~marc]
adiciona(falt, "faltante", "GRUPO_MERCADORIA|FABRICANTE|REFERENCIA_FABRICANTE", n=36)

# --- abreviacao: telegrafico / denso em abreviacoes ---
ABREVS = r"\b(PARAF|SEXT|RET\.?|MANG|ROL(?:\.|\b)|VALV|HIDR|COMPR?\b|DIAM|LUBR|FABR\b|APLIC|MONT|INT\b|EXT\b|CAB\b)"
dens = base["_txt"].str.count(ABREVS)
curto = base["DESCRICAO_LONGA"].str.len() < 60
abre = base[(dens >= 2) | (curto & (dens >= 1))]
adiciona(abre, "abreviacao", "GRUPO_MERCADORIA|NCM", n=50)

df = pd.DataFrame(linhas)
df.to_csv(RAIZ / "candidatos.csv", index=False)
res = df.groupby("estrato").size()
tot_rotulos = sum(len(c.split("|")) for c in df["campos_alvo"])
print(res.to_string())
print(f"itens: {len(df)} | rotulos previstos: {tot_rotulos}")
