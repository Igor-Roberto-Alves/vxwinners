"""Separa dado AUSENTE de dado PERDIDO nos registros saneados e incompletos.

Quando uma caixa obrigatoria fica vazia, o pipeline sabe so que NAO ACHOU o
valor - nao que o texto nao o traz. Este script pergunta ao LLM, no Bedrock,
apenas se o texto MENCIONA o atributo e qual e o trecho literal. O LLM nunca
escreve valor em caixa nenhuma:

  - o trecho devolvido tem de existir no texto (conferido por codigo); se nao
    existe, a resposta e descartada e conta como AUSENTE;
  - se o trecho e um valor valido do PDM, a caixa estava PERDIDA (bug de
    extracao); se nao e, o dado esta PRESENTE FORA DO PADRAO (deveria ser
    PENDENTE, nao saneado).

Quem vai ao LLM:
  - toda caixa faltante com SINAL no texto (rotulo do atributo escrito, valor
    parecido com um da lista, grandeza da unidade certa sobrando);
  - uma AMOSTRA aleatoria das caixas sem sinal, para estimar com intervalo de
    confianca quantas estao perdidas no grupo que a heuristica chama de ausente.

Saida: artefatos/deteccao_ausentes.jsonl (uma linha por caixa) e o resumo.
Nao altera saneado_base.csv nem decisoes_base.jsonl.

Uso:
  python 12_detectar_ausentes.py --so-contar          # custo estimado, sem chamar
  python 12_detectar_ausentes.py                      # amostra de 400 sem sinal
  python 12_detectar_ausentes.py --amostra 800
"""

import argparse
import csv
import difflib
import hashlib
import json
import math
import random
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, Validador, ler_base  # noqa: E402
from saneamento.caixas import tipo_da_caixa  # noqa: E402
from saneamento.llm import MODELO_PADRAO  # noqa: E402
from saneamento.texto import normalizar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--modelo", default=MODELO_PADRAO)
p.add_argument("--threads", type=int, default=16)
p.add_argument("--amostra", type=int, default=400,
               help="caixas SEM sinal sorteadas para estimar a taxa de perda")
p.add_argument("--semente", type=int, default=20261107)
p.add_argument("--so-contar", action="store_true")
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")
validador = Validador(pdm)

# ------------------------------------------------------------------ sinais

UNIDADE = {
    "MM2": r"\d+(?:[.,]\d+)?\s?MM2",
    "MM": r"\d+(?:[.,]\d+)?\s?MM(?!2)",
    "POL": r"\d+(?:[./]\d+)*\s?POL",
    "BAR": r"\d+(?:[.,]\d+)?\s?(?:BAR|PSI|KGF|MPA|LBS)",
}
ROTULOS = {
    "MATERIAL": ["MATERIAL", "MAT"], "ACABAMENTO": ["ACABAMENTO", "ACAB", "TRATAMENTO", "REVESTIMENTO"],
    "NORMA": ["NORMA", "CONF", "PADRAO"], "APLICACAO": ["APLICACAO", "APLIC", "USO"],
    "MODELO EQUIPAMENTO": ["MODELO", "MOD", "EQUIP"], "CLASSE RESISTENCIA": ["CLASSE", "GRAU"],
    "TIPO": ["TIPO"],
}


def sinal(atributo, texto: str, usados: set[str]) -> str | None:
    """Motivo para suspeitar que o dado esta no texto, ou None."""
    tipo = tipo_da_caixa(atributo)
    if tipo == "NUMERICA":
        f = normalizar(atributo.formato)
        for u in (u for u in ("MM2", "MM", "POL", "BAR") if u in f):
            for m in re.finditer(UNIDADE[u], texto):
                if normalizar(m.group(0)).replace(" ", "") not in usados:
                    return f"grandeza {u} sobrando"
        return None
    if atributo.fechado:
        for r in ROTULOS.get(atributo.nome, [atributo.nome]):
            if re.search(rf"(?<![A-Z]){re.escape(r)}(?![A-Z])", texto):
                return "rotulo do atributo escrito"
        toks = texto.split()
        grams = {" ".join(toks[i:i + n]) for n in (1, 2, 3) for i in range(len(toks) - n + 1)}
        for v in atributo.valores:
            vv = normalizar(v)
            if len(vv) >= 5 and difflib.get_close_matches(vv, grams, n=1, cutoff=0.86):
                return "parecido com valor da lista"
    return None


# ------------------------------------------------------------------ levantamento

print("Levantando caixas faltantes em registros saneados e incompletos...")
base = {str(r["CODIGO_MATERIAL"]): r for r in ler_base(a.base)}
reg = {x["CODIGO_MATERIAL"]: x for x in csv.DictReader((ART / "saneado_base.csv").open(encoding="utf-8"))}
caixas = []                       # (codigo, id_pdm, atributo, motivo|None)
with (ART / "decisoes_base.jsonl").open(encoding="utf-8") as fh:
    for linha in fh:
        d = json.loads(linha)
        r = reg.get(d["codigo"])
        if not r or r.get("ESTADO") != "SANEADO" or r.get("COMPLETO") == "1":
            continue
        classe = pdm.classes.get(d["id_pdm"])
        if classe is None:
            continue
        b = base.get(d["codigo"], {})
        texto = normalizar(f"{b.get('DESCRICAO_LONGA', '')} {b.get('DESCRICAO_CURTA', '')}")
        usados = {normalizar(x["valor"]).replace(" ", "") for x in d["decisoes"] if x["valor"]}
        por_nome = {x.nome: x for x in classe.atributos}
        for x in d["decisoes"]:
            at = por_nome.get(x["atributo"])
            if x["estado"] == "PENDENTE" and at is not None:
                caixas.append((d["codigo"], d["id_pdm"], at.nome, sinal(at, texto, usados)))

com_sinal = [c for c in caixas if c[3]]
sem_sinal = [c for c in caixas if not c[3]]
random.Random(a.semente).shuffle(sem_sinal)
amostra = sem_sinal[: a.amostra]
alvo = com_sinal + amostra

por_registro: dict[str, list] = defaultdict(list)
for c in alvo:
    por_registro[c[0]].append(c)

print(f"caixas faltantes ...................... {len(caixas):>8,}")
print(f"  com sinal no texto (todas vao) ...... {len(com_sinal):>8,}")
print(f"  sem sinal ........................... {len(sem_sinal):>8,}  (amostra de {len(amostra):,})")
print(f"chamadas (uma por registro) ........... {len(por_registro):>8,}")

# ------------------------------------------------------------------ prompt

SISTEMA = """Voce audita uma extracao de atributos de materiais industriais.

Para cada atributo perguntado, diga se o TEXTO do cadastro informa o VALOR
daquele atributo, e copie o trecho.

Regras:
- PRESENTE so quando o texto traz o valor do atributo. Copie o trecho EXATAMENTE
  como esta no texto, curto (so o valor e, se houver, a unidade).
- O nome do atributo sozinho nao e valor: 'MATERIAL' sem material depois e
  AUSENTE.
- Valor de OUTRO atributo nao conta: o numero depois de 'COD FABRICANTE' e
  referencia, nao FABRICANTE; o diametro nao e o comprimento.
- Nao deduza nem complete. Se o texto nao escreve, e AUSENTE, mesmo que o valor
  seja obvio para quem conhece a peca.
- Valor generico conta como PRESENTE ('ACO CARBONO' quando a lista pede o grau
  do aco): voce diz se o texto informa, nao se o valor esta no padrao.
"""


def descrever(atributo) -> str:
    exemplos = " | ".join(atributo.valores[:12]) if atributo.fechado else ""
    s = f"- {atributo.nome} (formato: {atributo.formato or 'lista'})"
    return s + (f"; exemplos de valores: {exemplos}" if exemplos else "")


def ferramenta(nomes):
    return {"toolSpec": {
        "name": "responder",
        "description": "Para cada atributo, se o texto informa o valor e o trecho literal.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"caixas": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "atributo": {"type": "string", "enum": nomes},
                    "status": {"type": "string", "enum": ["PRESENTE", "AUSENTE"]},
                    "trecho": {"type": ["string", "null"]},
                },
                "required": ["atributo", "status", "trecho"],
                "additionalProperties": False,
            }}},
            "required": ["caixas"],
            "additionalProperties": False,
        }},
    }}


def montar(codigo):
    itens = por_registro[codigo]
    classe = pdm.classes[itens[0][1]]
    por_nome = {x.nome: x for x in classe.atributos}
    nomes = [i[2] for i in itens]
    b = base.get(codigo, {})
    texto = " | ".join(str(b.get(c, "") or "") for c in ("DESCRICAO_LONGA", "DESCRICAO_CURTA"))
    pergunta = (f"CLASSE: {' / '.join(classe.substantivos[:1])} "
                f"{(classe.qualificadores or [''])[0]} ({classe.id_pdm})\n"
                f"TEXTO DO CADASTRO: {texto}\n\n"
                f"ATRIBUTOS:\n" + "\n".join(descrever(por_nome[n]) for n in nomes))
    corpo = {
        "modelId": a.modelo,
        "system": [{"text": SISTEMA}],
        "messages": [{"role": "user", "content": [{"text": pergunta}]}],
        "toolConfig": {"tools": [ferramenta(nomes)], "toolChoice": {"tool": {"name": "responder"}}},
        "inferenceConfig": {"maxTokens": 80 + 60 * len(nomes)},
    }
    if not re.search(r"(sonnet-5|opus-5|opus-4-[6-9]|fable-5)", a.modelo):
        corpo["inferenceConfig"]["temperature"] = 0
    return corpo


# custo: ~3,5 caracteres por token, mais a ferramenta; Haiku 4.5 US$1/M entrada, US$5/M saida
tok_ent = sum(len(json.dumps(montar(c), ensure_ascii=False)) / 3.5 for c in por_registro)
tok_sai = sum(25 + 30 * len(v) for v in por_registro.values())
print(f"custo estimado ........................ US$ {tok_ent / 1e6 * 1 + tok_sai / 1e6 * 5:>7.2f}")
print(f"modelo ................................ {a.modelo}")
if a.so_contar:
    sys.exit(0)

# ------------------------------------------------------------------ chamadas

import boto3  # noqa: E402

cliente = boto3.client("bedrock-runtime")
CACHE = ART / "cache_deteccao"
CACHE.mkdir(exist_ok=True)
trava = threading.Lock()
cont = Counter()
saida = []
t0 = time.time()


def tratar(codigo):
    corpo = montar(codigo)
    chave = hashlib.sha256(json.dumps(corpo, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    arq = CACHE / f"{chave}.json"
    if arq.exists():
        resp = json.loads(arq.read_text(encoding="utf-8"))
        uso = {}
        with trava:
            cont["do_cache"] += 1
    else:
        try:
            r = cliente.converse(**corpo)
        except Exception as e:                               # noqa: BLE001
            with trava:
                cont["erro"] += 1
                cont["ultimo_erro"] = 0
                print(f"  erro: {str(e)[:140]}", flush=True)
            return
        uso = r.get("usage", {})
        resp = next((bl["toolUse"]["input"] for bl in r["output"]["message"]["content"]
                     if "toolUse" in bl), {}) or {}
        arq.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")

    b = base.get(codigo, {})
    texto_n = normalizar(f"{b.get('DESCRICAO_LONGA', '')} {b.get('DESCRICAO_CURTA', '')}")
    respostas = {x.get("atributo"): x for x in (resp.get("caixas") or [])}
    linhas = []
    for (cod, cid, nome, motivo) in por_registro[codigo]:
        x = respostas.get(nome, {})
        status, trecho = x.get("status", "AUSENTE"), (x.get("trecho") or "").strip()
        verificado = bool(trecho) and normalizar(trecho) in texto_n
        if status == "PRESENTE" and not verificado:
            veredito = "AUSENTE"                  # trecho que nao esta no texto: descartado
            nota = "trecho do LLM nao existe no texto"
        elif status == "PRESENTE":
            atributo = next(at for at in pdm.classes[cid].atributos if at.nome == nome)
            v = validador.valor(atributo, trecho)
            veredito = "PERDIDO" if v.ok else "PRESENTE_FORA_DO_PADRAO"
            nota = f"valido: {v.valor}" if v.ok else v.motivo
        else:
            veredito, nota = "AUSENTE", ""
        linhas.append({"codigo": cod, "id_pdm": cid, "atributo": nome,
                       "grupo": "com_sinal" if motivo else "amostra_sem_sinal",
                       "sinal": motivo, "veredito": veredito, "trecho": trecho, "nota": nota})
    with trava:
        cont["chamadas"] += 1
        cont["tok_ent"] += uso.get("inputTokens", 0)
        cont["tok_sai"] += uso.get("outputTokens", 0)
        saida.extend(linhas)
        if cont["chamadas"] % 250 == 0:
            print(f"  {cont['chamadas']:>6,}/{len(por_registro):,}", flush=True)


print(f"\nchamando o Bedrock com {a.threads} threads...\n")
with ThreadPoolExecutor(max_workers=a.threads) as ex:
    for f in as_completed([ex.submit(tratar, c) for c in por_registro]):
        f.result()

# ACRESCENTA ao que ja foi detectado, em vez de sobrescrever. A extracao parte
# do zero a cada execucao, e uma caixa marcada GENERICO numa rodada anterior ja
# nao aparece como faltante nesta: sobrescrever apagava as marcacoes antigas, e
# reaplicar o arquivo as desfazia. Onde (codigo, atributo) repete, vale a nova.
ARQ_SAIDA = ART / "deteccao_ausentes.jsonl"
juntas = {}
if ARQ_SAIDA.exists():
    for linha in ARQ_SAIDA.open(encoding="utf-8"):
        x = json.loads(linha)
        juntas[(x["codigo"], x["atributo"])] = x
for x in saida:
    juntas[(x["codigo"], x["atributo"])] = x
with ARQ_SAIDA.open("w", encoding="utf-8") as fh:
    for x in sorted(juntas.values(), key=lambda x: (x["codigo"], x["atributo"])):
        fh.write(json.dumps(x, ensure_ascii=False) + "\n")


def wilson(k, n, z=1.96):
    if not n:
        return 0.0, 0.0, 0.0
    pp = k / n
    den = 1 + z * z / n
    c = (pp + z * z / (2 * n)) / den
    m = z * math.sqrt(pp * (1 - pp) / n + z * z / (4 * n * n)) / den
    return pp, max(0.0, c - m), min(1.0, c + m)


custo = cont["tok_ent"] / 1e6 * 1.00 + cont["tok_sai"] / 1e6 * 5.00
print()
print("=" * 78)
print("AUSENTE x PERDIDO".center(78))
print("=" * 78)
for grupo in ("com_sinal", "amostra_sem_sinal"):
    g = [x for x in saida if x["grupo"] == grupo]
    c = Counter(x["veredito"] for x in g)
    print(f"\n{grupo}: {len(g):,} caixas")
    for v in ("AUSENTE", "PRESENTE_FORA_DO_PADRAO", "PERDIDO"):
        pp, lo, hi = wilson(c[v], len(g))
        print(f"  {v:26s} {c[v]:>6,}  {100 * pp:5.1f}%  [IC 95% {100 * lo:.1f}-{100 * hi:.1f}%]")
g = [x for x in saida if x["grupo"] == "amostra_sem_sinal"]
if g:
    k = sum(1 for x in g if x["veredito"] != "AUSENTE")
    pp, lo, hi = wilson(k, len(g))
    print(f"\nEstimativa nas {len(sem_sinal):,} caixas sem sinal: dado no texto em "
          f"{100 * pp:.1f}% [IC 95% {100 * lo:.1f}-{100 * hi:.1f}%], "
          f"~{round(pp * len(sem_sinal)):,} caixas")
print(f"\nrespostas descartadas (trecho fora do texto): "
      f"{sum(1 for x in saida if x['nota'] == 'trecho do LLM nao existe no texto'):,}")
print(f"Chamadas .............................. {cont['chamadas']:>8,}  (cache: {cont['do_cache']:,}, erros: {cont['erro']:,})")
print(f"CUSTO REAL ............................ US$ {custo:>7.2f}")
print(f"Tempo ................................. {(time.time() - t0) / 60:>8.1f} min")
print(f"\nGravado: {ART / 'deteccao_ausentes.jsonl'}")
