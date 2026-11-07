"""Resolve por TERMO, nao por registro: canoniza com LLM e guarda no dicionario.

A diferenca de custo e de 65x, e ela vem de enxergar o problema certo.

    por registro                          por termo
    ------------                          ---------
    11.852 chamadas                       1.963 chamadas
    schema inteiro da classe (2.618 tok)  so a lista do atributo (~220 tok)
    US$ 44,60                             US$ 0,68
    resolve aquele registro               resolve TODOS que tem o termo

As 8.924 caixas obrigatorias em que o BERT recortou um trecho e o enum do PDM
recusou contem apenas 1.963 trechos DISTINTOS - repeticao de 4,5x. 'ZINC'
aparece 131 vezes, 'MANUAL' 190, 'MANOPLA' 105. Perguntar 131 vezes qual valor
corresponde a 'ZINC' e pagar 131 vezes pela mesma resposta.

Resolvido o termo, ele entra em `aprendizado.json` e passa a ser resolvido por
dicionario, de graca, em qualquer registro - inclusive nos futuros.

Uso:
  python 11_canonizar_termos.py --limite 50      # teste
  python 11_canonizar_termos.py                  # tudo, ~US$ 0,70
"""

import argparse
import json
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, Validador  # noqa: E402
from saneamento.aprendizado import Aprendizado  # noqa: E402
from saneamento.llm import MODELO_PADRAO  # noqa: E402
from saneamento.texto import normalizar  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--modelo", default=MODELO_PADRAO)
p.add_argument("--threads", type=int, default=16)
p.add_argument("--limite", type=int, default=0, help="so os N termos mais frequentes")
p.add_argument("--so-contar", action="store_true")
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")
validador = Validador(pdm)

# ------------------------------------------------------------------ levantamento

RX_MOTIVO = re.compile(r"BERT propos (.+?), recusado")

print("Levantando os trechos recusados pelo enum...")
freq: Counter = Counter()
exemplo_classe: dict[tuple[str, str], str] = {}
with (ART / "decisoes_base.jsonl").open(encoding="utf-8") as fh:
    for linha in fh:
        d = json.loads(linha)
        classe = pdm.classes.get(d["id_pdm"])
        if classe is None:
            continue
        por_nome = {x.nome: x for x in classe.atributos}
        for x in d["decisoes"]:
            if x["estado"] != "INVALIDO":
                continue
            at = por_nome.get(x["atributo"])
            # so vocabulario fechado: para caixa numerica o mapa termo->valor nao
            # generaliza (110MM nao significa 'diametro do eixo')
            if at is None or not at.fechado or not (at.obrigatorio and at.sempre):
                continue
            m = RX_MOTIVO.search(x.get("motivo") or "")
            termo = x.get("bert") or (m.group(1) if m else None)
            if not termo:
                continue
            chave = (x["atributo"], normalizar(termo))
            freq[chave] += 1
            exemplo_classe.setdefault(chave, d["id_pdm"])

ordenado = freq.most_common(a.limite or None)
ocorr = sum(freq.values())
cobre = sum(n for _, n in ordenado)
custo = len(ordenado) * (220 / 1e6 * 1.00 + 25 / 1e6 * 5.00)

print(f"ocorrencias ........................... {ocorr:>8,}")
print(f"termos distintos a resolver ........... {len(ordenado):>8,}")
print(f"cobrem ................................ {100 * cobre / max(ocorr, 1):>7.1f}% das ocorrencias")
print(f"custo estimado ........................ US$ {custo:>6.2f}")
print(f"modelo ................................ {a.modelo}")
if a.so_contar:
    sys.exit(0)

# ------------------------------------------------------------------ prompt curto

SISTEMA = """Voce padroniza valores de atributo de material industrial contra uma \
lista fechada.

Regras:
- Responda com EXATAMENTE um valor da lista, ou null.
- null quando o termo nao corresponde a nenhum valor, ou quando corresponde a \
MAIS DE UM (termo ambiguo nao se resolve por palpite).
- null quando o termo for nome de atributo, codigo de peca, ou outra coisa que \
nao seja um valor daquele atributo.
- Nao explique. Responda so o valor ou a palavra null."""


def ferramenta(atributo):
    return {"toolSpec": {
        "name": "responder",
        "description": f"Valor canonico de {atributo.nome}, ou null.",
        "inputSchema": {"json": {
            "type": "object",
            "properties": {"valor": {"type": ["string", "null"],
                                     "enum": atributo.valores + [None]}},
            "required": ["valor"],
            "additionalProperties": False,
        }},
    }}


import boto3  # noqa: E402

cliente = boto3.client("bedrock-runtime")
aprendizado = Aprendizado(ART / "aprendizado.json")
trava = threading.Lock()
cont = Counter()
decisoes_llm = []
t0 = time.time()
ACEITA_TEMP = not re.search(r"(sonnet-5|opus-5|opus-4-[6-9]|fable-5)", a.modelo)


def resolver(item):
    (attr, termo), n = item
    cid = exemplo_classe[(attr, termo)]
    atributo = next((x for x in pdm.classes[cid].atributos if x.nome == attr), None)
    if atributo is None:
        return None

    corpo = {
        "modelId": a.modelo,
        "system": [{"text": SISTEMA}],
        "messages": [{"role": "user", "content": [{"text":
            f"ATRIBUTO: {attr}\n"
            f"VALORES PERMITIDOS: {' | '.join(atributo.valores)}\n\n"
            f"O cadastro escreveu: {termo!r}\n\n"
            f"Qual valor da lista corresponde? Se nenhum, ou se mais de um "
            f"servir, responda null."}]}],
        "toolConfig": {"tools": [ferramenta(atributo)],
                       "toolChoice": {"tool": {"name": "responder"}}},
        "inferenceConfig": {"maxTokens": 120},
    }
    if ACEITA_TEMP:
        corpo["inferenceConfig"]["temperature"] = 0

    try:
        r = cliente.converse(**corpo)
    except Exception as e:                                   # noqa: BLE001
        with trava:
            cont["erro"] += 1
            cont["ultimo"] = str(e)[:150]
        return None

    uso = r.get("usage", {})
    valor = None
    for bloco in r["output"]["message"]["content"]:
        if "toolUse" in bloco:
            valor = (bloco["toolUse"]["input"] or {}).get("valor")

    with trava:
        cont["chamadas"] += 1
        cont["tok_ent"] += uso.get("inputTokens", 0)
        cont["tok_sai"] += uso.get("outputTokens", 0)
        if valor is None:
            cont["declinou"] += 1
            cont["ocorr_declinadas"] += n
        else:
            v = validador.valor(atributo, valor)
            if not v.ok:
                cont["recusado_validador"] += 1
            elif aprendizado.aprender(atributo, termo, v.valor, "llm", cid):
                cont["aprendido"] += 1
                cont["ocorr_resolvidas"] += n
                decisoes_llm.append({"atributo": attr, "termo": termo,
                                     "valor": v.valor, "ocorrencias": n})
            else:
                cont["rejeitado_dicionario"] += 1
        if cont["chamadas"] % 200 == 0:
            print(f"  {cont['chamadas']:>5,}/{len(ordenado):,}  "
                  f"aprendidos={cont['aprendido']:,}  declinou={cont['declinou']:,}  "
                  f"ocorrencias cobertas={cont['ocorr_resolvidas']:,}", flush=True)
    return valor


print(f"\nresolvendo {len(ordenado):,} termos com {a.threads} threads...\n")
with ThreadPoolExecutor(max_workers=a.threads) as ex:
    futuros = [ex.submit(resolver, x) for x in ordenado]
    for f in as_completed(futuros):
        f.result()

minutos = (time.time() - t0) / 60
aprendizado.salvar()
(ART / "termos_canonizados.jsonl").write_text(
    "\n".join(json.dumps(x, ensure_ascii=False) for x in
              sorted(decisoes_llm, key=lambda x: -x["ocorrencias"])) + "\n",
    encoding="utf-8")

real = cont["tok_ent"] / 1e6 * 1.00 + cont["tok_sai"] / 1e6 * 5.00
e = aprendizado.estatisticas()
print()
print("=" * 78)
print("CANONIZACAO POR TERMO".center(78))
print("=" * 78)
print(f"Chamadas ao Bedrock ................... {cont['chamadas']:>8,}")
print(f"  termos APRENDIDOS ................... {cont['aprendido']:>8,}")
print(f"  o LLM declinou (termo ambiguo/invalido) {cont['declinou']:>7,}")
print(f"  recusados pelo validador ............ {cont['recusado_validador']:>8,}")
print(f"  rejeitados pelo dicionario .......... {cont['rejeitado_dicionario']:>8,}")
print(f"  erros de chamada .................... {cont['erro']:>8,}")
print()
print(f"OCORRENCIAS cobertas .................. {cont['ocorr_resolvidas']:>8,}  "
      f"{100 * cont['ocorr_resolvidas'] / max(ocorr, 1):>5.1f}% das {ocorr:,}")
print(f"  declinadas (dado nao resolvivel) .... {cont['ocorr_declinadas']:>8,}")
print(f"Dicionario aprendido .................. {e['entradas']:>8,} termos")
print(f"Tokens ................................ {cont['tok_ent']:,} entrada / {cont['tok_sai']:,} saida")
print(f"CUSTO REAL ............................ US$ {real:>6.2f}")
print(f"Tempo ................................. {minutos:>8.1f} min")
if cont.get("ultimo"):
    print(f"ultimo erro: {cont['ultimo']}")
print(f"\nGravado: {ART / 'aprendizado.json'}")
print(f"Gravado: {ART / 'termos_canonizados.jsonl'}")
