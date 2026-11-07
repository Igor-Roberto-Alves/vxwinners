"""Treina e serializa os artefatos do servico de sugestao.

Producao: usa TODOS os registros rotulados da base (nao os splits do benchmark).
Vencedores do benchmark: tfidf+LR (grupo 96,5% = teto; NCM 91% top-1 / 99% top-3;
fabricante 82% fallback do lexico) + NN de similares para anti-duplicata.
"""
import json
import sys
import time
from pathlib import Path

import joblib
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
sys.path.insert(0, str(REPO / "preenchimento"))
from contrato import norm_rotulo, norm_texto  # noqa: E402

MOD = RAIZ / "modelos"
MOD.mkdir(exist_ok=True)

base = pd.read_csv(REPO / "preenchimento/dados/base.csv", dtype=str, keep_default_na=False)
base["_txt"] = (base["DESCRICAO_CURTA"].map(norm_texto) + " " +
                base["DESCRICAO_LONGA"].map(norm_texto)).str.strip()
base["_grupo"] = base["GRUPO_MERCADORIA"].map(norm_texto)
base["_txt_g"] = base["_txt"] + " GRUPO " + base["_grupo"].str.replace(" ", "_")


def treina_clf(nome, textos, y):
    t = time.monotonic()
    vw = TfidfVectorizer(ngram_range=(1, 2), min_df=2)
    vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)
    X = sparse.hstack([vw.fit_transform(textos), vc.fit_transform(textos)]).tocsr()
    lr = LogisticRegression(max_iter=3000)
    lr.fit(X, y)
    joblib.dump({"vw": vw, "vc": vc, "lr": lr}, MOD / f"{nome}.joblib", compress=3)
    print(f"{nome}: ok {X.shape} em {time.monotonic()-t:.0f}s", flush=True)


# GRUPO: texto sem o proprio grupo
treina_clf("grupo", base["_txt"], base["_grupo"])

# NCM: texto com grupo como token (igual ao benchmark)
m = base[base["NCM"].map(lambda v: norm_rotulo("NCM", v)) != ""]
treina_clf("ncm", m["_txt_g"], m["NCM"].map(lambda v: norm_rotulo("NCM", v)))

# FABRICANTE: modelo de fallback + lexico canonico
m = base[base["FABRICANTE"].map(norm_texto) != ""]
treina_clf("fabricante", m["_txt_g"], m["FABRICANTE"].map(norm_texto))
freq = m["FABRICANTE"].map(norm_texto).value_counts()
(MOD / "lexico_fabricantes.json").write_text(
    json.dumps({"freq": freq.to_dict()}, ensure_ascii=False))

# SIMILARES: vizinhos lexicais na base inteira (anti-duplicata)
vw = TfidfVectorizer(ngram_range=(1, 2), min_df=2)
X = vw.fit_transform(base["_txt"])
nn = NearestNeighbors(n_neighbors=6, metric="cosine").fit(X)
joblib.dump({"vw": vw, "nn": nn}, MOD / "similares.joblib", compress=3)
base[["CODIGO_MATERIAL", "DESCRICAO_LONGA", "GRUPO_MERCADORIA", "STATUS",
      "UNIDADE_MEDIDA", "NCM"]].to_csv(MOD / "similares_meta.csv", index=False)
print(f"similares: ok {X.shape}", flush=True)
print("TREINO COMPLETO", flush=True)
