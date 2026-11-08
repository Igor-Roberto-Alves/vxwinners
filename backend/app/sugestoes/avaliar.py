"""Mede o motor de sugestões na base estruturada: dado um item real, a opção certa aparece?

Para cada item (ativo, chave fechada) e cada atributo de lista, pergunta ao motor de produção as
opções com o contexto dos atributos anteriores (a pessoa preenche na ordem do PDM), deixando o
próprio item de fora do histórico. Mede acerto no 1º lugar e entre os 3 primeiros.
"""
from __future__ import annotations

import json
import random
from collections import defaultdict

from sqlalchemy import text

from ..db import engine
from ..pdm import repositorio
from . import ranking


def avalia(n: int = 1500, semente: int = 5) -> dict:
    rng = random.Random(semente)
    with engine().connect() as c:
        pdm = repositorio.ativo(c)
        linhas = c.execute(text("""select codigo, id_pdm, nome, valores from material_identidade
            where completa and ativo and nome is not null""")).all()
        rng.shuffle(linhas)
        agg = defaultdict(lambda: [0, 0, 0, 0])   # casos, acerto@1, acerto@3, sem opcoes
        for cod, idp, nome, valores in linhas[:n]:
            valores = valores if isinstance(valores, dict) else json.loads(valores)
            classe = pdm.classes[idp]
            anteriores: dict[str, str] = {}
            for a in classe.atributos:
                v = valores.get(a.nome)
                if not v:
                    continue
                if a.tipo != "LIVRE":
                    o = ranking.opcoes(c, pdm, idp, nome, a.nome, dict(anteriores), excluir=cod)
                    grupo = ("referencia" if classe.por_referencia else "especificacao") + ("/lista" if a.tipo == "LISTA" else "/medida")
                    k = agg[grupo]
                    k[0] += 1
                    vals = [x.valor for x in o.opcoes]
                    k[1] += vals[:1] == [v]
                    k[2] += v in vals
                    k[3] += not vals
                anteriores[a.nome] = v
    por = {g: {"casos": k[0], "top1": round(k[1] / k[0], 3), "top3": round(k[2] / k[0], 3), "sem_opcoes": round(k[3] / k[0], 3)}
           for g, k in sorted(agg.items()) if k[0]}
    tot = [sum(k[i] for k in agg.values()) for i in range(4)]
    return {"itens_amostrados": min(n, len(linhas)), "casos": tot[0], "top1": round(tot[1] / tot[0], 3),
            "top3": round(tot[2] / tot[0], 3), "por_grupo": por}
