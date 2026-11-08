"""Ponte com o serviço de sugestão do time (`servico/api.py`, treinado por `servico/treina.py`).

Modelos tf-idf + regressão logística para grupo, NCM e fabricante, extração de referência e vizinhos
de texto na base inteira. O benchmark está em `preenchimento/benchmark.csv`: NCM 91% no 1º lugar e 99%
entre os 3 primeiros; fabricante 82% quando o texto não traz o nome.

O carregamento é opcional e nunca derruba o cadastro: sem modelos treinados, ou sem as dependências,
as sugestões somem e o resto segue. São sempre SUGESTÕES: quem decide é a pessoa, e a regra do PDM
continua sendo a referência do NCM quando ela existe.
"""
from __future__ import annotations

import importlib.util
import threading

from ..config import RAIZ_REPO

_ARQ = RAIZ_REPO / "servico" / "api.py"
_MODELOS = RAIZ_REPO / "servico" / "modelos"
_est: dict = {"mod": None, "erro": None}
_trava = threading.Lock()


def treinados() -> bool:
    return (_MODELOS / "similares.joblib").exists()


def carrega() -> bool:
    """Carrega uma vez. Devolve True se o serviço está pronto."""
    with _trava:
        if _est["mod"] is not None:
            return True
        if _est["erro"] is not None:
            return False
        if not treinados():
            _est["erro"] = "modelos nao treinados: rode `python servico/treina.py`"
            return False
        try:
            spec = importlib.util.spec_from_file_location("servico_api", _ARQ)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            mod.carregar_artefatos()
            _est["mod"] = mod
            return True
        except Exception as e:  # noqa: BLE001 - sugestão é opcional: registra e segue sem ela
            _est["erro"] = f"{type(e).__name__}: {e}"
            return False


def estado() -> dict:
    return {"pronto": _est["mod"] is not None, "treinados": treinados(), "erro": _est["erro"]}


def pronto() -> bool:
    return _est["mod"] is not None


def sugerir(descricao: str, grupo: str | None = None) -> dict | None:
    if not pronto() or not (descricao or "").strip():
        return None
    try:
        return _est["mod"].montar_sugestao(descricao, grupo)
    except Exception:  # noqa: BLE001
        return None


def similares(descricao: str) -> list[dict]:
    if not pronto() or not (descricao or "").strip():
        return []
    try:
        mod = _est["mod"]
        return mod.buscar_similares(mod.norm_texto(descricao))
    except Exception:  # noqa: BLE001
        return []


def linhas_base() -> int:
    return len(_est["mod"].A["meta"]) if pronto() else 0
