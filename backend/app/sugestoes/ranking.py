"""Opções de valor para um atributo, a partir do que já está cadastrado.

Regras (docs/06-plano-modo-cadastro.md, seção 6.3): nada vem preenchido por frequência; a pessoa vê
até 3 opções com a contagem. A frequência é calculada dentro do NOME do material (não da classe) e,
quando há atributos já preenchidos, dentro dos itens que coincidem com eles. Part number não tem
opções, porque quase cada item tem o seu.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import Connection, text

from ..estruturacao.canonicalizar import valor_valido
from ..pdm.modelo import Pdm

SUPORTE_MINIMO = 3        # itens necessários para usar o contexto dos outros atributos
BASE_MINIMA_PERCENTUAL = 20  # abaixo disto não mostra percentual


@dataclass
class Opcao:
    valor: str
    n: int
    pct: float | None
    fonte: str = "HISTORICO"


@dataclass
class Opcoes:
    atributo: str
    opcoes: list[Opcao] = field(default_factory=list)
    base: int = 0
    contexto: list[str] = field(default_factory=list)
    sem_opcoes_motivo: str | None = None


def opcoes(conn: Connection, pdm: Pdm, id_pdm: str, nome: str | None, atributo: str,
           preenchidos: dict[str, str | None], limite: int = 3, excluir: str | None = None) -> Opcoes:
    """`excluir`: código a deixar de fora do histórico (avaliação: o item não pode "colar a resposta")."""
    a = pdm.classes[id_pdm].atributo(atributo)
    out = Opcoes(atributo)
    if a is None:
        out.sem_opcoes_motivo = "atributo não existe na classe"
        return out
    if a.tipo == "LIVRE":
        out.sem_opcoes_motivo = "texto livre (referência, código): quase cada item tem o seu; digite"
        return out
    if nome:
        rows = conn.execute(text("select valores from material_identidade where id_pdm = :i and nome = :n and ativo and codigo <> :x"),
                            {"i": id_pdm, "n": nome, "x": excluir or ""}).all()
    else:
        rows = conn.execute(text("select valores from material_identidade where id_pdm = :i and ativo and codigo <> :x"),
                            {"i": id_pdm, "x": excluir or ""}).all()
    pool = [r[0] if isinstance(r[0], dict) else json.loads(r[0]) for r in rows]
    pool = [v for v in pool if v.get(atributo) and valor_valido(pdm, id_pdm, atributo, v[atributo])]
    if not pool:
        return out
    ordem = [x.nome for x in pdm.classes[id_pdm].atributos]
    contexto = [k for k in ordem if k != atributo and preenchidos.get(k)]
    # contexto mais específico primeiro; recua tirando o último atributo até haver suporte
    while True:
        sel = [v for v in pool if all(v.get(k) == preenchidos[k] for k in contexto)] if contexto else pool
        if len(sel) >= SUPORTE_MINIMO or not contexto:
            break
        contexto = contexto[:-1]
    cont = Counter(v[atributo] for v in sel)
    total = sum(cont.values())
    out.base, out.contexto = total, contexto
    for valor, n in cont.most_common(limite):
        out.opcoes.append(Opcao(valor, n, round(100 * n / total, 1) if total >= BASE_MINIMA_PERCENTUAL else None))
    return out
