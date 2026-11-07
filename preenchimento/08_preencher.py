"""Preenche os campos faltantes reais da base com os vencedores do benchmark.

- NCM (1.173): tfidf_lr treinado em todos os rotulados (91,1% top-1 / 98,9% top-3 no teste)
- FABRICANTE (15.674): cascata regras (precisao 99,9%) -> LLM few-shot Sonnet no resto (84,3% no teste)
- REFERENCIA_FABRICANTE (18.488): extracao por regras (88,3% nos cobertos); sem candidato = PENDENTE
- GRUPO_MERCADORIA (0 faltantes): bonus — lista de rotulos suspeitos (modelo discorda com conf alta)

Saida em saida/preenchido_{campo}.csv e saida/grupo_suspeitos.csv, com metodo, conf e top3.
"""
import importlib
import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contrato import DADOS, SAIDA, norm_rotulo, norm_texto, texto_entrada
from bedrock_util import SONNET, Contador, converse, extrai_json

regras = importlib.import_module("02_regras")

t0 = time.monotonic()
base = pd.read_csv(DADOS / "base.csv", dtype=str).fillna("")
for campo in ["NCM", "FABRICANTE", "REFERENCIA_FABRICANTE", "GRUPO_MERCADORIA"]:
    base[f"_{campo}"] = base[campo].map(lambda v, c=campo: norm_rotulo(c, v))
base["_texto"] = base.apply(lambda r: texto_entrada(r, incluir_grupo=True), axis=1)
resumo = {}


def vetores(treino_txt, alvo_txt):
    vw = TfidfVectorizer(ngram_range=(1, 2), min_df=2)
    vc = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2)
    Xt = sparse.hstack([vw.fit_transform(treino_txt), vc.fit_transform(treino_txt)]).tocsr()
    Xa = sparse.hstack([vw.transform(alvo_txt), vc.transform(alvo_txt)]).tocsr()
    return Xt, Xa


# ---------------------------------------------------------------- NCM: tfidf_lr
if (SAIDA / "preenchido_NCM.csv").exists():
    sai = pd.read_csv(SAIDA / "preenchido_NCM.csv", dtype=str)
    resumo["NCM"] = {"faltantes": len(sai), "preenchidos": len(sai),
                     "conf_media": float(pd.to_numeric(sai["conf"]).mean())}
    print("NCM: ja preenchido, pulando")
else:
    rot = base[base["_NCM"] != ""]
    falt = base[base["_NCM"] == ""]
    print(f"NCM: treinando em {len(rot)} rotulados para preencher {len(falt)}...")
    Xt, Xa = vetores(rot["_texto"], falt["_texto"])
    lr = LogisticRegression(max_iter=3000)
    lr.fit(Xt, rot["_NCM"])
    proba = lr.predict_proba(Xa)
    ordem = np.argsort(-proba, axis=1)[:, :3]
    sai = pd.DataFrame({
        "CODIGO_MATERIAL": falt["CODIGO_MATERIAL"].values,
        "DESCRICAO_LONGA": falt["DESCRICAO_LONGA"].values,
        "y_pred": lr.classes_[ordem[:, 0]],
        "conf": np.round(proba[np.arange(len(falt)), ordem[:, 0]], 4),
        "top3": ["|".join(lr.classes_[i] for i in linha) for linha in ordem],
        "metodo": "tfidf_lr",
    })
    sai.to_csv(SAIDA / "preenchido_NCM.csv", index=False)
    resumo["NCM"] = {"faltantes": len(falt), "preenchidos": len(sai),
                     "conf_media": float(sai["conf"].mean())}
    print(f"NCM ok ({time.monotonic()-t0:.0f}s)")

# ------------------------------------------------- FABRICANTE: regras -> Sonnet
rot = base[base["_FABRICANTE"] != ""]
falt = base[base["_FABRICANTE"] == ""].copy()
nomes = sorted(rot["_FABRICANTE"].unique(), key=len, reverse=True)
freq = rot["_FABRICANTE"].value_counts()
print(f"FABRICANTE: lexico de {len(nomes)} nomes; {len(falt)} faltantes...")

padroes = {n: re.compile(r"(?<![A-Z0-9])" + re.escape(n) + r"(?![A-Z0-9])") for n in nomes}


def casa_lexico(txt):
    achados = [n for n in nomes if padroes[n].search(txt)]
    achados.sort(key=lambda n: (-len(n), -freq.get(n, 0)))
    return achados


falt["casados"] = falt["_texto"].map(casa_lexico)
falt["txt"] = falt["_texto"]
cobertos = falt[falt["casados"].map(len) > 0]
restantes = falt[falt["casados"].map(len) == 0]
print(f"FABRICANTE: regras cobre {len(cobertos)}; LLM Sonnet para {len(restantes)}")

linhas_fab = [{
    "CODIGO_MATERIAL": r.CODIGO_MATERIAL, "DESCRICAO_LONGA": r.DESCRICAO_LONGA,
    "y_pred": r.casados[0], "conf": 0.999, "top3": "|".join(r.casados[:3]),
    "metodo": "regras_lexico",
} for r in cobertos.itertuples()]

# few-shot: vizinhos TF-IDF dos rotulados
vw = TfidfVectorizer(ngram_range=(1, 2), min_df=2)
Xr = vw.fit_transform(rot["_texto"])
nn = NearestNeighbors(n_neighbors=3, metric="cosine").fit(Xr)
viz = nn.kneighbors(vw.transform(restantes["_texto"]), return_distance=False)
rot_txt, rot_y = rot["_texto"].tolist(), rot["_FABRICANTE"].tolist()

SIST = ("Voce preenche o campo FABRICANTE de registros de materiais industriais de mineracao. "
        "Responda SOMENTE com os fabricantes desta lista (escolha o mais provavel pelo tipo de item "
        "quando a marca nao estiver explicita no texto):\n" + ", ".join(sorted(nomes)) +
        "\nSaida: JSON array COMPACTO em UMA linha, sem espacos nem quebras, no formato "
        "[{\"id\":N,\"top3\":[{\"v\":\"NOME\",\"p\":0.0}]}] e absolutamente nada fora do JSON.")

cont = Contador()
resultados_llm = {}
CKPT = SAIDA / "fab_llm_ckpt.jsonl"
ck_lock = threading.Lock()
if CKPT.exists():
    for _ln in CKPT.read_text().splitlines():
        try:
            _d = json.loads(_ln)
            resultados_llm[_d["c"]] = (_d["t3"], _d["p"])
        except Exception:
            pass
    print(f"FABRICANTE: checkpoint com {len(resultados_llm)} itens ja resolvidos")


def chama_lote(lote):
    itens = []
    for pos, (i, r) in enumerate(lote):
        exemplos = "; ".join(f"[{rot_txt[j][:120]} -> {rot_y[j]}]" for j in viz[i][:3])
        itens.append(f'id {pos}: TEXTO: {r.txt[:400]}\n  EXEMPLOS PARECIDOS: {exemplos}')
    dados = None
    for mt in (8000, 12000):
        try:
            resp = converse(SONNET, "Itens:\n" + "\n".join(itens), sistema=SIST,
                            max_tokens=mt, contador=cont)
            dados = extrai_json(resp)
            break
        except Exception as e:
            erro = f"{type(e).__name__} {str(e)[:80]}"
    if dados is None:
        print("lote falhou apos retry:", erro)
        return
    try:
        if isinstance(dados, dict):  # formatos {"itens":[...]} ou {"0": {...}}
            if isinstance(dados.get("itens"), list):
                dados = dados["itens"]
            else:
                dados = [{"id": k, **(v if isinstance(v, dict) else {"top3": v})}
                         for k, v in dados.items()]
        if not isinstance(dados, list):
            print("lote em formato inesperado:", type(dados).__name__)
            return
        for item in dados:
            if not isinstance(item, dict):
                continue
            try:
                pos = int(item.get("id", -1))
            except (TypeError, ValueError):
                continue
            if 0 <= pos < len(lote):
                cands = item.get("top3") or []
                if isinstance(cands, dict):
                    cands = [cands]
                t3 = [norm_rotulo("FABRICANTE", c.get("v", ""))
                      for c in cands if isinstance(c, dict)]
                t3 = [v for v in t3 if v]
                conf = cands[0].get("p", "") if cands and isinstance(cands[0], dict) else ""
                if t3:
                    cod = lote[pos][1].CODIGO_MATERIAL
                    resultados_llm[cod] = (t3, conf)
                    with ck_lock, open(CKPT, "a") as fh:
                        fh.write(json.dumps({"c": cod, "t3": t3, "p": conf}) + "\n")
    except Exception as e:  # nenhum lote pode derrubar a execucao inteira
        print("lote descartado:", type(e).__name__, str(e)[:80])


pares = [(i, r) for i, r in enumerate(restantes.itertuples())
         if r.CODIGO_MATERIAL not in resultados_llm]
lotes = [pares[i:i + 10] for i in range(0, len(pares), 10)]
print(f"FABRICANTE: {len(lotes)} chamadas Sonnet...")
with ThreadPoolExecutor(max_workers=8) as ex:
    for k, _ in enumerate(ex.map(chama_lote, lotes)):
        if (k + 1) % 50 == 0:
            print(f"  {k+1}/{len(lotes)} lotes")

for r in restantes.itertuples():
    t3, conf = resultados_llm.get(r.CODIGO_MATERIAL, ([], ""))
    linhas_fab.append({
        "CODIGO_MATERIAL": r.CODIGO_MATERIAL, "DESCRICAO_LONGA": r.DESCRICAO_LONGA,
        "y_pred": t3[0] if t3 else "PENDENTE", "conf": conf if t3 else "",
        "top3": "|".join(t3[:3]), "metodo": "llm_fewshot_sonnet" if t3 else "pendente",
    })
pd.DataFrame(linhas_fab).to_csv(SAIDA / "preenchido_FABRICANTE.csv", index=False)
resumo["FABRICANTE"] = {
    "faltantes": len(falt), "via_regras": len(cobertos), "via_llm": len(resultados_llm),
    "pendentes": len(restantes) - len(resultados_llm),
    "tokens_entrada": cont.entrada, "tokens_saida": cont.saida,
    "custo_usd": round(cont.custo(SONNET), 2),
}
print(f"FABRICANTE ok ({time.monotonic()-t0:.0f}s) custo LLM=${cont.custo(SONNET):.2f}")

# ------------------------------------- REFERENCIA_FABRICANTE: extracao por regras
# extrair_referencia devolve (lista_ranqueada [(candidato, flag_sep00)...], origem);
# consumo identico ao roda_referencia do benchmark (02_regras.py)
falt = base[base["_REFERENCIA_FABRICANTE"] == ""]
fabset = set()
for v in base.loc[base["_FABRICANTE"] != "", "_FABRICANTE"]:
    fabset.update(re.findall(r"[A-Z0-9]+", v))
CONF_ORIGEM = {"marcador": 0.85, "perto_fab": 0.6, "mais_longo": 0.45}
print(f"REFERENCIA: extraindo de {len(falt)} faltantes...")
linhas_ref = []
for r in falt.itertuples():
    ordem, origem = regras.extrair_referencia(r.DESCRICAO_LONGA, r.DESCRICAO_CURTA, fabset)
    if not ordem:
        linhas_ref.append({
            "CODIGO_MATERIAL": r.CODIGO_MATERIAL, "DESCRICAO_LONGA": r.DESCRICAO_LONGA,
            "y_pred": "PENDENTE", "conf": "", "top3": "", "metodo": "pendente",
        })
        continue
    x, sep00 = ordem[0]
    bruto = x[:-2] if (sep00 and len(x) > 6) else x
    val = norm_rotulo("REFERENCIA_FABRICANTE", bruto)
    outros = [norm_rotulo("REFERENCIA_FABRICANTE", c) for c, _ in ordem[1:3]]
    top3 = "|".join(dict.fromkeys([v for v in [val] + outros if v]))
    linhas_ref.append({
        "CODIGO_MATERIAL": r.CODIGO_MATERIAL, "DESCRICAO_LONGA": r.DESCRICAO_LONGA,
        "y_pred": val, "conf": CONF_ORIGEM.get(origem, 0.45), "top3": top3,
        "metodo": f"regras_extracao_{origem}",
    })
df_ref = pd.DataFrame(linhas_ref)
df_ref.to_csv(SAIDA / "preenchido_REFERENCIA_FABRICANTE.csv", index=False)
resumo["REFERENCIA_FABRICANTE"] = {
    "faltantes": len(falt),
    "extraidas": int((df_ref["metodo"] != "pendente").sum()),
    "pendentes": int((df_ref["metodo"] == "pendente").sum()),
}
print(f"REFERENCIA ok ({time.monotonic()-t0:.0f}s)")

# ---------------------------------- GRUPO: suspeitos (modelo x rotulo da base)
print("GRUPO: treinando na base inteira para apontar rotulos suspeitos...")
txt_sem_grupo = base.apply(lambda r: texto_entrada(r, incluir_grupo=False), axis=1)
Xt, Xa = vetores(txt_sem_grupo, txt_sem_grupo)
lr = LogisticRegression(max_iter=3000, n_jobs=-1)
lr.fit(Xt, base["_GRUPO_MERCADORIA"])
proba = lr.predict_proba(Xa)
top = np.argmax(proba, axis=1)
pred = lr.classes_[top]
conf = proba[np.arange(len(base)), top]
susp = base.loc[(pred != base["_GRUPO_MERCADORIA"].values) & (conf >= 0.90),
                ["CODIGO_MATERIAL", "DESCRICAO_LONGA", "GRUPO_MERCADORIA"]].copy()
susp["grupo_sugerido"] = pred[(pred != base["_GRUPO_MERCADORIA"].values) & (conf >= 0.90)]
susp["conf"] = np.round(conf[(pred != base["_GRUPO_MERCADORIA"].values) & (conf >= 0.90)], 4)
susp.to_csv(SAIDA / "grupo_suspeitos.csv", index=False)
resumo["GRUPO_MERCADORIA"] = {"suspeitos_conf>=0.90": len(susp)}

resumo["segundos_total"] = round(time.monotonic() - t0, 1)
(SAIDA / "resumo_preenchimento.json").write_text(json.dumps(resumo, indent=1, ensure_ascii=False))
print(json.dumps(resumo, indent=1, ensure_ascii=False))
