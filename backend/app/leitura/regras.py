"""Leitura de pedidos por regras: e-mail, ficha técnica e catálogo viram o mesmo formato que o
extrator da base já entende (`ATRIBUTO: VALOR` separado por `;`).

Só entra o que o texto diz de forma explícita (valor da lista, rótulo, `M16 x 60`). Medidas soltas
não são atribuídas por posição: viram sugestão, nunca preenchimento.
"""
from __future__ import annotations

import re

from ..classes.resolver import IndiceClasses
from ..estruturacao.modelo import Extracao
from ..estruturacao.regras import extrai_por_regras
from ..normalizacao.texto import normaliza
from ..pdm.modelo import Pdm

_SO_APONTA = re.compile(r"\b(EM ANEXO|SEGUE|ANEXO|CATALOGO ABAIXO|CONFORME CATALOGO|FICHA TECNICA)\b")
_CAMPOS_CADASTRO = {
    "FABRICANTE": "fabricante", "MARCA": "fabricante", "FABR": "fabricante",
    "REFERENCIA": "referencia_fabricante", "PART NUMBER": "referencia_fabricante", "P/N": "referencia_fabricante",
    "REFERENCIA DO FABRICANTE": "referencia_fabricante", "REF": "referencia_fabricante",
}


def prepara_texto(texto: str | None, anexo: str | None) -> str:
    """Junta pedido e anexo, tira marcadores de lista e quebras de linha, e padroniza separadores."""
    partes = []
    for bloco in (texto, anexo):
        if not bloco:
            continue
        n = normaliza(bloco)
        # "Segue ficha técnica em anexo." não traz informação: só o anexo vale
        if bloco is texto and anexo and _SO_APONTA.search(n) and len(n) < 90:
            continue
        partes.append(bloco)
    bruto = "\n".join(partes)
    linhas = [re.sub(r"^\s*[-•*·]\s*", "", ln).strip() for ln in bruto.splitlines()]
    linhas = [ln for ln in linhas if ln]
    return "; ".join(re.sub(r"\s*\|\s*", "; ", ln) for ln in linhas)


def campos_do_cadastro(texto: str) -> dict[str, str]:
    """Fabricante e referência rotulados: ficam nos campos próprios (regra 8 do PDM)."""
    out: dict[str, str] = {}
    for ln in re.split(r"[;\n]", texto):
        if ":" not in ln:
            continue
        rot, _, val = ln.partition(":")
        alvo = _CAMPOS_CADASTRO.get(normaliza(rot))
        if alvo and val.strip() and alvo not in out:
            out[alvo] = val.strip()
    return out


def le_pedido(pdm: Pdm, indice: IndiceClasses, texto: str | None, anexo: str | None = None) -> tuple[Extracao, str, dict[str, str]]:
    """Devolve (extração, texto preparado, campos do cadastro). Valores recebem origem PEDIDO_REGRA."""
    preparado = prepara_texto(texto, anexo)
    ex = extrai_por_regras(pdm, indice, {"descricao_longa": preparado, "grupo": None})
    for v in ex.valores.values():
        if v.origem in ("REGRA_ROTULO", "REGRA_TEXTO", "REGRA_PDM"):
            v.origem = "PEDIDO_REGRA"
    ex.metodo = "PEDIDO_REGRA"
    return ex, preparado, campos_do_cadastro(preparado)
