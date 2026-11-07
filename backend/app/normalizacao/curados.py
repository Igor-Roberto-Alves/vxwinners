"""Conhecimento de domínio compartilhado com o pipeline de saneamento (`src/saneamento`).

O dicionário de sinônimos e a limpeza de referência existem em um lugar só: o que a equipe curar lá
vale aqui. Sem isso, os dois pipelines divergem em silêncio (foi o que a comparação entre eles mostrou).
"""
from __future__ import annotations

import sys

from ..config import RAIZ_REPO

_SRC = str(RAIZ_REPO / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from saneamento.sinonimos import SINONIMO_SUJEITO, SINONIMOS  # noqa: E402
from saneamento.texto import referencia_canonica, referencia_limpa  # noqa: E402

__all__ = ["SINONIMOS", "SINONIMO_SUJEITO", "referencia_canonica", "referencia_limpa"]
