"""API de sugestao de cadastro de materiais (FastAPI, porta 8700).

Serve os modelos treinados por treina.py (tfidf+LR para grupo/ncm/fabricante,
NN de similares) + lexico de fabricantes + extracao de referencia do 02_regras.

Contrato:
  GET  /saude     -> status e modelos carregados
  POST /sugerir   -> grupo, ncm, fabricante, referencia e similares numa chamada
  POST /similares -> somente a lista de similares
"""
import importlib
import json
import os
import re
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from scipy import sparse

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
MODELOS = RAIZ / "modelos"
PREENCH = REPO / "preenchimento"
sys.path.insert(0, str(PREENCH))
from contrato import norm_ref, norm_texto  # noqa: E402

NOMES_MODELOS = ["grupo", "ncm", "fabricante", "similares"]
CONF_REFERENCIA = {"marcador": 0.85, "perto_fab": 0.6, "mais_longo": 0.45}
CORTE_SIMILARIDADE = 0.15

A = {}  # artefatos carregados no startup


def carregar_artefatos():
    for nome in NOMES_MODELOS:
        A[nome] = joblib.load(MODELOS / f"{nome}.joblib")
    freq = json.loads((MODELOS / "lexico_fabricantes.json").read_text())["freq"]
    # mais longo primeiro; desempate por frequencia no treino
    nomes = sorted(freq, key=lambda n: (-len(n), -freq[n]))
    A["lexico"] = [(n, re.compile(r"(?<![A-Z0-9])" + re.escape(n) + r"(?![A-Z0-9])"))
                   for n in nomes]
    A["fabset"] = {tok for n in freq for tok in re.findall(r"[A-Z0-9]+", n)}
    A["meta"] = pd.read_csv(MODELOS / "similares_meta.csv", dtype=str, keep_default_na=False)
    # 02_regras abre o proprio .log por caminho relativo: importar com cwd certo
    cwd = os.getcwd()
    try:
        os.chdir(PREENCH)
        A["regras"] = importlib.import_module("02_regras")
    finally:
        os.chdir(cwd)


def top3_modelo(nome, texto):
    m = A[nome]
    X = sparse.hstack([m["vw"].transform([texto]), m["vc"].transform([texto])]).tocsr()
    proba = m["lr"].predict_proba(X)[0]
    ordem = proba.argsort()[::-1][:3]
    return [{"valor": str(m["lr"].classes_[i]), "conf": round(float(proba[i]), 4)}
            for i in ordem]


def sugerir_fabricante(texto, texto_g):
    casados = [nome for nome, rx in A["lexico"] if rx.search(texto)]
    if casados:
        return {"origem": "lexico",
                "sugestoes": [{"valor": n, "conf": 0.999} for n in casados[:3]]}
    return {"origem": "modelo", "sugestoes": top3_modelo("fabricante", texto_g)}


def extrair_ref(descricao):
    ordem, origem = A["regras"].extrair_referencia(descricao, "", A["fabset"])
    if not ordem:
        return {"valor": None, "conf": None, "origem": "extracao"}
    valor, sep00 = ordem[0]
    if sep00 and len(valor) > 6:  # convencao do treino: sufixo '-00' sai do rotulo
        valor = valor[:-2]
    return {"valor": norm_ref(valor), "conf": CONF_REFERENCIA.get(origem, 0.45),
            "origem": "extracao"}


def buscar_similares(texto):
    m = A["similares"]
    X = m["vw"].transform([texto])
    if X.nnz == 0:
        return []
    dist, idx = m["nn"].kneighbors(X, n_neighbors=5)
    saida = []
    for d, i in zip(dist[0], idx[0]):
        sim = round(float(1.0 - d), 4)
        if sim < CORTE_SIMILARIDADE:
            continue
        r = A["meta"].iloc[int(i)]
        saida.append({"codigo": r["CODIGO_MATERIAL"], "descricao": r["DESCRICAO_LONGA"],
                      "grupo": r["GRUPO_MERCADORIA"], "status": r["STATUS"],
                      "similaridade": sim})
    return saida


def montar_sugestao(descricao, grupo_informado):
    texto = norm_texto(descricao)
    sug_grupo = top3_modelo("grupo", texto)
    grupo = norm_texto(grupo_informado or "") or sug_grupo[0]["valor"]
    texto_g = texto + " GRUPO " + grupo.replace(" ", "_")
    sug_ncm = [{"valor": s["valor"],
                "valor_formatado": f'{s["valor"][:4]}.{s["valor"][4:6]}.{s["valor"][6:]}',
                "conf": s["conf"]} for s in top3_modelo("ncm", texto_g)]
    return {"grupo": {"sugestoes": sug_grupo},
            "ncm": {"sugestoes": sug_ncm},
            "fabricante": sugerir_fabricante(texto, texto_g),
            "referencia": extrair_ref(descricao),
            "similares": buscar_similares(texto)}


@asynccontextmanager
async def lifespan(app):
    carregar_artefatos()
    montar_sugestao("PARAFUSO SEXTAVADO M10X50 ACO INOX", None)  # aquecimento
    yield


app = FastAPI(title="Sugestao de cadastro de materiais", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def erro_interno(request, exc):
    return JSONResponse(status_code=500, content={"erro": f"{type(exc).__name__}: {exc}"})


class ReqSimilares(BaseModel):
    descricao: str

    @field_validator("descricao")
    @classmethod
    def descricao_nao_vazia(cls, v):
        if not str(v or "").strip():
            raise ValueError("descricao vazia: informe a descricao do material")
        return v


class ReqSugerir(ReqSimilares):
    grupo: str | None = None


@app.get("/saude")
def saude():
    return {"ok": True, "modelos": NOMES_MODELOS, "linhas_base": len(A["meta"])}


@app.post("/sugerir")
def sugerir(req: ReqSugerir):
    t0 = time.monotonic()
    resp = montar_sugestao(req.descricao, req.grupo)
    resp["latencia_ms"] = int(round((time.monotonic() - t0) * 1000))
    return resp


@app.post("/similares")
def similares(req: ReqSimilares):
    return {"similares": buscar_similares(norm_texto(req.descricao))}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8700)
