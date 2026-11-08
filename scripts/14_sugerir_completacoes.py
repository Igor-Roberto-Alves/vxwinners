"""Completacoes possiveis para dado GENERICO, com probabilidade e teste retroativo.

Dado generico nao e ausencia de informacao, e uma RESTRICAO. 'ZINCADO' elimina
todo acabamento menos ZINCADO BRANCO e ZINCADO AMARELO; 'INOX' elimina os acos
carbono. O modelo:

  1. CANDIDATOS: valores da lista do PDM (da classe e do atributo) que REFINAM o
     termo - todo token do termo aparece, por prefixo, num token do valor.
     Um candidato so = nao era generico, era sinonimo faltando no dicionario.
  2. ORDEM: P(valor | o que o registro ja tem preenchido), Bayes ingenuo com
     suavizacao de Laplace, contado nos registros da propria base em que o
     atributo esta preenchido. A classe de resistencia A4-70 puxa o material
     para inox 316; 8.8 puxa para aco carbono.
  3. TESTE RETROATIVO: em registros com o valor especifico, esconde o valor,
     deixa so o termo generico e ve se o modelo acerta (deixando o proprio
     registro fora da contagem). Mede acerto e calibracao por faixa de
     probabilidade ANTES de qualquer uso.

A sugestao NUNCA vai para a caixa nem para a chave de identidade. Ela vira uma
pergunta pre-preenchida para o solicitante ou para a revisao:
  "O cadastro diz 'ZINCADO'. E ZINCADO BRANCO (87%) ou ZINCADO AMARELO (13%)?"

Entrada: artefatos/deteccao_ausentes.jsonl (os genericos) e decisoes_base.jsonl
(o contexto). Sem LLM.
Saida:   artefatos/completacoes_sugeridas.jsonl e o resumo.

Uso: python 14_sugerir_completacoes.py
"""

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm  # noqa: E402
from saneamento.texto import normalizar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--min-suporte", type=int, default=20,
               help="registros de treino minimos para a ordem valer mais que o empate")
a = p.parse_args()
ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")

# palavras do trecho que sao rotulo, nao valor
ROTULO = {"MATERIAL", "MAT", "CORPO", "ACAB", "ACABAMENTO", "TRATAMENTO", "REVESTIMENTO",
          "DE", "COM", "EM", "TIPO", "ACIONAMENTO", "NORMA", "CONF"}
# abreviacoes que o termo generico usa e a lista nao
EXPANDE = {"AC": "ACO", "SS": "INOX", "ZINC": "ZINCADO", "ZINCADA": "ZINCADO", "GALV": "GALVANIZADO",
           "CARB": "CARBONO", "INOXIDAVEL": "INOX", "BICROMATIZADO": "ZINCADO"}


def tokens_termo(trecho: str) -> list[str]:
    out = []
    for t in normalizar(trecho).split():
        t = EXPANDE.get(t, t)
        if t not in ROTULO and len(t) >= 2:
            out.append(t)
    return out


def candidatos(termo_tok: list[str], valores: list[str]) -> list[str]:
    """Valores da lista que refinam o termo: cada token do termo e prefixo de um token do valor."""
    if not termo_tok:
        return []
    out = []
    for v in valores:
        vt = normalizar(v).split()
        if all(any(u.startswith(t) for u in vt) for t in termo_tok):
            out.append(v)
    return out


# ------------------------------------------------------------------ contexto

print("Lendo decisoes...")
registros = {}                          # codigo -> (id_pdm, {atributo: valor})
with (ART / "decisoes_base.jsonl").open(encoding="utf-8") as fh:
    for linha in fh:
        d = json.loads(linha)
        if d.get("id_pdm"):
            registros[d["codigo"]] = (d["id_pdm"], {x["atributo"]: x["valor"]
                                                   for x in d["decisoes"] if x["valor"]})

# contagens por (classe, atributo-alvo): n(v) e n(v, outro=valor)
n_v: dict[tuple, Counter] = defaultdict(Counter)
n_vo: dict[tuple, Counter] = defaultdict(Counter)
dominio: dict[tuple, set] = defaultdict(set)    # (classe, outro) -> valores vistos
for cod, (cid, vals) in registros.items():
    for alvo, v in vals.items():
        n_v[(cid, alvo)][v] += 1
        for outro, o in vals.items():
            if outro != alvo:
                n_vo[(cid, alvo)][(v, outro, o)] += 1
                dominio[(cid, outro)].add(o)


def pontuar(cid, alvo, cands, contexto, excluir=None):
    """P(candidato | contexto) por Bayes ingenuo. excluir = registro deixado de fora."""
    nv, nvo = n_v[(cid, alvo)], n_vo[(cid, alvo)]
    contexto = {k: v for k, v in contexto.items() if k != alvo}
    log, suporte = {}, 0
    for c in cands:
        base_c = nv[c] - (1 if excluir and excluir.get(alvo) == c else 0)
        suporte += max(base_c, 0)
        lp = math.log(base_c + 1)                    # prior suavizado
        for outro, o in contexto.items():
            k = len(dominio[(cid, outro)]) or 1
            co = nvo[(c, outro, o)] - (1 if excluir and excluir.get(alvo) == c
                                        and excluir.get(outro) == o else 0)
            lp += math.log((max(co, 0) + 1) / (max(base_c, 0) + k))
        log[c] = lp
    m = max(log.values())
    z = sum(math.exp(x - m) for x in log.values())
    probs = {c: math.exp(x - m) / z for c, x in log.items()}
    return sorted(probs.items(), key=lambda kv: -kv[1]), suporte


def banda(p1, suporte):
    if suporte < a.min_suporte:
        return "SEM_BASE"            # poucos exemplos: pergunta aberta
    if p1 >= 0.90:
        return "PROVAVEL"            # confirmar a sugestao
    if p1 >= 0.60:
        return "INCLINADA"           # oferecer as duas primeiras
    return "ABERTA"                  # perguntar sem sugerir


# ------------------------------------------------------------------ genericos

det = [json.loads(l) for l in (ART / "deteccao_ausentes.jsonl").open(encoding="utf-8")]
genericos = [x for x in det if x["veredito"] == "PRESENTE_FORA_DO_PADRAO"]
saida, termos_por_alvo = [], defaultdict(Counter)
tipos = Counter()
for x in genericos:
    cid, alvo = x["id_pdm"], x["atributo"]
    classe = pdm.classes.get(cid)
    atr = next((t for t in classe.atributos if t.nome == alvo), None) if classe else None
    if atr is None or not atr.fechado:
        tipos["caixa numerica ou livre (fora do modelo)"] += 1
        continue
    tt = tokens_termo(x["trecho"])
    cands = candidatos(tt, atr.valores)
    contexto = registros.get(x["codigo"], (cid, {}))[1]
    if not cands:
        tipos["termo nao refina nenhum valor da lista"] += 1
        saida.append({**x, "termo": " ".join(tt), "candidatos": [], "banda": "SEM_CANDIDATO"})
        continue
    if len(cands) == 1:
        tipos["um candidato so (sinonimo faltando no dicionario)"] += 1
        saida.append({**x, "termo": " ".join(tt), "candidatos": [[cands[0], 1.0]],
                      "banda": "UNICO", "suporte": n_v[(cid, alvo)][cands[0]]})
        continue
    termos_por_alvo[(cid, alvo)][" ".join(tt)] += 1
    ordem, sup = pontuar(cid, alvo, cands, contexto)
    b = banda(ordem[0][1], sup)
    tipos[f"generico, banda {b}"] += 1
    top = ordem[:3]
    pergunta = (f"O cadastro diz {x['trecho']!r} para {alvo}. Qual destes: "
                + "; ".join(f"{v} ({100 * pp:.0f}%)" for v, pp in top) + "?")
    saida.append({**x, "termo": " ".join(tt), "candidatos": [[v, round(pp, 3)] for v, pp in ordem],
                  "banda": b, "suporte": sup, "pergunta": pergunta})

with (ART / "completacoes_sugeridas.jsonl").open("w", encoding="utf-8") as fh:
    for s in saida:
        fh.write(json.dumps(s, ensure_ascii=False) + "\n")

# ------------------------------------------------------------------ teste retroativo
# Para cada (classe, atributo, termo generico) visto na base, pega os registros
# cujo valor especifico e um dos candidatos, esconde o valor e preve.

faixas = [(0.9, 1.01, "PROVAVEL >=90%"), (0.6, 0.9, "INCLINADA 60-90%"), (0.0, 0.6, "ABERTA <60%")]
acerto = Counter()
total = Counter()
por_termo = []
for (cid, alvo), termos in termos_por_alvo.items():
    atr = next(t for t in pdm.classes[cid].atributos if t.nome == alvo)
    for termo, _ in termos.most_common(5):
        cands = candidatos(termo.split(), atr.valores)
        if len(cands) < 2:
            continue
        ok = n = 0
        for cod, (c2, vals) in registros.items():
            if c2 != cid or vals.get(alvo) not in cands:
                continue
            ordem, sup = pontuar(cid, alvo, cands, vals, excluir=vals)
            if sup < a.min_suporte:
                continue
            p1 = ordem[0][1]
            f = next(nome for lo, hi, nome in faixas if lo <= p1 < hi)
            total[f] += 1
            acerto[f] += int(ordem[0][0] == vals[alvo])
            n += 1
            ok += int(ordem[0][0] == vals[alvo])
            maioria = max(cands, key=lambda v: n_v[(cid, alvo)][v])
            acerto["_maioria"] += int(maioria == vals[alvo])
            total["_maioria"] += 1
        if n:
            por_termo.append((cid, alvo, termo, len(cands), n, ok / n))

print()
print("=" * 78)
print("COMPLETACOES PARA DADO GENERICO".center(78))
print("=" * 78)
print(f"caixas com dado generico (deteccao) ... {len(genericos):>8,}")
for k, v in tipos.most_common():
    print(f"  {v:>7,}  {k}")
print("\nTESTE RETROATIVO (valor especifico escondido, so o termo generico visivel)")
for _, _, f in faixas:
    if total[f]:
        print(f"  {f:22s} {total[f]:>6,} casos  acerto {100 * acerto[f] / total[f]:5.1f}%")
t = sum(total[f] for _, _, f in faixas)
if t:
    print(f"  {'todas as faixas':22s} {t:>6,} casos  acerto {100 * sum(acerto[f] for _, _, f in faixas) / t:5.1f}%"
          f"   (chutar o valor mais comum: {100 * acerto['_maioria'] / max(total['_maioria'], 1):.1f}%)")
print("\nPor termo (os mais frequentes):")
for cid, alvo, termo, nc, n, ac in sorted(por_termo, key=lambda x: -x[4])[:12]:
    print(f"  {cid} {alvo[:16]:16} {termo[:18]!r:20} {nc} candidatos  {n:>5,} casos  acerto {100 * ac:5.1f}%")
print("\nExemplos de pergunta ao solicitante:")
for s in [s for s in saida if s.get("pergunta")][:6]:
    print(f"  [{s['banda']}] {s['pergunta'][:150]}")
print(f"\nGravado: {ART / 'completacoes_sugeridas.jsonl'}")
