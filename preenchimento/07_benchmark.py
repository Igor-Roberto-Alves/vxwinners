"""Agrega as predicoes de todas as solucoes num benchmark unico.

Recomputa as metricas exclusivamente a partir de pred/*.csv (nunca confia
em metrica calculada pela propria solucao) e junta custo/tempo de metricas/*.json.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato import CATEGORICOS, METRICAS, PRED, RAIZ, caminho_split, norm_rotulo

# faltantes reais na base (para extrapolar o custo de preencher tudo)
FALTANTES = {"GRUPO_MERCADORIA": 0, "NCM": 1173, "FABRICANTE": 15674,
             "REFERENCIA_FABRICANTE": 18488}

splits = {}

# sentinelas de "nao sei" devolvidas por LLMs: contam como abstencao, por decisao
# explicita (nao por acidente de parsing do pandas)
SENTINELAS = {"NA", "N/A", "NONE", "NULL", "NAN", "-", "NAO INFORMADO", "N A"}


def abst(v):
    return "" if v in SENTINELAS else v


def teste(campo):
    if campo not in splits:
        df = pd.read_csv(caminho_split(campo, "teste"), dtype=str, keep_default_na=False)
        splits[campo] = df.set_index("CODIGO_MATERIAL")["y"]
    return splits[campo]


def f1_macro(y_true, y_pred):
    classes = set(y_true)
    f1s = []
    for c in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == c and p == c)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != c and p == c)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == c and p != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if prec + rec else 0.0)
    return sum(f1s) / len(f1s) if f1s else 0.0


linhas = []
for arq in sorted(PRED.glob("*.csv")):
    solucao, campo = arq.stem.split("__", 1)
    df = pd.read_csv(arq, dtype=str, keep_default_na=False)
    gab = teste(campo)
    n_teste = len(gab)
    df = df[df["CODIGO_MATERIAL"].isin(gab.index)].drop_duplicates("CODIGO_MATERIAL")
    # gabarito sempre do split (nao confia no y_true gravado) + renormaliza y_pred
    df["gab"] = df["CODIGO_MATERIAL"].map(gab)
    df["p"] = df["y_pred"].map(lambda v: abst(norm_rotulo(campo, v)))
    df["t3"] = df["top3"].map(
        lambda v: [abst(norm_rotulo(campo, x)) for x in str(v).split("|") if x.strip()])
    df["t3"] = df["t3"].map(lambda xs: [x for x in xs if x])

    cobertos = df[df["p"] != ""]
    acertos = int((df["p"] == df["gab"]).sum())
    acertos_cob = int((cobertos["p"] == cobertos["gab"]).sum())
    top3_ok = int(sum(1 for g, t in zip(df["gab"], df["t3"]) if g in t))

    meta = {}
    marq = METRICAS / f"{arq.stem}.json"
    if marq.exists():
        meta = json.loads(marq.read_text())

    custo = float(meta.get("custo_estimado_usd") or 0.0)
    seg = float(meta.get("segundos") or 0.0)
    n_pred = len(df)
    linhas.append({
        "solucao": solucao, "campo": campo,
        "n_teste": n_teste, "n_pred": n_pred,
        "cobertura": round(len(cobertos) / n_teste, 4),
        "top1": round(acertos / n_teste, 4),
        "top1_cobertos": round(acertos_cob / len(cobertos), 4) if len(cobertos) else 0.0,
        "top3": round(top3_ok / n_teste, 4),
        "f1_macro": round(f1_macro(list(cobertos["gab"]), list(cobertos["p"])), 4)
        if campo in CATEGORICOS and len(cobertos) else "",
        "segundos": round(seg, 1),
        "tokens_in": int(meta.get("tokens_entrada") or 0),
        "tokens_out": int(meta.get("tokens_saida") or 0),
        "custo_teste_usd": round(custo, 4),
        "usd_por_1k": round(custo / n_pred * 1000, 4) if n_pred else "",
        "custo_preencher_faltantes_usd": round(custo / n_pred * FALTANTES[campo], 2)
        if n_pred and FALTANTES[campo] else 0.0,
        "modelo": meta.get("modelo", ""),
    })

bench = pd.DataFrame(linhas).sort_values(["campo", "top1"], ascending=[True, False])
bench.to_csv(RAIZ / "benchmark.csv", index=False)

for campo in ["GRUPO_MERCADORIA", "NCM", "FABRICANTE", "REFERENCIA_FABRICANTE"]:
    sub = bench[bench["campo"] == campo]
    if sub.empty:
        continue
    print(f"\n=== {campo} (teste={sub.iloc[0]['n_teste']}, faltantes reais={FALTANTES[campo]}) ===")
    cols = ["solucao", "cobertura", "top1", "top1_cobertos", "top3", "f1_macro",
            "segundos", "custo_teste_usd", "usd_por_1k", "custo_preencher_faltantes_usd"]
    print(sub[cols].to_string(index=False))
print(f"\nbenchmark.csv gravado com {len(bench)} linhas")
