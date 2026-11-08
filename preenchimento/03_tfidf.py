"""03_tfidf.py - solucao 'tfidf_lr': ML classico sem API.

- GRUPO_MERCADORIA, NCM, FABRICANTE: TF-IDF (word 1-2 + char_wb 3-5, uniao) +
  LogisticRegression com predict_proba (conf = prob top1, top3 = 3 classes mais provaveis).
- REFERENCIA_FABRICANTE: recuperacao por vizinho lexical (NearestNeighbors cosine
  sobre o TF-IDF do treino) - estrategia de copia do y do vizinho mais proximo.

Ajuste exclusivamente no split de treino; y do teste usado apenas como y_true.
Uso: python 03_tfidf.py [--amostra N] [--campos C1 C2 ...]
     --amostra N: validacao com N linhas de treino/teste, grava como solucao
                  temporaria 'tmp_valida' (apagar depois).
"""
import argparse
import time
import warnings

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

from contrato import (
    CAMPOS,
    RAIZ,
    SEED,
    caminho_split,
    norm_rotulo,
    salvar_meta,
    salvar_pred,
    texto_entrada,
)

SOLUCAO = "tfidf_lr"
LOG = RAIZ / "03_tfidf.log"


def log(msg: str):
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(linha, flush=True)
    with open(LOG, "a") as f:
        f.write(linha + "\n")


def carregar(campo: str, parte: str, nrows=None) -> pd.DataFrame:
    return pd.read_csv(
        caminho_split(campo, parte), dtype=str, keep_default_na=False, nrows=nrows
    )


def textos(df: pd.DataFrame, campo: str) -> list[str]:
    incluir = campo != "GRUPO_MERCADORIA"
    return [texto_entrada(r, incluir_grupo=incluir) for _, r in df.iterrows()]


def vetorizar(txt_treino: list[str], txt_teste: list[str]):
    """Uniao TF-IDF word(1,2) + char_wb(3,5), min_df=2, fit so no treino."""
    vw = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2)
    vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)
    Xtr = sp.hstack([vw.fit_transform(txt_treino), vc.fit_transform(txt_treino)], format="csr")
    Xte = sp.hstack([vw.transform(txt_teste), vc.transform(txt_teste)], format="csr")
    return Xtr, Xte


def montar_pred(te: pd.DataFrame, campo: str, y_pred, conf, top3_listas) -> pd.DataFrame:
    linhas = []
    for i in range(len(te)):
        itens, vistos = [], set()
        for c in top3_listas[i]:
            c = norm_rotulo(campo, c)
            if c and c not in vistos:
                vistos.add(c)
                itens.append(c)
        linhas.append(
            {
                "CODIGO_MATERIAL": te["CODIGO_MATERIAL"].iloc[i],
                "y_true": te["y"].iloc[i],
                "y_pred": norm_rotulo(campo, y_pred[i]),
                "conf": float(conf[i]),
                "top3": "|".join(itens[:3]),
            }
        )
    return pd.DataFrame(linhas)


def classificar(campo: str, solucao: str, nrows=None):
    t0 = time.time()
    tr = carregar(campo, "treino", nrows)
    te = carregar(campo, "teste", nrows)
    log(f"{campo}: treino={len(tr)} teste={len(te)} - vetorizando...")
    Xtr, Xte = vetorizar(textos(tr, campo), textos(te, campo))
    log(f"{campo}: X treino {Xtr.shape}, teste {Xte.shape} - ajustando LogisticRegression (lbfgs)...")

    solver = "lbfgs"
    clf = LogisticRegression(max_iter=3000, n_jobs=-1)
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always", ConvergenceWarning)
        clf.fit(Xtr, tr["y"])
        nao_convergiu = any(issubclass(w.category, ConvergenceWarning) for w in avisos)
    if nao_convergiu:
        log(f"{campo}: lbfgs nao convergiu em 3000 iter - refazendo com saga tol=1e-3...")
        solver = "saga"
        clf = LogisticRegression(solver="saga", tol=1e-3, max_iter=3000, n_jobs=-1, random_state=SEED)
        clf.fit(Xtr, tr["y"])
    log(f"{campo}: ajuste concluido ({time.time() - t0:.0f}s, solver={solver}, {len(clf.classes_)} classes) - prevendo...")

    proba = clf.predict_proba(Xte)
    ordem = np.argsort(-proba, axis=1)[:, :3]
    y_pred = clf.classes_[ordem[:, 0]]
    conf = proba[np.arange(len(te)), ordem[:, 0]]
    top3 = [[clf.classes_[j] for j in ordem[i]] for i in range(len(te))]

    df = montar_pred(te, campo, y_pred, conf, top3)
    segundos = time.time() - t0
    salvar_pred(solucao, campo, df)
    salvar_meta(
        solucao,
        campo,
        segundos=round(segundos, 1),
        chamadas_api=0,
        tokens_entrada=0,
        tokens_saida=0,
        modelo="",
        custo_estimado_usd=0.0,
        observacoes=(
            f"TF-IDF uniao word(1,2)+char_wb(3,5) min_df=2 ({Xtr.shape[1]} dims, fit so no treino) "
            f"+ LogisticRegression(max_iter=3000, solver={solver}); conf=prob top1, "
            f"top3=3 classes mais provaveis; sem API."
        ),
    )
    log(f"{campo}: salvo ({segundos:.0f}s)")


def referencia_vizinho(campo: str, solucao: str, nrows=None):
    t0 = time.time()
    tr = carregar(campo, "treino", nrows)
    te = carregar(campo, "teste", nrows)
    log(f"{campo}: treino={len(tr)} teste={len(te)} - vetorizando...")
    Xtr, Xte = vetorizar(textos(tr, campo), textos(te, campo))
    log(f"{campo}: X treino {Xtr.shape} - NearestNeighbors cosine...")

    nn = NearestNeighbors(n_neighbors=min(3, len(tr)), metric="cosine")
    nn.fit(Xtr)
    dist, idx = nn.kneighbors(Xte)
    y_tr = tr["y"].to_numpy()
    y_pred = y_tr[idx[:, 0]]
    conf = np.clip(1.0 - dist[:, 0], 0.0, 1.0)
    top3 = [[y_tr[j] for j in idx[i]] for i in range(len(te))]

    df = montar_pred(te, campo, y_pred, conf, top3)
    segundos = time.time() - t0
    salvar_pred(solucao, campo, df)
    salvar_meta(
        solucao,
        campo,
        segundos=round(segundos, 1),
        chamadas_api=0,
        tokens_entrada=0,
        tokens_saida=0,
        modelo="",
        custo_estimado_usd=0.0,
        observacoes=(
            "Recuperacao por vizinho lexical: NearestNeighbors(metric='cosine') sobre TF-IDF "
            "uniao word(1,2)+char_wb(3,5) do treino; y_pred = copia do y do vizinho 1, "
            "conf = 1 - distancia, top3 = y dos vizinhos 1-3. Estrategia de COPIA: so funciona "
            "para itens quase-duplicados do treino, nao generaliza para referencias ineditas; sem API."
        ),
    )
    log(f"{campo}: salvo ({segundos:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--amostra", type=int, default=0, help="N linhas p/ validacao (0 = tudo)")
    ap.add_argument("--campos", nargs="*", default=CAMPOS)
    args = ap.parse_args()

    nrows = args.amostra or None
    solucao = "tmp_valida" if nrows else SOLUCAO
    log(f"=== inicio {solucao} | campos={args.campos} | amostra={nrows or 'completa'} ===")
    for campo in args.campos:
        if campo == "REFERENCIA_FABRICANTE":
            referencia_vizinho(campo, solucao, nrows)
        else:
            classificar(campo, solucao, nrows)
    log(f"=== fim {solucao} ===")


if __name__ == "__main__":
    main()
