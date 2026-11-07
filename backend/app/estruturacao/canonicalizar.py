"""Um único ponto de entrada para transformar o texto de um atributo no valor canônico do PDM.

Usado pela API (digitação), pelo extrator por regras, pela leitura de pedidos e para
conferir o que o LLM devolve: nenhum valor entra sem passar por aqui.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..identidade.referencias import fabricante_canonico, referencia_generica
from ..normalizacao import formatos, grandezas
from ..normalizacao.vocabulario import casa_lista
from ..pdm.modelo import Atributo, Pdm


@dataclass(frozen=True)
class Canonico:
    valor: str | None
    confianca: float = 0.0
    motivo: str = ""
    candidatos: tuple[str, ...] = field(default_factory=tuple)
    fora_do_pdm: bool = False  # texto reconhecido como tentativa de valor, mas inválido para o atributo


def canonicaliza_atributo(a: Atributo, texto: str | None, id_pdm: str | None = None) -> Canonico:
    if texto is None or not str(texto).strip():
        return Canonico(None, 0.0, "vazio")
    texto = str(texto)
    if a.tipo == "LISTA":
        t = texto
        if a.nome == "FABRICANTE":
            t = fabricante_canonico(texto, a.valores) or texto
        # bitola de rosca vinda com ruído: `M-8`, `M 12`, `M12X50`
        if any(re.match(r"^M\d", v) for v in a.valores):
            b = grandezas.rosca_composta(texto).get("BITOLA")
            if b and b.valor:
                t = b.valor
        r = casa_lista(a.valores, t)
        if r.valor:
            return Canonico(r.valor, r.confianca, r.motivo)
        return Canonico(None, 0.0, r.motivo, r.candidatos, fora_do_pdm=r.motivo != "vazio")
    if id_pdm == "PDM020" and a.nome == "REFERENCIA":
        from ..identidade.referencias import referencia_rolamento

        ref = referencia_rolamento(texto)
        if ref and re.match(r"^\d{4,5}", ref):
            return Canonico(ref, 0.95, "referencia na notacao do PDM")
    n = formatos.normaliza_valor(a.tipo, texto, atributo=a.nome)
    if n.valor and formatos.valida(a.tipo, n.valor):
        return Canonico(n.valor, n.confianca, n.motivo)
    return Canonico(None, 0.0, n.motivo or "formato invalido", (), fora_do_pdm=True)


def canonicaliza(pdm: Pdm, id_pdm: str, atributo: str, texto: str | None) -> Canonico:
    a = pdm.classes[id_pdm].atributo(atributo)
    if a is None:
        return Canonico(None, 0.0, "atributo nao existe na classe")
    return canonicaliza_atributo(a, texto, id_pdm)


def valor_valido(pdm: Pdm, id_pdm: str, atributo: str, valor: str) -> bool:
    """O valor (já escrito) obedece ao PDM? Lista fechada confere por igualdade; formato, por regex."""
    a = pdm.classes[id_pdm].atributo(atributo)
    if a is None:
        return False
    if a.tipo == "LISTA":
        return valor in a.valores
    return formatos.valida(a.tipo, valor)


def referencia_para_chave(texto: str | None) -> str | None:
    return referencia_generica(texto)
