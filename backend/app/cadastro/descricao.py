"""Descrição no padrão do PDM (regras 1 a 3, 8 e 9):

    SUBSTANTIVO QUALIFICADOR; ATRIBUTO: VALOR; ATRIBUTO: VALOR; ...

Atributos na ordem da aba ATRIBUTOS. A descrição é sempre gerada, nunca digitada: assim
caixa, acento, ordem e abreviação (regras 3 e 4) são corretos por construção.
"""
from __future__ import annotations

from ..pdm.modelo import Pdm

LIMITE_CURTA = 40  # limite de tela do ERP (DESCRICAO_CURTA)


def monta_longa(pdm: Pdm, id_pdm: str, nome: str, valores: dict[str, str | None], *, marca_pendentes: bool = False) -> str:
    partes = [nome]
    for atr, aplica in pdm.aplicaveis(id_pdm, nome, valores):
        if aplica is not True:
            continue
        v = valores.get(atr.nome)
        if v:
            partes.append(f"{atr.nome}: {v}")
        elif marca_pendentes and atr.obrigatorio:
            partes.append(f"{atr.nome}: ?")
    return "; ".join(partes)


def monta_curta(pdm: Pdm, id_pdm: str, nome: str, valores: dict[str, str | None]) -> str:
    """Nome + valores dos atributos obrigatórios, cortada em palavra inteira até 40 caracteres."""
    obrig = pdm.obrigatorios_aplicaveis(id_pdm, nome, valores)
    texto = " ".join([nome] + [valores[a.nome] for a in obrig if valores.get(a.nome)])
    if len(texto) <= LIMITE_CURTA:
        return texto
    corte = texto[:LIMITE_CURTA]
    if texto[LIMITE_CURTA] != " ":
        corte = corte.rsplit(" ", 1)[0] if " " in corte else corte
    return corte.rstrip()
