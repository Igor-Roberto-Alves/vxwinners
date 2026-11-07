"""Camada 4 - LLM (Claude no Bedrock): roda so no residuo que o arbitro escalou.

Nunca e chamado na base inteira. Entra quando regra e BERT discordam, quando o
dicionario casou mais de um valor ou quando o sujeito ficou incerto. A saida
passa pelo mesmo validador das outras camadas: valor fora da lista de valores
permitidos do PDM e recusado, mesmo vindo do modelo grande.

Credenciais: .env do projeto (ver claude-bedrock.sh). Sem credencial valida o
pipeline continua rodando - o residuo fica marcado para revisao humana, que e o
comportamento correto, nao um erro.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .pdm import Classe

# IDs sao perfis de inferencia (prefixo us.), nao IDs de foundation model: todos os
# Claude da conta so aceitam INFERENCE_PROFILE, invocar anthropic.* direto da erro.
# Haiku e o modelo de volume do residuo; Sonnet entra no que o Haiku erra.
MODELO_PADRAO = os.environ.get("MODELO_LLM", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
MODELO_DIFICIL = os.environ.get("MODELO_LLM_DIFICIL", "us.anthropic.claude-sonnet-5")
REGIAO_PADRAO = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

# Da geracao Opus 4.7 / Sonnet 5 em diante temperature foi removida do inferenceConfig
# e a Converse devolve ValidationException ("`temperature` is deprecated for this
# model"). Mandar o campo derruba 100% das chamadas, nao uma parte.
_ACEITA_TEMPERATURA = re.compile(
    r"claude-(?:v2|instant|3|3-5|3-7|haiku-4-5|sonnet-4-5|opus-4-5|sonnet-4-6|opus-4-6)", re.I
)

# Erro de configuracao: repetir nao conserta e, no residuo inteiro, repetir 3x com
# backoff custa horas para produzir zero resultado. So throttling e falha de rede
# merecem nova tentativa.
_PERMANENTES = ("ValidationException", "AccessDeniedException", "ResourceNotFoundException",
                "UnrecognizedClientException", "InvalidSignatureException",
                "SerializationException")

SISTEMA = """Voce extrai atributos tecnicos de materiais industriais para um cadastro \
padronizado (PDM). Devolva APENAS o que esta escrito no texto.

Regras obrigatorias:
- Atributo com lista de valores: use EXATAMENTE um dos valores da lista, nunca uma variacao.
- Atributo ausente no texto: devolva null. Nunca deduza, nunca complete com conhecimento proprio.
- Termo do texto que serve a mais de um valor da lista: devolva null. "ZINCADO" com
  ZINCADO AMARELO e ZINCADO BRANCO na lista nao decide entre os dois, e escolher um
  inventa informacao que o texto nao tem - essa decisao e do cadastrista. Devolva o
  valor so quando o texto distingue um unico item da lista.
- Notacao compacta junta atributos: M12X50 = BITOLA M12 + COMPRIMENTO 50MM.
- Passo de rosca ausente implica ROSCA = METRICA GROSSA.
- Varias grandezas de mesma unidade na mesma classe: o texto as lista na ordem dos
  atributos. Se vierem menos numeros que atributos, o primeiro numero e do atributo
  de menor ordem (a medida principal da classe, que o texto nunca omite) e o ultimo
  e do atributo de maior ordem; os atributos do meio ficam null. Em RETENTOR
  "RET 50MM 8MM" e DIAMETRO EIXO 50MM + LARGURA 8MM, com DIAMETRO ALOJAMENTO null.
- Ordem de grandeza do dominio, use como conferencia: DIAMETRO ALOJAMENTO >
  DIAMETRO EIXO > LARGURA e ESPESSURA. Atribuicao que inverta isso esta errada.
- Milimetro: numero + MM com decimal em virgula (16,25MM). Polegada: fracao + POL (1.1/4POL).
- Pressao sempre em BAR (converta de psi dividindo por 14,5038; de MPa multiplicando por 10).
- Texto em maiusculas, sem acento e sem cedilha.
- Para cada atributo preenchido, informe o trecho exato do texto que o originou."""


@dataclass
class RespostaLlm:
    valores: dict[str, str | None]
    evidencias: dict[str, str]
    bruto: str = ""
    tokens_entrada: int = 0
    tokens_saida: int = 0
    do_cache: bool = False
    erro: str = ""
    truncado: bool = False


def _ferramenta(classe: Classe) -> dict:
    """Schema de saida forcado por tool use: o modelo so pode devolver estes campos."""
    props = {}
    for a in sorted(classe.atributos, key=lambda x: x.ordem):
        campo: dict = {"description": f"{a.nome}. {a.formato}"[:300]}
        if a.valores:
            campo["type"] = ["string", "null"]
            campo["enum"] = a.valores + [None]
        else:
            campo["type"] = ["string", "null"]
        props[a.nome] = campo
    return {
        "toolSpec": {
            "name": "registrar_atributos",
            "description": f"Registra os atributos da classe {classe.id_pdm}.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        # additionalProperties False: o modelo nao pode inventar nome
                        # de atributo fora da classe. O validador recusaria depois, mas
                        # ai o custo da chamada ja foi pago.
                        "atributos": {"type": "object", "properties": props,
                                      "additionalProperties": False},
                        "evidencias": {
                            "type": "object",
                            "description": "atributo -> trecho do texto que originou o valor",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    "required": ["atributos"],
                }
            },
        }
    }


def _prompt(classe: Classe, texto: str, foco: list[str], motivos: list[str]) -> str:
    linhas = [f"CLASSE: {classe.rotulo()} ({classe.id_pdm})", "", "ATRIBUTOS:"]
    for a in sorted(classe.atributos, key=lambda x: x.ordem):
        marca = "obrigatorio" if (a.obrigatorio and a.sempre) else "opcional"
        if a.valores:
            regra = "um de: " + " | ".join(a.valores)
        else:
            regra = a.formato or "texto livre"
        linhas.append(f"  {a.nome} ({marca}) {regra}"[:400])
    if foco:
        linhas += ["", "ATENCAO ESPECIAL nestes atributos, onde as camadas automaticas "
                   "nao chegaram a acordo:", "  " + ", ".join(foco)]
    if motivos:
        linhas += ["", "MOTIVO DA ESCALADA: " + "; ".join(motivos)]
    linhas += ["", "TEXTO:", texto]
    return "\n".join(linhas)


class DesempateLlm:
    def __init__(self, modelo: str = MODELO_PADRAO, regiao: str = REGIAO_PADRAO,
                 cache: str | Path = "artefatos/cache_llm", ativo: bool = True,
                 tentativas: int = 3, max_tokens: int = 1500):
        self.modelo = modelo
        self.regiao = regiao
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.tentativas = tentativas
        self.max_tokens = max_tokens
        self.ativo = ativo
        self._cliente = None
        self.erro_cliente = ""
        self._temperatura = bool(_ACEITA_TEMPERATURA.search(modelo))
        self.contador = {"chamadas": 0, "cache": 0, "erros": 0, "truncados": 0,
                         "tokens_entrada": 0, "tokens_saida": 0}

    # ------------------------------------------------------------- cliente

    @property
    def cliente(self):
        if self._cliente is None and self.ativo:
            try:
                import boto3

                self._cliente = boto3.client("bedrock-runtime", region_name=self.regiao)
            except Exception as e:  # credencial ausente, boto3 ausente, regiao invalida
                self.erro_cliente = f"{type(e).__name__}: {e}"
                self.ativo = False
        return self._cliente

    # ------------------------------------------------------------- cache

    def _chave(self, classe: Classe, texto: str, foco: list[str]) -> Path:
        crua = json.dumps([self.modelo, classe.id_pdm, texto, sorted(foco)], ensure_ascii=False)
        return self.cache / (hashlib.sha256(crua.encode()).hexdigest()[:24] + ".json")

    # ------------------------------------------------------------- chamada

    def desempatar(self, classe: Classe, texto: str, foco: list[str],
                   motivos: list[str] | None = None) -> RespostaLlm:
        arq = self._chave(classe, texto, foco)
        if arq.exists():
            d = json.loads(arq.read_text(encoding="utf-8"))
            self.contador["cache"] += 1
            return RespostaLlm(d["valores"], d.get("evidencias", {}), do_cache=True)

        if not self.ativo or self.cliente is None:
            return RespostaLlm({}, {}, erro=self.erro_cliente or "LLM desativado")

        corpo = {
            "modelId": self.modelo,
            "system": [{"text": SISTEMA}],
            "messages": [{"role": "user", "content": [{"text": _prompt(classe, texto, foco, motivos or [])}]}],
            "toolConfig": {
                "tools": [_ferramenta(classe)],
                "toolChoice": {"tool": {"name": "registrar_atributos"}},
            },
            "inferenceConfig": {"maxTokens": self.max_tokens},
        }
        if self._temperatura:
            corpo["inferenceConfig"]["temperature"] = 0

        erro = ""
        for tentativa in range(self.tentativas):
            try:
                r = self.cliente.converse(**corpo)
            except Exception as e:
                nome = type(e).__name__
                erro = f"{nome}: {e}"
                # Modelo novo que ainda nao esta em _ACEITA_TEMPERATURA: tira o campo
                # e tenta de novo em vez de perder o residuo inteiro.
                if "temperature" in str(e) and self._temperatura:
                    self._temperatura = False
                    corpo["inferenceConfig"].pop("temperature", None)
                    continue
                if nome in _PERMANENTES:
                    # Erro de configuracao vale para toda chamada seguinte: desliga a
                    # camada e guarda o motivo onde 04_extrair.py ja imprime, em vez de
                    # repetir 3.569 vezes o mesmo ValidationException em silencio.
                    self.ativo = False
                    self.erro_cliente = erro
                    break
                if tentativa < self.tentativas - 1:
                    time.sleep(2 ** tentativa + random.random())
                continue

            uso = r.get("usage", {})
            entrada_tok = uso.get("inputTokens", 0)
            saida_tok = uso.get("outputTokens", 0)
            self.contador["chamadas"] += 1
            self.contador["tokens_entrada"] += entrada_tok
            self.contador["tokens_saida"] += saida_tok

            valores, evid = {}, {}
            for bloco in r["output"]["message"]["content"]:
                if "toolUse" in bloco:
                    entrada = bloco["toolUse"]["input"]
                    valores = entrada.get("atributos", {}) or {}
                    evid = entrada.get("evidencias", {}) or {}

            # maxTokens cortou a resposta no meio: o toolUse chega vazio ou pela
            # metade. Cachear isso congela o registro errado para sempre.
            truncado = r.get("stopReason") == "max_tokens"
            if truncado:
                self.contador["truncados"] += 1
            if valores and not truncado:
                arq.write_text(json.dumps({"valores": valores, "evidencias": evid},
                                          ensure_ascii=False), encoding="utf-8")
            return RespostaLlm(valores, evid, tokens_entrada=entrada_tok,
                               tokens_saida=saida_tok, truncado=truncado,
                               erro="resposta truncada por maxTokens" if truncado else "")

        self.contador["erros"] += 1
        if not self.erro_cliente:
            self.erro_cliente = erro
        return RespostaLlm({}, {}, erro=erro)

    def resumo(self) -> str:
        c = self.contador
        s = (f"LLM ({self.modelo}): {c['chamadas']} chamadas, {c['cache']} do cache, "
             f"{c['erros']} erros, {c['truncados']} truncados, "
             f"{c['tokens_entrada']} tokens entrada, {c['tokens_saida']} tokens saida")
        if self.erro_cliente:
            s += f"\n  ultimo erro: {self.erro_cliente}"
        return s
