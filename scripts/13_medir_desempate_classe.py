"""Mede o ganho de desempatar a CLASSE por kNN de embedding (docs/08).

Nao altera o pipeline. Classifica a base com o classificador lexico, separa as
populacoes frageis e pergunta ao kNN o que ele faria em cada uma:

  empate           o lexico empatou entre classes irmas (mesmo substantivo,
                   nenhum qualificador no texto) e ficou com a primeira da lista
  grupo_corrigido  nada casou no GRUPO_MERCADORIA e a busca foi nas 44 classes

kNN = os 7 registros mais parecidos (cosseno, e5-small) entre os que o lexico
classifica com seguranca (substantivo + qualificador casados, conf >= 0,95),
votando com peso pela similaridade. No empate, so as classes empatadas votam.

Depois reprocessa a base so com regras, com e sem a troca, e mede o efeito em
SANEADO, chaves fechadas e codigos redundantes.

Uso:
  python 13_medir_desempate_classe.py                # ~5 min em CPU
  python 13_medir_desempate_classe.py --voto 0.85    # limiar do voto do kNN

Saida em artefatos/desempate_classe/: trocas.csv (cada troca proposta, para
revisao a mao) e resumo.json.
"""

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, Pipeline, ler_base  # noqa: E402
from saneamento.embeddings import PREFIXO_CONSULTA, Codificador  # noqa: E402
from saneamento.regras import Sujeito  # noqa: E402
from saneamento.sinonimos import expandir_sujeito  # noqa: E402
from saneamento.texto import juntar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--k", type=int, default=7)
p.add_argument("--voto", type=float, default=0.85,
               help="fracao minima do voto do kNN para propor a troca")
a = p.parse_args()

ART = Path(a.artefatos)
SAIDA = ART / "desempate_classe"
SAIDA.mkdir(parents=True, exist_ok=True)
pdm = Pdm.carregar(ART / "pdm.json")
rows = ler_base(a.base)
COLUNAS = ("DESCRICAO_LONGA", "DESCRICAO_CURTA", "FABRICANTE", "REFERENCIA_FABRICANTE")


def texto_de(r):
    return juntar(*(str(r.get(c, "") or "") for c in COLUNAS))


def curto(r):
    return juntar(str(r.get("DESCRICAO_LONGA") or ""), str(r.get("DESCRICAO_CURTA") or ""))[:200]


# ------------------------------------------------ 1. classificacao lexica atual
clf = Pipeline(pdm).clf
sujeitos = [clf.classificar(texto_de(r), str(r.get("GRUPO_MERCADORIA") or "").strip())
            for r in rows]


def populacao(s):
    if s.classe is None:
        return "sem classe"
    if s.empate:
        return "empate"
    if s.grupo_corrigido:
        return "grupo_corrigido"
    return "seguro" if s.confianca >= 0.95 else "so substantivo"


pop = collections.Counter(populacao(s) for s in sujeitos)
print("== Populacao")
for k, v in pop.most_common():
    print(f"  {v:7,}  {k}")

# ------------------------------------------------ 2. kNN
print("\ncodificando a base (e5-small)...", flush=True)
enc = Codificador(lote=128)
E = np.array(enc.codificar([curto(r) for r in rows], prefixo=PREFIXO_CONSULTA), dtype=np.float32)
E /= np.linalg.norm(E, axis=1, keepdims=True)
ref = [i for i, s in enumerate(sujeitos) if populacao(s) == "seguro"]
R, yr = E[ref], np.array([sujeitos[i].classe.id_pdm for i in ref])


def knn(i, permitidas=None):
    sim = R @ E[i]
    if permitidas is not None:
        sim = np.where(np.isin(yr, list(permitidas)), sim, -1.0)
    idx = np.argpartition(-sim, a.k)[:a.k]
    voto = collections.Counter()
    for j in idx:
        if sim[j] > 0:
            voto[yr[j]] += float(sim[j])
    if not voto:
        return None, 0.0
    c, peso = voto.most_common(1)[0]
    return c, peso / sum(voto.values())


trocas = {}                    # codigo -> classe nova, so na populacao empate
linhas = []
for i, s in enumerate(sujeitos):
    tipo = populacao(s)
    if tipo not in ("empate", "grupo_corrigido"):
        continue
    c, voto = knn(i, set(s.empate) if tipo == "empate" else None)
    if c and c != s.classe.id_pdm and voto >= a.voto:
        cod = str(rows[i]["CODIGO_MATERIAL"])
        linhas.append({"CODIGO": cod, "POPULACAO": tipo, "LEXICO": s.classe.id_pdm,
                       "KNN": c, "VOTO": round(voto, 2), "DESCRICAO": curto(rows[i])})
        if tipo == "empate":
            trocas[cod] = c

with (SAIDA / "trocas.csv").open("w", encoding="utf-8", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(linhas[0]) if linhas else ["CODIGO"])
    w.writeheader()
    w.writerows(linhas)
por_pop = collections.Counter(x["POPULACAO"] for x in linhas)
print(f"\n== Trocas propostas (voto >= {a.voto})")
for k in ("empate", "grupo_corrigido"):
    print(f"  {k:16} {por_pop[k]:5}  de {pop[k]:,}")
print("  (so as de 'empate' sao aplicadas na medicao abaixo: em grupo_corrigido o")
print("   kNN errou a maioria na revisao a mao - ver docs/08)")


# ------------------------------------------------ 3. efeito no pipeline
def rodar(com_troca: bool):
    pipe = Pipeline(pdm)
    original = pipe.clf.classificar
    out = []
    for r in rows:
        cid = trocas.get(str(r["CODIGO_MATERIAL"])) if com_troca else None
        if cid:
            c = pdm.classes[cid]
            s = pipe.clf._buscar(expandir_sujeito(texto_de(r)), [c])
            if s.classe is None:
                s = Sujeito(classe=c, substantivo=c.substantivos[0])
            s.empate, s.confianca = (), max(s.confianca, 0.6)
            pipe.clf.classificar = lambda *_a, _s=s, **_k: _s
        out.append(pipe.processar(r))
        pipe.clf.classificar = original
    clusters = collections.defaultdict(list)
    for x in out:
        if x.chave_identidade:
            clusters[x.chave_identidade].append(x.codigo)
    return {
        "SANEADO": sum(x.estado == "SANEADO" for x in out),
        "chaves fechadas": sum(1 for x in out if x.chave_identidade),
        "codigos redundantes": sum(len(v) - 1 for v in clusters.values() if len(v) > 1),
    }, clusters


antes, _ = rodar(False)
depois, cl = rodar(True)
print("\n== Efeito no pipeline (so regras), aplicando as trocas de empate")
for k in antes:
    print(f"  {k:20} {antes[k]:7,} -> {depois[k]:7,}  ({depois[k] - antes[k]:+,})")
novos = [v for v in cl.values() if len(v) > 1 and any(c in trocas for c in v)]
print(f"  clusters com registro reclassificado: {len(novos)}  (revise: {SAIDA / 'resumo.json'})")

json.dump({"populacao": pop, "trocas_por_populacao": por_pop, "antes": antes,
           "depois": depois, "clusters_com_reclassificado": novos},
          (SAIDA / "resumo.json").open("w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"\nGravado: {SAIDA / 'trocas.csv'}")
