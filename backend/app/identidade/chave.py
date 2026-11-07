"""Chave de identidade de um item (regra 10 do PDM).

Duplicidade deixa de ser problema de similaridade de texto e vira igualdade de chave:
 - classes de ESPECIFICACAO: id + nome + todos os atributos obrigatórios aplicáveis;
 - classes de REFERENCIA (filtros, sobressalentes): id + fabricante + referência.
A chave só "fecha" (completa=True) quando todos os componentes existem.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..pdm.modelo import Pdm
from .referencias import fabricante_canonico, referencia_generica, referencia_rolamento


@dataclass(frozen=True)
class Chave:
    texto: str | None
    completa: bool
    faltando: tuple[str, ...] = field(default_factory=tuple)
    componentes: dict = field(default_factory=dict, compare=False)


def _valor_identidade(id_pdm: str, atributo: str, valor: str) -> str:
    if id_pdm == "PDM020" and atributo == "REFERENCIA":
        return referencia_rolamento(valor) or valor
    if atributo.startswith("REFERENCIA") or atributo == "PERFIL":
        return referencia_generica(valor) or valor
    return valor


def chave_identidade(pdm: Pdm, id_pdm: str, nome: str, valores: dict[str, str | None]) -> Chave:
    classe = pdm.classes[id_pdm]
    if classe.por_referencia:
        a_fab = classe.atributo("FABRICANTE")
        fab = fabricante_canonico(valores.get("FABRICANTE"), a_fab.valores if a_fab else ())
        ref = referencia_generica(valores.get("REFERENCIA FABRICANTE"))
        faltando = tuple(n for n, v in (("FABRICANTE", fab), ("REFERENCIA FABRICANTE", ref)) if not v)
        if faltando:
            return Chave(None, False, faltando)
        return Chave(f"{id_pdm}|{fab}|{ref}", True, (), {"FABRICANTE": fab, "REFERENCIA FABRICANTE": ref})

    obrig = pdm.obrigatorios_aplicaveis(id_pdm, nome, valores)
    partes, faltando, comp = [], [], {}
    for a in obrig:
        v = valores.get(a.nome)
        if not v:
            faltando.append(a.nome)
            continue
        v = _valor_identidade(id_pdm, a.nome, v)
        comp[a.nome] = v
        partes.append(f"{a.nome}={v}")
    if faltando:
        return Chave(None, False, tuple(faltando), comp)
    return Chave(f"{id_pdm}|{nome}|" + "|".join(partes), True, (), comp)
