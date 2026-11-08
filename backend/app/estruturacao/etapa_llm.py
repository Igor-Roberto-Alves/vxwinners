"""Etapa de LLM da estruturação: só entra onde as regras não fecharam a chave.

Cada chamada é registrada (tokens, tempo, resultado); o resultado é guardado em cache pelo
hash da entrada, então reexecutar custa zero. A saída do modelo é validada antes de gravar.
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy import text

from ..classes.resolver import IndiceClasses
from ..config import settings
from ..db import engine, transacao
from ..llm import cliente as _cli
from ..llm import extrator
from ..llm.prompt import PROMPT_VERSAO, monta_entrada
from ..pdm import repositorio
from ..pdm.modelo import Pdm
from . import persistir
from .executor import COLUNAS
from .modelo import Extracao
from .regras import extrai_por_regras


def entrada_material(m: dict) -> str:
    return monta_entrada({
        "GRUPO DO ERP (pode estar errado)": m.get("grupo"),
        "DESCRICAO LONGA": m.get("descricao_longa"),
        "DESCRICAO CURTA": m.get("descricao_curta"),
        "FABRICANTE (coluna do ERP)": m.get("fabricante"),
        "REFERENCIA DO FABRICANTE (coluna do ERP)": m.get("referencia_fabricante"),
    })


def classes_do_prompt(pdm: Pdm, grupo: str | None, ex_regras: Extracao):
    g = pdm.classes[ex_regras.id_pdm].grupo if ex_regras.id_pdm else grupo
    classes = sorted(pdm.classes_do_grupo(g), key=lambda c: c.id_pdm) if g else []
    return g, classes


def mescla(regras: Extracao, llm: Extracao) -> Extracao:
    """As regras mandam: o LLM só preenche o que elas deixaram vazio. Conflito vira aviso."""
    if not regras.id_pdm:
        if llm.id_pdm:
            llm.metodo = "LLM"
        return llm
    out = regras
    if llm.id_pdm and llm.id_pdm != regras.id_pdm:
        out.avisos.append(f"LLM discorda da classe ({llm.id_pdm})")
        return out
    if out.nome is None and llm.nome:
        out.nome = llm.nome
    for atr, v in llm.valores.items():
        atual = out.valores.get(atr)
        if atual is None or not atual.valor:
            if v.valor or not atual:
                out.valores[atr] = v
        elif v.valor and v.valor != atual.valor:
            out.avisos.append(f"conflito LLM/regra em {atr}: regra={atual.valor} llm={v.valor}")
    out.metodo = "REGRA+LLM"
    return out


def _cache_get(chaves: list[str]) -> dict[str, dict]:
    with engine().connect() as c:
        rows = c.execute(text("select chave, resultado from cache_extracao where chave = any(:k)"), {"k": chaves}).all()
    return {r[0]: r[1] for r in rows}


def _cache_put(c, itens: list[tuple[str, dict, str]]) -> None:
    if itens:
        c.execute(text("insert into cache_extracao (chave, resultado, modelo) values (:k, cast(:r as jsonb), :m) on conflict do nothing"),
                  [{"k": k, "r": json.dumps(r), "m": m} for k, r, m in itens])


def executa(limite: int | None = None, modelo: str | None = None, amostra: bool = False, concorrencia: int | None = None) -> dict:
    s = settings()
    modelo = modelo or s.llm_modelo_extracao
    pdm = repositorio.ativo()
    indice = IndiceClasses(pdm)
    ordem = "random()" if amostra else "m.codigo"
    sql = (f"select {COLUNAS} from material m left join material_identidade i using (codigo) "
           f"left join material_classificacao k using (codigo) "
           f"where i.completa is not true and coalesce(k.extrator, '') not like 'regras+llm%' "
           f"order by {ordem}" + (f" limit {int(limite)}" if limite else ""))
    with engine().connect() as c:
        mats = [dict(r._mapping) for r in c.execute(text(sql))]

    trabalho, sem_classes = [], []
    for m in mats:
        er = extrai_por_regras(pdm, indice, m)
        g, classes = classes_do_prompt(pdm, m.get("grupo"), er)
        if not classes:
            sem_classes.append((m, er))  # nada a perguntar ao modelo: fica o resultado das regras
            continue
        entrada = entrada_material(m)
        trabalho.append((m, er, classes, entrada, extrator.chave_cache(modelo, [c.id_pdm for c in classes], entrada)))

    em_cache = _cache_get([t[4] for t in trabalho])
    pendentes = [t for t in trabalho if t[4] not in em_cache]
    respostas: dict[str, extrator.Resposta] = {}
    t0 = time.time()
    with ThreadPoolExecutor(concorrencia or s.llm_concorrencia) as ex:
        futs = {ex.submit(extrator.chama, pdm, t[2], t[3], modelo): t for t in pendentes}
        feitos = 0
        for f in as_completed(futs):
            t = futs[f]
            respostas[t[4]] = f.result()
            feitos += 1
            if feitos % 200 == 0:
                print(f"  ... {feitos}/{len(pendentes)} chamadas ({time.time()-t0:.0f}s)", flush=True)

    itens, log, novos_cache = list(sem_classes), [], []
    for m, er, classes, entrada, chave in trabalho:
        if chave in em_cache:
            saida, origem = em_cache[chave], "cache"
        else:
            r = respostas[chave]
            saida, origem = r.saida, ("ok" if r.saida else "erro")
            if r.saida:
                novos_cache.append((chave, r.saida, modelo))
            log.append({"m": modelo, "h": hashlib.sha256(entrada.encode()).hexdigest()[:16], "ti": r.tokens_entrada,
                        "tc": r.cache_leitura, "to": r.tokens_saida, "ms": r.ms, "res": origem, "err": r.erro})
        if saida is None:
            continue  # falha de API: não grava, para a próxima execução tentar de novo
        ex_llm = extrator.valida(pdm, classes, saida, entrada)
        itens.append((m, mescla(er, ex_llm)))

    with transacao() as c:
        _cache_put(c, novos_cache)
        if log:
            c.execute(text("""insert into llm_chamada (finalidade, modelo, prompt_versao, entrada_hash, tokens_entrada,
                tokens_cache, tokens_saida, ms, resultado, erro) values ('estruturacao', :m, :pv, :h, :ti, :tc, :to, :ms, :res, :err)"""),
                      [{**l, "pv": PROMPT_VERSAO} for l in log])
        persistir.grava(c, pdm, itens, f"regras+llm:{PROMPT_VERSAO}")
        persistir.atualiza_estatisticas(c)

    rs = list(respostas.values())
    ti, to = sum(r.tokens_entrada for r in rs), sum(r.tokens_saida for r in rs)
    cr, cw = sum(r.cache_leitura for r in rs), sum(r.cache_escrita for r in rs)
    custo = sum(r.custo for r in rs)
    chamadas = len(rs)
    return {
        "candidatos": len(trabalho), "chamadas": chamadas, "do_cache": len(trabalho) - chamadas,
        "erros": sum(1 for r in rs if r.erro), "tokens_entrada": ti, "tokens_saida": to,
        "cache_leitura": cr, "cache_escrita": cw, "custo_usd": round(custo, 4),
        "custo_por_chamada_usd": round(custo / chamadas, 5) if chamadas else 0,
        "segundos": round(time.time() - t0, 1), "modelo": modelo,
        "primeiro_erro": next((r.erro for r in rs if r.erro), None),
    }


def executa_tudo(teto_usd: float = 60.0, lote: int = 2000, modelo: str | None = None, concorrencia: int | None = None) -> dict:
    """Processa todos os candidatos em lotes, gravando a cada lote. Para sozinho ao passar do teto de
    gasto estimado, ou se um lote inteiro falhar (credencial expirada, cota). Retomável."""
    gasto = 0.0
    total = {"lotes": 0, "chamadas": 0, "erros": 0, "custo_usd": 0.0, "interrompido_por": None}
    while True:
        r = executa(limite=lote, modelo=modelo, concorrencia=concorrencia)
        if r["candidatos"] == 0:
            break
        total["lotes"] += 1
        total["chamadas"] += r["chamadas"]
        total["erros"] += r["erros"]
        gasto += r["custo_usd"]
        total["custo_usd"] = round(gasto, 4)
        print(f"lote {total['lotes']}: {r['chamadas']} chamadas, {r['erros']} erros, US$ {r['custo_usd']:.2f} "
              f"(acumulado US$ {gasto:.2f}) em {r['segundos']}s", flush=True)
        if r["chamadas"] and r["erros"] == r["chamadas"]:
            total["interrompido_por"] = f"lote inteiro falhou: {r['primeiro_erro']}"
            break
        if gasto >= teto_usd:
            total["interrompido_por"] = f"teto de gasto de US$ {teto_usd:.0f} atingido"
            break
    return total
