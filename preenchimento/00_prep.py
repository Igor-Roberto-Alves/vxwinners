"""Prepara o benchmark: converte xlsx, perfila a falta de dados e congela os splits.

Avaliacao por mascaramento: linhas onde o campo ESTA preenchido viram
treino/teste (o valor conhecido e o ground truth); o teste fica congelado
para todas as solucoes.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato import (CAMPOS, DADOS, ENTRADAS, N_TESTE, SEED,
                      caminho_split, norm_ref, norm_rotulo)

REPO = Path(__file__).resolve().parent.parent

base = pd.read_excel(REPO / "dados/01_base_materiais.xlsx",
                     sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
base.to_csv(DADOS / "base.csv", index=False)

for aba, nome in [("CLASSES", "pdm_classes"), ("NCM_REFERENCIA", "pdm_ncm_referencia"),
                  ("GRUPOS_MERCADORIA", "pdm_grupos"),
                  ("SUBSTANTIVOS_SOBRESSALENTES", "pdm_subst_sobressalentes"),
                  ("SUBSTANTIVOS_CONEXOES", "pdm_subst_conexoes")]:
    try:
        df = pd.read_excel(REPO / "dados/03_padrao_cadastro_PDM.xlsx",
                           sheet_name=aba, dtype=str).fillna("")
        df.to_csv(DADOS / f"{nome}.csv", index=False)
    except Exception as e:
        print(f"aba {aba}: {e}")

resumo = {"n_linhas": len(base), "colunas": list(base.columns)}
rng = np.random.RandomState(SEED)

for campo in CAMPOS:
    y = base[campo].map(lambda v: norm_rotulo(campo, v))
    elegiveis = base.index[y != ""].values
    idx = rng.permutation(elegiveis)
    n_t = min(N_TESTE[campo], len(idx) // 3)
    teste, treino = idx[:n_t], idx[n_t:]
    cols = ["CODIGO_MATERIAL"] + ENTRADAS + (
        ["GRUPO_MERCADORIA"] if campo != "GRUPO_MERCADORIA" else [])
    for parte, ind in (("treino", treino), ("teste", teste)):
        df = base.loc[ind, cols].copy()
        df["y"] = y.loc[ind].values
        df.to_csv(caminho_split(campo, parte), index=False)
    resumo[campo] = {
        "preenchidos": int((y != "").sum()),
        "faltantes": int((y == "").sum()),
        "classes_distintas": int(pd.Series(y[y != ""]).nunique()),
        "n_treino": len(treino),
        "n_teste": len(teste),
    }

# teto de extracao: % do teste em que o rotulo aparece dentro do texto descritivo
for campo in ("FABRICANTE", "REFERENCIA_FABRICANTE"):
    t = pd.read_csv(caminho_split(campo, "teste"), dtype=str).fillna("")
    txt = (t["DESCRICAO_CURTA"] + " " + t["DESCRICAO_LONGA"]).map(norm_ref)
    alvo = t["y"].map(norm_ref)
    dentro = [a in x for a, x in zip(alvo, txt) if a]
    resumo[campo]["teto_extraivel_no_texto"] = round(float(np.mean(dentro)), 4)

(DADOS / "resumo_prep.json").write_text(json.dumps(resumo, indent=1, ensure_ascii=False))
print(json.dumps(resumo, indent=1, ensure_ascii=False))
