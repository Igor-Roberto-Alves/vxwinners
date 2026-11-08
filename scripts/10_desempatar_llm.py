"""Desempate por LLM nos registros escalados, em paralelo, sem passar pelo pipeline.

Existe como script separado de proposito: `Pipeline.processar_lote` chama o
Bedrock em laco sequencial, e 4.341 registros a ~2,5s por chamada dao 3 horas de
parede. Aqui as chamadas vao num pool de threads, o que derruba para ~10 min.

Tambem evita reprocessar a extracao: le `artefatos/decisoes_base.jsonl`, que ja
tem a decisao de cada caixa, e trata somente o residuo escalado.

Toda proposta do LLM passa pelo MESMO validador das outras camadas: valor fora
da lista de valores permitidos do PDM e recusado, venha de onde vier. E toda
caixa resolvida alimenta o dicionario aprendido, para a mesma duvida nao custar
outra chamada.

Uso:
  python 10_desempatar_llm.py --limite 50 --threads 8     # teste
  python 10_desempatar_llm.py                            # tudo, ~10 min
  python 10_desempatar_llm.py --so-contar                # quanto custaria
"""

import argparse
import csv
import json
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, Validador, ler_base  # noqa: E402
from saneamento.aprendizado import Aprendizado  # noqa: E402
from saneamento.llm import MODELO_PADRAO, DesempateLlm  # noqa: E402
from saneamento.texto import juntar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--modelo", default=MODELO_PADRAO)
p.add_argument("--threads", type=int, default=16)
p.add_argument("--limite", type=int, default=0)
p.add_argument("--so-contar", action="store_true", help="estima custo e sai")
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")
validador = Validador(pdm)

# estados que justificam chamar o LLM. PENDENTE puro fica de fora: se ninguem
# viu nada no texto, nenhum modelo preenche sem inventar.
ESCALAVEIS = ("CONFLITO", "AMBIGUO", "INVALIDO", "INCERTO")

print("Lendo a trilha de decisoes...")
alvos = []
with (ART / "decisoes_base.jsonl").open(encoding="utf-8") as fh:
    for linha in fh:
        d = json.loads(linha)
        if not d["id_pdm"]:
            continue
        foco = [x["atributo"] for x in d["decisoes"] if x["estado"] in ESCALAVEIS]
        if foco:
            alvos.append((d["codigo"], d["id_pdm"], foco))

base = {r["CODIGO_MATERIAL"]: r for r in ler_base(a.base)}
for i, (cod, cid, foco) in enumerate(alvos):
    o = base.get(cod, {})
    alvos[i] = (cod, cid, foco, juntar(
        o.get("DESCRICAO_LONGA", ""), o.get("DESCRICAO_CURTA", ""),
        o.get("FABRICANTE", ""), o.get("REFERENCIA_FABRICANTE", "")))

if a.limite:
    alvos = alvos[: a.limite]

n_caixas = sum(len(f) for _, _, f, _ in alvos)
print(f"registros escalados ................... {len(alvos):>7,}")
print(f"caixas a desempatar ................... {n_caixas:>7,}")
# medidos na validacao do agente do Bedrock: ~2.157 tokens entrada, ~204 saida
custo = len(alvos) * (2157 / 1e6 * 1.00 + 204 / 1e6 * 5.00)
print(f"custo estimado (Haiku 4.5) ............ US$ {custo:>7.2f}")
print(f"modelo ................................ {a.modelo}")
if a.so_contar:
    sys.exit(0)

llm = DesempateLlm(modelo=a.modelo, cache=ART / "cache_llm")
aprendizado = Aprendizado(ART / "aprendizado.json")
trava = threading.Lock()
cont = Counter()
resultados = []
t0 = time.time()


def tratar(alvo):
    cod, cid, foco, texto = alvo
    classe = pdm.classes[cid]
    r = llm.desempatar(classe, texto, foco, [f"caixas em duvida: {', '.join(foco)}"])
    if r.erro and not r.valores:
        with trava:
            cont["erro"] += 1
            cont["ultimo_erro"] = 1
        return None

    por_nome = {x.nome: x for x in classe.atributos}
    aceitos, recusados = [], []
    for nome in foco:
        valor = (r.valores or {}).get(nome)
        atributo = por_nome.get(nome)
        if atributo is None:
            continue
        if valor is None:
            recusados.append((nome, None, "LLM devolveu null"))
            continue
        v = validador.valor(atributo, valor)
        if not v.ok:
            recusados.append((nome, valor, v.motivo))
            continue
        trecho = (r.evidencias or {}).get(nome, "")
        aceitos.append((nome, v.valor, trecho))
        if trecho:
            with trava:
                # `cod` e a procedencia: a linha em que o LLM leu este trecho
                aprendizado.aprender(atributo, trecho, v.valor, "llm", cid,
                                     codigos=cod)

    with trava:
        cont["registros"] += 1
        cont["aceitos"] += len(aceitos)
        cont["recusados"] += len(recusados)
        cont["nulos"] += sum(1 for _, v, _ in recusados if v is None)
        cont["do_cache"] += int(r.do_cache)
        if cont["registros"] % 200 == 0:
            dt = time.time() - t0
            print(f"  {cont['registros']:>6,}/{len(alvos):,}  "
                  f"aceitos={cont['aceitos']:,} recusados={cont['recusados']:,}  "
                  f"{cont['registros'] / max(dt, 1):.1f} reg/s  "
                  f"dicionario={len(aprendizado.entradas)}", flush=True)
    return {"codigo": cod, "id_pdm": cid,
            "aceitos": [{"atributo": n, "valor": v, "evidencia": e} for n, v, e in aceitos],
            "recusados": [{"atributo": n, "proposto": v, "motivo": m} for n, v, m in recusados]}


print(f"\nchamando o Bedrock com {a.threads} threads...\n")
with ThreadPoolExecutor(max_workers=a.threads) as ex:
    futuros = {ex.submit(tratar, x): x for x in alvos}
    for fut in as_completed(futuros):
        try:
            r = fut.result()
            if r:
                resultados.append(r)
        except Exception as e:                      # noqa: BLE001
            with trava:
                cont["excecao"] += 1
                print(f"  excecao: {type(e).__name__}: {e}", flush=True)

minutos = (time.time() - t0) / 60
aprendizado.salvar()
llm.salvar_cache() if hasattr(llm, "salvar_cache") else None

saida = ART / "desempate_llm.jsonl"
with saida.open("w", encoding="utf-8") as fh:
    for r in resultados:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")

print()
print("=" * 78)
print("DESEMPATE POR LLM".center(78))
print("=" * 78)
print(f"Registros tratados .................... {cont['registros']:>8,}")
print(f"  do cache (sem chamada nova) ......... {cont['do_cache']:>8,}")
print(f"  com erro de chamada ................. {cont['erro']:>8,}")
print(f"Caixas ACEITAS (passaram no validador)  {cont['aceitos']:>8,}  "
      f"{100 * cont['aceitos'] / max(n_caixas, 1):>5.1f}% das escaladas")
print(f"Caixas recusadas ...................... {cont['recusados']:>8,}")
print(f"  o LLM devolveu null (correto) ....... {cont['nulos']:>8,}")
print(f"  valor fora da lista do PDM .......... {cont['recusados'] - cont['nulos']:>8,}")
e = aprendizado.estatisticas()
print(f"Dicionario aprendido .................. {e['entradas']:>8,} termos "
      f"({e['confiaveis']} confiaveis)")
print(f"Tempo ................................. {minutos:>8.1f} min")
print(llm.resumo())
if llm.erro_cliente:
    print(f"ultimo erro: {llm.erro_cliente[:160]}")
print(f"\nGravado: {saida}")
print(f"Gravado: {ART / 'aprendizado.json'}")
