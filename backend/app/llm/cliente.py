"""Acesso ao Claude, isolado em um módulo: trocar de provedor não afeta o resto.

`bedrock` usa o AWS Bedrock (perfis de inferência). `aws_platform` usa o Claude Platform on AWS,
que exige AWS_REGION e ANTHROPIC_AWS_WORKSPACE_ID. As credenciais AWS vêm do ambiente; em
desenvolvimento, do .env fora do repositório. Nenhum segredo é registrado em log.
"""
from __future__ import annotations

import os
from functools import lru_cache

from ..config import ARQUIVOS_ENV, settings

# Estimativa em US$ por milhão de tokens (entrada, saída, leitura de cache, escrita de cache).
# Só serve para dimensionar custo: a cobrança real vem da conta AWS.
PRECOS = {
    "haiku-4-5": (1.0, 5.0, 0.10, 1.25),
    "sonnet-4-6": (3.0, 15.0, 0.30, 3.75),
    "sonnet-5": (2.0, 10.0, 0.20, 2.5),
    "opus-5": (5.0, 25.0, 0.50, 6.25),
}


def carrega_credenciais_dev() -> None:
    """Lê AWS_* do .env (sem sobrescrever o ambiente e sem imprimir nada)."""
    from dotenv import dotenv_values

    for caminho in ARQUIVOS_ENV:
        if caminho.exists():
            for k, v in dotenv_values(caminho).items():
                if k.startswith(("AWS_", "ANTHROPIC_AWS_")) and v:
                    os.environ.setdefault(k, v)


@lru_cache
def cliente():
    import anthropic

    carrega_credenciais_dev()
    s = settings()
    if s.llm_provider == "aws_platform":
        return anthropic.AnthropicAWS(aws_region=s.regiao, workspace_id=s.anthropic_aws_workspace_id, max_retries=4,
                                      timeout=s.llm_timeout_s)
    return anthropic.AnthropicBedrock(aws_region=s.regiao, max_retries=4, timeout=s.llm_timeout_s)


def custo_estimado(modelo: str, entrada: int, saida: int, cache_leitura: int = 0, cache_escrita: int = 0) -> float:
    chave = next((k for k in PRECOS if k in modelo), "haiku-4-5")
    pin, pout, pcr, pcw = PRECOS[chave]
    return (entrada * pin + saida * pout + cache_leitura * pcr + cache_escrita * pcw) / 1_000_000
