"""Contrato compartilhado do benchmark de preenchimento de campos.

Toda solucao le os splits congelados e grava predicoes e metadados
exatamente neste formato; o benchmark recomputa as metricas somente
a partir dos arquivos de predicao.
"""
from pathlib import Path
import json
import re
import unicodedata

RAIZ = Path(__file__).resolve().parent
DADOS = RAIZ / "dados"
SPLITS = DADOS / "splits"
PRED = RAIZ / "pred"
METRICAS = RAIZ / "metricas"
CACHE = RAIZ / "cache"
SAIDA = RAIZ / "saida"
for _d in (DADOS, SPLITS, PRED, METRICAS, CACHE, SAIDA):
    _d.mkdir(parents=True, exist_ok=True)

SEED = 42
CAMPOS = ["GRUPO_MERCADORIA", "NCM", "FABRICANTE", "REFERENCIA_FABRICANTE"]
CATEGORICOS = ["GRUPO_MERCADORIA", "NCM", "FABRICANTE"]
N_TESTE = {"GRUPO_MERCADORIA": 2000, "NCM": 2000, "FABRICANTE": 2000, "REFERENCIA_FABRICANTE": 1500}

# Colunas de entrada permitidas para prever qualquer campo.
# GRUPO_MERCADORIA entra como atributo, exceto quando e o proprio alvo.
ENTRADAS = ["DESCRICAO_CURTA", "DESCRICAO_LONGA", "CENTRO", "UNIDADE_MEDIDA"]


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_texto(s) -> str:
    s = sem_acento(str(s or "")).upper()
    return re.sub(r"\s+", " ", s).strip()


def norm_ncm(s) -> str:
    d = re.sub(r"\D", "", str(s or ""))
    return d if len(d) == 8 else ""


def norm_ref(s) -> str:
    return re.sub(r"[^A-Z0-9]", "", sem_acento(str(s or "")).upper())


def norm_rotulo(campo: str, valor) -> str:
    if campo == "NCM":
        return norm_ncm(valor)
    if campo == "REFERENCIA_FABRICANTE":
        return norm_ref(valor)
    return norm_texto(valor)


def texto_entrada(row, incluir_grupo=True) -> str:
    """Texto padrao que alimenta os modelos: descricoes + grupo como token."""
    get = row.get if hasattr(row, "get") else lambda k, d="": row[k] if k in row else d
    partes = [norm_texto(get("DESCRICAO_CURTA", "")), norm_texto(get("DESCRICAO_LONGA", ""))]
    if incluir_grupo:
        g = norm_texto(get("GRUPO_MERCADORIA", ""))
        if g:
            partes.append("GRUPO " + g.replace(" ", "_"))
    return " ".join(p for p in partes if p)


def caminho_split(campo: str, parte: str) -> Path:
    return SPLITS / f"{campo}__{parte}.csv"


def salvar_pred(solucao: str, campo: str, df):
    """df precisa ter: CODIGO_MATERIAL, y_true, y_pred, conf, top3.

    Valores ja normalizados com norm_rotulo; top3 = ate 3 valores separados por '|'.
    y_pred vazio = abstencao (a solucao nao cobre o caso).
    """
    cols = ["CODIGO_MATERIAL", "y_true", "y_pred", "conf", "top3"]
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    df[cols].to_csv(PRED / f"{solucao}__{campo}.csv", index=False)


def salvar_meta(solucao: str, campo: str, **kw):
    """Metadados de execucao: segundos, chamadas_api, tokens_entrada, tokens_saida,
    modelo, custo_estimado_usd, observacoes."""
    kw.update({"solucao": solucao, "campo": campo})
    (METRICAS / f"{solucao}__{campo}.json").write_text(
        json.dumps(kw, ensure_ascii=False, indent=1)
    )
