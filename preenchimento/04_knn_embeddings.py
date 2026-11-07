"""04_knn_embeddings.py — solucao 'knn_cohere'.

Embeddings AWS Bedrock Cohere embed v4 + kNN (k=25) em numpy puro.
- Categoricos (GRUPO_MERCADORIA, NCM, FABRICANTE): voto ponderado por similaridade
  (score de classe = soma das similaridades dos vizinhos daquela classe).
- REFERENCIA_FABRICANTE: copia do vizinho 1 (quase-duplicado); top3 = vizinhos 1-3.

Embeddings sao cacheados por campo/parte em cache/emb_{campo}_{parte}.npz;
reexecucao carrega do cache e nao rechama a API.

Uso:
  python 04_knn_embeddings.py --valida        # smoke test minusculo, nao grava nada
  python 04_knn_embeddings.py                 # roda os 4 campos no teste completo
  python 04_knn_embeddings.py --threads 4     # menos paralelismo se throttling dominar
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import numpy as np
import pandas as pd

from bedrock_util import COHERE_EMBED, Contador, embed_cohere
from contrato import (CAMPOS, CACHE, RAIZ, caminho_split, norm_rotulo,
                      salvar_meta, salvar_pred, texto_entrada)

SOLUCAO = "knn_cohere"
K = 25
LOTE = 96
ARQ_LOG = RAIZ / f"{SOLUCAO}.log"
AUTH_ERROS = ("ExpiredToken", "UnrecognizedClient")


def log(msg):
    linha = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(linha, flush=True)
    try:
        with open(ARQ_LOG, "a") as f:
            f.write(linha + "\n")
    except OSError:
        pass


def cod_erro(e):
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        cod = resp.get("Error", {}).get("Code", "")
        if cod:
            return cod
    return type(e).__name__


def monta_textos(df, campo):
    incluir = campo != "GRUPO_MERCADORIA"
    textos = []
    for _, row in df.iterrows():
        t = texto_entrada(row, incluir_grupo=incluir)
        textos.append(t if t.strip() else "SEM DESCRICAO")
    return textos


def embeda(textos, contador, threads, rotulo=""):
    """Embeda em lotes de LOTE com ThreadPoolExecutor; devolve (matriz float32, idx falhas).

    Lote que falha apos todos os retries vira linhas-zero (falha) — abstencao a jusante.
    Se TODAS as chamadas falharem com erro de credencial, aborta com AUTH_AWS.
    """
    n = len(textos)
    lotes = [(i, textos[i:i + LOTE]) for i in range(0, n, LOTE)]
    resultados, erros = {}, {}
    t0 = time.time()
    feitos = 0
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(embed_cohere, ts, contador): i for i, ts in lotes}
        for fut in as_completed(futs):
            i = futs[fut]
            try:
                resultados[i] = np.asarray(fut.result(), dtype=np.float32)
            except Exception as e:
                erros[i] = cod_erro(e)
                log(f"  {rotulo}: lote offset {i} FALHOU apos retries: {erros[i]}")
            feitos += 1
            if feitos % 25 == 0 or feitos == len(lotes):
                log(f"  {rotulo}: {feitos}/{len(lotes)} lotes ({time.time() - t0:.0f}s)")
    if erros and len(erros) == len(lotes) and all(
            any(a in c for a in AUTH_ERROS) for c in erros.values()):
        raise RuntimeError(
            f"AUTH_AWS: todas as {len(lotes)} chamadas de {rotulo} falharam com "
            f"{sorted(set(erros.values()))}")
    dim = next(iter(resultados.values())).shape[1] if resultados else 1
    M = np.zeros((n, dim), dtype=np.float32)
    falhas = []
    for i, ts in lotes:
        if i in resultados:
            M[i:i + len(ts)] = resultados[i]
        else:
            falhas.extend(range(i, i + len(ts)))
    return M, falhas


def embeddings_parte(campo, parte, df, contador, threads):
    """Matriz de embeddings alinhada as linhas de df, com cache npz por campo/parte."""
    arq = CACHE / f"emb_{campo}_{parte}.npz"
    codigos = np.asarray(df["CODIGO_MATERIAL"].astype(str).tolist())  # dtype <U, sem pickle
    if arq.exists():
        d = np.load(arq)
        pos = {c: j for j, c in enumerate(d["codigos"].astype(str).tolist())}
        try:
            idx = np.array([pos[c] for c in codigos.tolist()])
        except KeyError as e:
            raise RuntimeError(f"cache {arq.name} nao cobre o codigo {e}; apague o cache")
        log(f"{campo}/{parte}: embeddings do cache ({len(codigos)} linhas, 0 chamadas API)")
        return d["emb"][idx]
    textos = monta_textos(df, campo)
    log(f"{campo}/{parte}: embedando {len(textos)} textos em lotes de {LOTE}, "
        f"{threads} threads...")
    M, falhas = embeda(textos, contador, threads, rotulo=f"{campo}/{parte}")
    np.savez_compressed(arq, emb=M, codigos=codigos)
    log(f"{campo}/{parte}: cache salvo em {arq.name} ({len(falhas)} linhas com falha)")
    return M


def normaliza(M):
    """L2-normaliza; devolve (matriz, mask de linhas validas). Linha-zero = falha."""
    nrm = np.linalg.norm(M, axis=1)
    ok = nrm > 0
    N = M.astype(np.float32, copy=True)
    N[ok] /= nrm[ok, None]
    return N, ok


def prediz_categorico(Xte, ok_te, Xtr, y_tr):
    """Voto ponderado: score de classe = soma das similaridades dos k vizinhos da classe."""
    classes, ycod = np.unique(y_tr, return_inverse=True)
    k = min(K, Xtr.shape[0])
    S = Xte @ Xtr.T
    preds, confs, top3s = [], [], []
    for i in range(Xte.shape[0]):
        if not ok_te[i]:
            preds.append(""); confs.append(0.0); top3s.append("")
            continue
        s = S[i]
        viz = np.argpartition(-s, k - 1)[:k]
        scores = np.zeros(classes.size)
        np.add.at(scores, ycod[viz], s[viz].astype(np.float64))
        ordem = np.argsort(-scores)
        tot = float(scores.sum())
        cand = [str(classes[j]) for j in ordem[:3] if scores[j] > 0]
        if not cand or tot <= 0:
            preds.append(""); confs.append(0.0); top3s.append("")
            continue
        preds.append(cand[0])
        confs.append(round(min(max(float(scores[ordem[0]]) / tot, 0.0), 1.0), 6))
        top3s.append("|".join(cand))
    return preds, confs, top3s


def prediz_referencia(Xte, ok_te, Xtr, y_tr):
    """Texto livre: y_pred = y do vizinho 1 (quase-duplicado); top3 = vizinhos 1-3."""
    kk = min(3, Xtr.shape[0])
    S = Xte @ Xtr.T
    preds, confs, top3s = [], [], []
    for i in range(Xte.shape[0]):
        if not ok_te[i]:
            preds.append(""); confs.append(0.0); top3s.append("")
            continue
        s = S[i]
        viz = np.argpartition(-s, kk - 1)[:kk]
        viz = viz[np.argsort(-s[viz])]
        rotulos = []
        for j in viz:
            r = str(y_tr[j])
            if r and r not in rotulos:
                rotulos.append(r)
        if not rotulos:
            preds.append(""); confs.append(0.0); top3s.append("")
            continue
        preds.append(rotulos[0])
        confs.append(round(min(max(float(s[viz[0]]), 0.0), 1.0), 6))
        top3s.append("|".join(rotulos[:3]))
    return preds, confs, top3s


def roda_campo(campo, threads):
    t0 = time.time()
    cont = Contador()
    tr = pd.read_csv(caminho_split(campo, "treino"), dtype=str).fillna("")
    te = pd.read_csv(caminho_split(campo, "teste"), dtype=str).fillna("")
    log(f"=== {campo}: treino={len(tr)} teste={len(te)} ===")
    Etr = embeddings_parte(campo, "treino", tr, cont, threads)
    Ete = embeddings_parte(campo, "teste", te, cont, threads)
    Xtr, ok_tr = normaliza(Etr)
    Xte, ok_te = normaliza(Ete)
    y_tr = tr["y"].to_numpy()
    Xtr_v, y_tr_v = Xtr[ok_tr], y_tr[ok_tr]
    if campo == "REFERENCIA_FABRICANTE":
        preds, confs, top3s = prediz_referencia(Xte, ok_te, Xtr_v, y_tr_v)
    else:
        preds, confs, top3s = prediz_categorico(Xte, ok_te, Xtr_v, y_tr_v)
    out = pd.DataFrame({
        "CODIGO_MATERIAL": te["CODIGO_MATERIAL"],
        "y_true": te["y"],
        "y_pred": [norm_rotulo(campo, p) for p in preds],
        "conf": confs,
        "top3": ["|".join(v for v in (norm_rotulo(campo, c) for c in t.split("|")) if v)
                 if t else "" for t in top3s],
    })
    seg = round(time.time() - t0, 1)
    n_abst = int((out["y_pred"] == "").sum())
    falhas_tr = int((~ok_tr).sum())
    falhas_te = int((~ok_te).sum())
    obs = ("kNN k=%d sobre embeddings Cohere embed v4 (input_type=classification); "
           "similaridade = produto interno de vetores L2-normalizados; " % K)
    if campo == "REFERENCIA_FABRICANTE":
        obs += ("y_pred = y do vizinho 1 (copia de quase-duplicado), top3 = y dos "
                "vizinhos 1-3, conf = similaridade do vizinho 1; ")
    else:
        obs += ("score de classe = soma das similaridades dos vizinhos da classe; "
                "conf = score_top1/soma dos scores; top3 = 3 classes de maior score; ")
    obs += ("tokens estimados por chars/4 (API de embedding nao devolve contagem); "
            "chamadas/tokens cobrem embeddings de treino+teste do campo")
    if falhas_tr or falhas_te:
        obs += (f"; falhas de embedding apos retries: treino={falhas_tr} (excluidas do "
                f"indice), teste={falhas_te} (abstencao)")
    if n_abst:
        obs += f"; abstencoes={n_abst}"
    salvar_pred(SOLUCAO, campo, out)
    salvar_meta(SOLUCAO, campo,
                segundos=seg,
                chamadas_api=cont.chamadas,
                tokens_entrada=cont.entrada,
                tokens_saida=cont.saida,
                modelo=COHERE_EMBED,
                custo_estimado_usd=round(cont.custo(COHERE_EMBED), 4),
                observacoes=obs)
    log(f"{campo}: pronto em {seg}s | chamadas={cont.chamadas} tokens_est={cont.entrada} "
        f"custo=${cont.custo(COHERE_EMBED):.4f} | abstencoes={n_abst}")
    return {"campo": campo, "segundos": seg, "chamadas": cont.chamadas,
            "tokens": cont.entrada, "custo": cont.custo(COHERE_EMBED), "abst": n_abst}


def valida(threads):
    """Smoke test minusculo em foreground: 2 chamadas de embed, nada e gravado."""
    log("VALIDACAO: amostra minuscula (12 treino + 6 teste de FABRICANTE), sem gravar nada")
    cont = Contador()
    tr = pd.read_csv(caminho_split("FABRICANTE", "treino"), dtype=str).fillna("").head(12)
    te = pd.read_csv(caminho_split("FABRICANTE", "teste"), dtype=str).fillna("").head(6)
    Etr, f1 = embeda(monta_textos(tr, "FABRICANTE"), cont, threads, "val/treino")
    Ete, f2 = embeda(monta_textos(te, "FABRICANTE"), cont, threads, "val/teste")
    log(f"dims: treino={Etr.shape} teste={Ete.shape} falhas={len(f1) + len(f2)}")
    Xtr, ok_tr = normaliza(Etr)
    Xte, ok_te = normaliza(Ete)
    y = tr["y"].to_numpy()
    preds, confs, top3s = prediz_categorico(Xte, ok_te, Xtr[ok_tr], y[ok_tr])
    for cod, yt, p, c, t in zip(te["CODIGO_MATERIAL"], te["y"], preds, confs, top3s):
        log(f"  {cod}: y={yt} pred={p} conf={c} top3={t}")
    pr, cr, t3 = prediz_referencia(Xte, ok_te, Xtr[ok_tr], y[ok_tr])
    log(f"  caminho referencia ok: pred0={pr[0]} conf0={cr[0]} top3={t3[0]}")
    log(f"VALIDACAO ok | chamadas={cont.chamadas} tokens_est={cont.entrada} "
        f"custo=${cont.custo(COHERE_EMBED):.6f}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--valida", action="store_true", help="smoke test sem gravar nada")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--campos", nargs="*", default=CAMPOS)
    a = ap.parse_args()
    if a.valida:
        valida(a.threads)
        return
    t0 = time.time()
    res = []
    for campo in a.campos:
        res.append(roda_campo(campo, a.threads))
    log(f"TOTAL: {time.time() - t0:.0f}s | chamadas={sum(r['chamadas'] for r in res)} | "
        f"custo total=${sum(r['custo'] for r in res):.4f}")


if __name__ == "__main__":
    main()
