"""Extração de classe e atributos por LLM, com cache em disco e validação rígida da saída.

O modelo propõe; o código decide. Cada valor passa pelo canonicalizador e pelo PDM, o trecho
de origem precisa existir no texto, e nada com valor fora da lista entra como válido.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass

from ..config import settings
from ..estruturacao.canonicalizar import canonicaliza_atributo
from ..estruturacao.modelo import Extracao, Valor
from ..normalizacao.texto import normaliza
from ..pdm.modelo import Classe, Pdm
from . import cliente as _cli
from .prompt import PROMPT_VERSAO, esquema_saida, monta_entrada, monta_sistema


@dataclass
class Resposta:
    saida: dict | None
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    cache_leitura: int = 0
    cache_escrita: int = 0
    ms: int = 0
    erro: str | None = None
    do_cache: bool = False

    @property
    def custo(self) -> float:
        return _cli.custo_estimado(self.modelo, self.tokens_entrada, self.tokens_saida, self.cache_leitura, self.cache_escrita)


def chave_cache(modelo: str, ids_classes: list[str], entrada: str) -> str:
    return hashlib.sha256("|".join([PROMPT_VERSAO, modelo, ",".join(sorted(ids_classes)), entrada]).encode()).hexdigest()


def chama(pdm: Pdm, classes: list[Classe], entrada: str, modelo: str | None = None, max_tokens: int = 900) -> Resposta:
    modelo = modelo or settings().llm_modelo_extracao
    ids = [c.id_pdm for c in classes]
    t0 = time.time()
    try:
        r = _cli.cliente().messages.create(
            model=modelo, max_tokens=max_tokens,
            system=[{"type": "text", "text": monta_sistema(pdm, classes), "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": entrada}],
            output_config={"format": {"type": "json_schema", "schema": esquema_saida(ids)}},
        )
        if r.stop_reason == "refusal":
            return Resposta(None, modelo, erro="refusal", ms=int((time.time() - t0) * 1000))
        txt = "".join(b.text for b in r.content if b.type == "text")
        u = r.usage
        return Resposta(json.loads(txt), modelo, u.input_tokens, u.output_tokens,
                        getattr(u, "cache_read_input_tokens", 0) or 0, getattr(u, "cache_creation_input_tokens", 0) or 0,
                        int((time.time() - t0) * 1000))
    except Exception as e:  # noqa: BLE001 - qualquer falha vira resposta vazia, o fluxo segue sem LLM
        return Resposta(None, modelo, erro=f"{type(e).__name__}: {re.sub(r'[0-9]{12}', '<conta>', str(e))[:200]}",
                        ms=int((time.time() - t0) * 1000))


def _colapsa(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", normaliza(s))


def valida(pdm: Pdm, classes: list[Classe], saida: dict | None, texto_entrada: str) -> Extracao:
    """Converte a saída do modelo em Extracao, descartando o que não obedece ao PDM."""
    ex = Extracao(metodo="LLM")
    if not saida:
        return ex
    permitidas = {c.id_pdm: c for c in classes}
    idp = saida.get("classe")
    if idp not in permitidas:
        ex.avisos.append("LLM: sem classe" if idp == "NENHUMA" else f"LLM: classe fora do conjunto ({idp})")
        return ex
    classe = permitidas[idp]
    nome = normaliza(saida.get("nome"))
    if len(classe.nomes) == 1:
        nome = classe.nomes[0]
    else:
        mapa = {normaliza(n): n for n in classe.nomes}
        nome = mapa.get(nome)
        if nome is None and not classe.por_referencia:
            ex.avisos.append("LLM: nome do material invalido para a classe")
            return ex
    ex.id_pdm, ex.nome, ex.confianca_classe = idp, nome, 0.85
    base = _colapsa(texto_entrada)
    for item in saida.get("atributos", []):
        a = classe.atributo(normaliza(item.get("atributo")))
        if a is None:
            continue
        bruto, trecho = (item.get("valor") or "").strip(), (item.get("trecho") or "").strip()
        if not bruto:
            continue
        trecho_ok = bool(trecho) and _colapsa(trecho) in base
        c = canonicaliza_atributo(a, bruto, idp)
        if c.valor is None:
            ex.valores[a.nome] = Valor(None, bruto, "LLM", trecho or None, 0.0, c.candidatos)
            continue
        conf = min(c.confianca, 0.93) if trecho_ok else 0.5
        ex.valores[a.nome] = Valor(c.valor, bruto, "LLM", trecho or None, conf)
    return ex
