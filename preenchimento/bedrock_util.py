"""Chamadas Bedrock com retry/backoff e contagem de tokens/custo."""
import json
import random
import re
import threading
import time

import boto3
from botocore.config import Config

REGIAO = "us-east-1"
HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET = "us.anthropic.claude-sonnet-5"
OPUS = "us.anthropic.claude-opus-5"
FABLE = "us.anthropic.claude-fable-5"
COHERE_EMBED = "us.cohere.embed-v4:0"
TITAN_EMBED = "amazon.titan-embed-text-v2:0"

# USD por 1M tokens (entrada, saida). Tabela Anthropic 1P; Bedrock usa precos
# de tabela equivalentes para esses modelos. Embeddings: preco por 1M tokens de entrada.
PRECOS = {
    HAIKU: (1.00, 5.00),
    SONNET: (2.00, 10.00),
    OPUS: (5.00, 25.00),
    FABLE: (10.00, 50.00),
    COHERE_EMBED: (0.12, 0.0),
    TITAN_EMBED: (0.02, 0.0),
}

_rt = boto3.client(
    "bedrock-runtime",
    region_name=REGIAO,
    config=Config(retries={"max_attempts": 0}, read_timeout=600, connect_timeout=10,
                  max_pool_connections=64),
)

RETRIAVEIS = ("ThrottlingException", "ServiceUnavailableException", "ModelTimeoutException",
              "ModelNotReadyException", "InternalServerException", "ServiceQuotaExceededException",
              "EventStreamError", "ReadTimeoutError", "ConnectionError")


class Contador:
    """Acumulador thread-safe de tokens e chamadas."""

    def __init__(self):
        self.lock = threading.Lock()
        self.entrada = 0
        self.saida = 0
        self.chamadas = 0

    def soma(self, e, s):
        with self.lock:
            self.entrada += int(e)
            self.saida += int(s)
            self.chamadas += 1

    def custo(self, model_id):
        pe, ps = PRECOS.get(model_id, (0.0, 0.0))
        return self.entrada / 1e6 * pe + self.saida / 1e6 * ps


def _retriavel(e):
    nome = type(e).__name__
    cod = ""
    resp = getattr(e, "response", None)
    if isinstance(resp, dict):
        cod = resp.get("Error", {}).get("Code", "")
    return any(r in (nome, cod) for r in RETRIAVEIS)


def converse(model_id, texto_usuario, sistema=None, max_tokens=2000, contador=None,
             max_tentativas=10):
    """Uma chamada de chat; devolve o texto da resposta. Retry exponencial em throttling."""
    req = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": texto_usuario}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    if sistema:
        req["system"] = [{"text": sistema}]
    for tentativa in range(max_tentativas):
        try:
            r = _rt.converse(**req)
            u = r["usage"]
            if contador:
                contador.soma(u["inputTokens"], u["outputTokens"])
            textos = [b["text"] for b in r["output"]["message"]["content"] if "text" in b]
            return "\n".join(textos)
        except Exception as e:
            if _retriavel(e) and tentativa < max_tentativas - 1:
                time.sleep(min(60, (2 ** tentativa) * 0.5 + random.random()))
                continue
            raise
    raise RuntimeError(f"esgotou tentativas em {model_id}")


def extrai_json(texto):
    """Extrai o primeiro objeto/array JSON de uma resposta de modelo."""
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?\s*|\s*```$", "", texto, flags=re.S).strip()
    inicios = [i for i in (texto.find("{"), texto.find("[")) if i >= 0]
    if not inicios:
        raise ValueError("sem JSON na resposta")
    return json.JSONDecoder().raw_decode(texto[min(inicios):])[0]


def embed_cohere(textos, contador=None, model_id=COHERE_EMBED,
                 input_type="classification", max_tentativas=10):
    """Embeda ate 96 textos por chamada; devolve lista de vetores float.

    Tokens de entrada sao estimados por len(texto)/4 (a API de embedding
    nao devolve contagem), marcado como estimativa no custo.
    """
    corpo = {"texts": [t[:2000] for t in textos], "input_type": input_type,
             "embedding_types": ["float"]}
    for tentativa in range(max_tentativas):
        try:
            r = _rt.invoke_model(modelId=model_id, body=json.dumps(corpo))
            out = json.loads(r["body"].read())
            emb = out.get("embeddings")
            if isinstance(emb, dict):
                emb = emb.get("float") or next(iter(emb.values()))
            if contador:
                contador.soma(sum(max(1, len(t) // 4) for t in textos), 0)
            return emb
        except Exception as e:
            if _retriavel(e) and tentativa < max_tentativas - 1:
                time.sleep(min(60, (2 ** tentativa) * 0.5 + random.random()))
                continue
            raise
    raise RuntimeError("esgotou tentativas no embed")
