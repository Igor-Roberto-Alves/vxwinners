"""Leitura de pedido por LLM: complementa as regras, nunca as substitui, e nunca bloqueia o fluxo.

Qualquer falha (credencial, cota, recusa) devolve None e a pessoa segue preenchendo à mão.
"""
from __future__ import annotations

from ..estruturacao.etapa_llm import mescla
from ..estruturacao.modelo import Extracao
from ..llm import extrator
from ..llm.prompt import monta_entrada
from ..pdm.modelo import Pdm


def le_com_llm(pdm: Pdm, texto_preparado: str, ex_regras: Extracao, modelo: str | None = None) -> tuple[Extracao | None, extrator.Resposta]:
    if ex_regras.id_pdm:
        classes = sorted(pdm.classes_do_grupo(pdm.classes[ex_regras.id_pdm].grupo), key=lambda c: c.id_pdm)
    else:
        classes = sorted(pdm.classes.values(), key=lambda c: c.id_pdm)  # sem pista: todas as classes
    entrada = monta_entrada({"TEXTO DO PEDIDO": texto_preparado})
    r = extrator.chama(pdm, classes, entrada, modelo)
    if not r.saida:
        return None, r
    ex_llm = extrator.valida(pdm, classes, r.saida, entrada)
    final = mescla(ex_regras, ex_llm)
    for v in final.valores.values():
        if v.origem == "LLM":
            v.origem = "PEDIDO_LLM"
    final.metodo = "PEDIDO_REGRA+LLM"
    return final, r
