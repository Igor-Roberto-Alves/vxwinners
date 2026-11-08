"""Avalia a extração por LLM contra um gabarito derivado da própria base.

Gabarito: registros cuja descrição já está no formato `ATRIBUTO: VALOR` e foi lida por regras com
confiança alta. Para o teste, os rótulos são removidos (fica o texto telegráfico, como na maior parte
da base) e o modelo precisa recuperar os mesmos valores.

LIMITE: o texto de entrada é feito dos mesmos valores do gabarito, então o recall é otimista. A
precisão por atributo (o modelo coloca o valor no atributo certo?) é a medida que importa. Isto não
substitui uma amostra anotada à mão por especialistas.
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from ..classes.resolver import IndiceClasses
from ..config import RAIZ_BACKEND, settings
from ..llm import extrator
from ..llm.prompt import monta_entrada
from ..pdm import repositorio
from .executor import materiais
from .etapa_llm import classes_do_prompt
from .regras import extrai_por_regras, _partes


def _gabarito(pdm, indice, m):
    ex = extrai_por_regras(pdm, indice, m)
    if not ex.id_pdm or not ex.nome or ex.confianca_classe < 0.85:
        return None
    rot = {k: v for k, v in ex.valores.items() if v.origem == "REGRA_ROTULO" and v.valor and v.confianca >= 0.95}
    obrig = {a.nome for a in pdm.obrigatorios_aplicaveis(ex.id_pdm, ex.nome, {k: v.valor for k, v in rot.items()})}
    if len(rot) < 3 or len(obrig - set(rot)) > 1:
        return None
    return ex, rot


def telegrafico(texto: str, rot) -> str:
    partes = _partes(texto)
    cabeca = partes[0] if partes and ":" not in partes[0] else ""
    valores = [v.bruto for v in rot.values() if v.bruto]
    return re.sub(r"\s+", " ", " ".join([cabeca, *valores])).strip()


def avaliar(n: int = 120, semente: int = 7, modelo: str | None = None) -> dict:
    modelo = modelo or settings().llm_modelo_extracao
    pdm = repositorio.ativo()
    indice = IndiceClasses(pdm)
    cand = []
    for m in materiais():
        g = _gabarito(pdm, indice, m)
        if g:
            cand.append((m, *g))
    random.Random(semente).shuffle(cand)
    amostra = cand[:n]

    def roda(t):
        m, ex, rot = t
        entrada_txt = telegrafico(m["descricao_longa"], rot)
        entrada = monta_entrada({"GRUPO DO ERP (pode estar errado)": m["grupo"], "DESCRICAO LONGA": entrada_txt})
        _, classes = classes_do_prompt(pdm, m["grupo"], ex)
        r = extrator.chama(pdm, classes, entrada, modelo)
        return t, entrada_txt, r, extrator.valida(pdm, classes, r.saida, entrada)

    with ThreadPoolExecutor(settings().llm_concorrencia) as pool:
        res = list(pool.map(roda, amostra))

    por_tipo = defaultdict(lambda: [0, 0, 0])   # certo, errado, perdido
    por_attr = defaultdict(lambda: [0, 0, 0])
    classe_ok = classe_total = erros_chamada = 0
    custo = 0.0
    exemplos_errados = []
    for (m, gold, rot), txt, r, llm in res:
        custo += r.custo
        if r.erro:
            erros_chamada += 1
            continue
        classe_total += 1
        classe_ok += llm.id_pdm == gold.id_pdm
        for atr, gv in rot.items():
            tipo = pdm.classes[gold.id_pdm].atributo(atr).tipo
            tipo = "LISTA" if tipo == "LISTA" else ("LIVRE" if tipo == "LIVRE" else "MEDIDA")
            lv = llm.valores.get(atr)
            if lv and lv.valor and lv.confianca >= 0.9:
                k = 0 if lv.valor == gv.valor else 1
                if k == 1 and len(exemplos_errados) < 12:
                    exemplos_errados.append({"texto": txt, "atributo": atr, "gabarito": gv.valor, "llm": lv.valor, "trecho": lv.trecho})
            else:
                k = 2
            por_tipo[tipo][k] += 1
            por_attr[atr][k] += 1

    def lin(d):
        c, e, p = d
        return {"certo": c, "errado": e, "perdido": p, "precisao": round(c / (c + e), 3) if c + e else None,
                "recall": round(c / (c + e + p), 3) if c + e + p else None}

    tot = [sum(v[i] for v in por_tipo.values()) for i in range(3)]
    out = {"modelo": modelo, "amostra": len(res), "candidatos_no_gabarito": len(cand), "erros_de_chamada": erros_chamada,
           "classe_acerto": round(classe_ok / classe_total, 3) if classe_total else None,
           "geral": lin(tot), "por_tipo": {k: lin(v) for k, v in por_tipo.items()},
           "atributos_com_mais_erro": sorted(((k, v[1]) for k, v in por_attr.items() if v[1]), key=lambda x: -x[1])[:8],
           "exemplos_errados": exemplos_errados, "custo_usd": round(custo, 4)}
    destino = RAIZ_BACKEND / "artefatos" / "avaliacao_llm.json"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    return out
