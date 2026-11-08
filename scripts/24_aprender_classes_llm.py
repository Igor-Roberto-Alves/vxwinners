"""O LLM aprende a traduzir NOME DE CLASSE e grava a regra no dicionario.

O catalogo do fornecedor chega em ingles ('Generic | Ball valve | 1POL, 150#...').
O classificador procura o substantivo do PDM (VALVULA ESFERA), nao acha e conclui
FORA_DO_PDM: no gabarito de pedidos, 16 dos 16 erros de classe sao isso.

Este script pergunta ao LLM, uma vez por texto recusado, qual trecho nomeia o
item e qual sujeito do PDM ele e. A resposta vira REGRA (termo -> sujeito do
PDM) em artefatos/sujeito_aprendido.json, que o 04_extrair.py carrega: dai em
diante 'BALL VALVE' resolve por dicionario, de graca, em qualquer pedido futuro.

A traducao e da EXPRESSAO para o sujeito do PDM, nunca palavra a palavra:
'BALL' sozinho seria 'bola', que nao e classe nenhuma.

Travas - uma regra so e gravada se passar em todas:
  lista fechada  o sujeito tem que ser um dos sujeitos do PDM (ou NENHUMA,
                 para servico, cafe, movel - que ficam fora do PDM, certo)
  literal        o termo tem que estar escrito no texto
  reproduz       aplicada ao texto, a regra faz o classificador cair na classe
                 escolhida
  consistente    o mesmo termo nao pode receber sujeitos diferentes em pedidos
                 diferentes ('PIPE FITTING' pode ser TE ou NIPLE: vai para humano)
  nao colide     o termo nao aparece em nenhum dos 23.554 textos da base, para
                 a regra nao mexer em registro ja classificado

Uso:
  python 24_aprender_classes_llm.py --so-contar          # custo, sem chamar
  python 24_aprender_classes_llm.py                      # aprende com os pedidos
  python 24_aprender_classes_llm.py --excluir-gabarito   # so com pedidos fora do gabarito
"""

import argparse
import hashlib
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import sinonimos  # noqa: E402
from saneamento.dados import ler_base, ler_pedidos  # noqa: E402
from saneamento.llm import MODELO_PADRAO, PRECO, REGIAO_PADRAO  # noqa: E402
from saneamento.pdm import Pdm  # noqa: E402
from saneamento.regras import ClassificadorLexico  # noqa: E402
from saneamento.texto import juntar, normalizar  # noqa: E402

VERSAO_PROMPT = "classe-v1"

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--decisoes", default=None, help="padrao: <artefatos>/decisoes_pedidos.jsonl")
p.add_argument("--pedidos-arquivo", default=str(RAIZ / "dados/02_pedidos_cadastro.xlsx"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--modelo", default=MODELO_PADRAO)
p.add_argument("--saida", default=None, help="padrao: <artefatos>/sujeito_aprendido.json")
p.add_argument("--excluir-gabarito", action="store_true",
               help="nao aprende com os 120 pedidos de avaliacao/gold_classe_pedidos.csv")
p.add_argument("--so-contar", action="store_true")
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")
clf = ClassificadorLexico(pdm)
CACHE = ART / "cache_llm_classe"
CACHE.mkdir(exist_ok=True)

# Sujeito = substantivo + qualificador, exatamente como o classificador casa.
SUJEITOS: dict[str, str] = {}
for c in pdm.classes.values():
    for s in c.substantivos:
        for q in (c.qualificadores or [""]):
            SUJEITOS[f"{s} {q}".strip()] = c.id_pdm
NENHUMA = "NENHUMA"

# ------------------------------------------------------------ o que aprender
arq_dec = Path(a.decisoes or ART / "decisoes_pedidos.jsonl")
fora = {json.loads(l)["codigo"] for l in arq_dec.open(encoding="utf-8")
        if json.loads(l)["estado"] == "FORA_DO_PDM"}
excluir = set()
if a.excluir_gabarito:
    import csv
    with (RAIZ / "avaliacao/gold_classe_pedidos.csv").open(encoding="utf-8") as fh:
        excluir = {r["ID_PEDIDO"] for r in csv.DictReader(fh)}


def texto_do(reg: dict) -> str:
    # o MESMO texto que Pipeline.processar entrega ao classificador
    return juntar(*(str(reg.get(c, "") or "") for c in
                    ("DESCRICAO_LONGA", "DESCRICAO_CURTA", "FABRICANTE", "REFERENCIA_FABRICANTE")))


pedidos = {r["CODIGO_MATERIAL"]: r for r in ler_pedidos(a.pedidos_arquivo)}
por_texto: dict[str, list[str]] = defaultdict(list)
for cod in sorted(fora - excluir):
    por_texto[texto_do(pedidos[cod])].append(cod)

print(f"Pedidos FORA_DO_PDM ................... {len(fora)}"
      + (f"  ({len(fora & excluir)} do gabarito excluidos)" if excluir else ""))
print(f"Textos distintos a perguntar .......... {len(por_texto)}")

SISTEMA = """Voce classifica itens de pedidos de cadastro de materiais industriais \
contra uma lista FECHADA de sujeitos do padrao (PDM), em portugues.

O texto pode estar em ingles (linha de catalogo de fornecedor) ou em portugues.
1. Ache o trecho do texto que NOMEIA o tipo do item (ex.: 'Ball valve', \
'Hex head bolt', 'Oil seal'). Copie esse trecho EXATAMENTE como esta escrito, \
o mais curto possivel, sem fabricante, medida, material ou norma.
2. Escolha o sujeito do PDM que corresponde a esse tipo de item. Traduza a \
EXPRESSAO inteira pelo sentido tecnico, nunca palavra a palavra \
(Ball valve e VALVULA ESFERA, nao 'bola').
3. Se o item nao for nenhum sujeito da lista (servico, alimento, movel, \
informatica, uniforme), responda NENHUMA. Nunca force uma classe."""


def prompt(texto: str) -> str:
    lista = "\n".join(f"- {s}" for s in sorted(SUJEITOS))
    return f"Sujeitos do PDM:\n{lista}\n- {NENHUMA}\n\nTexto do pedido:\n{texto}"


FERRAMENTA = {"toolSpec": {
    "name": "registrar_classe",
    "description": "Registra o trecho que nomeia o item e o sujeito do PDM correspondente.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {
            "termo": {"type": "string", "description": "trecho literal do texto que nomeia o tipo do item"},
            "sujeito": {"type": "string", "enum": sorted(SUJEITOS) + [NENHUMA]},
            "motivo": {"type": "string", "description": "uma frase curta"},
        },
        "required": ["termo", "sujeito", "motivo"],
    }},
}}

p_ent, p_sai = next((v for k, v in PRECO.items() if k in a.modelo), PRECO["haiku-4-5"])
if a.so_contar:
    tok = sum((len(SISTEMA) + len(prompt(t))) / 3.5 + 120 for t in por_texto)
    custo = (tok * p_ent + len(por_texto) * 80 * p_sai) / 1e6
    print(f"Estimativa ............................ ~{tok:,.0f} tokens de entrada, US$ {custo:.3f}")
    sys.exit(0)

# ------------------------------------------------------------ perguntar
import boto3  # noqa: E402

cliente = boto3.client("bedrock-runtime", region_name=REGIAO_PADRAO)
uso = {"chamadas": 0, "cache": 0, "entrada": 0, "saida": 0}


def perguntar(texto: str) -> dict:
    chave = hashlib.sha256(json.dumps([a.modelo, VERSAO_PROMPT, texto]).encode()).hexdigest()[:24]
    arq = CACHE / f"{chave}.json"
    if arq.exists():
        uso["cache"] += 1
        return json.loads(arq.read_text(encoding="utf-8"))
    for tentativa in range(3):
        try:
            r = cliente.converse(
                modelId=a.modelo, system=[{"text": SISTEMA}],
                messages=[{"role": "user", "content": [{"text": prompt(texto)}]}],
                toolConfig={"tools": [FERRAMENTA], "toolChoice": {"tool": {"name": "registrar_classe"}}},
                inferenceConfig={"maxTokens": 300})
            break
        except Exception as e:  # throttling / rede
            if tentativa == 2:
                raise
            time.sleep(2 ** tentativa)
    uso["chamadas"] += 1
    uso["entrada"] += r["usage"]["inputTokens"]
    uso["saida"] += r["usage"]["outputTokens"]
    resp = next(b["toolUse"]["input"] for b in r["output"]["message"]["content"] if "toolUse" in b)
    arq.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    return resp


def classe_com(regras: dict[str, str], texto: str) -> str | None:
    antes = dict(sinonimos.SUJEITO_APRENDIDO)
    sinonimos.SUJEITO_APRENDIDO.clear()
    sinonimos.SUJEITO_APRENDIDO.update(regras)
    try:
        s = clf.classificar(texto, "")
        return s.classe.id_pdm if s.classe else None
    finally:
        sinonimos.SUJEITO_APRENDIDO.clear()
        sinonimos.SUJEITO_APRENDIDO.update(antes)


propostas: dict[str, list[dict]] = defaultdict(list)
nenhuma, descartes = [], []
for texto, cods in por_texto.items():
    r = perguntar(texto)
    termo, suj = normalizar(r.get("termo", "")), r.get("sujeito", "")
    item = {"termo": termo, "sujeito": suj, "origens": cods, "motivo": r.get("motivo", ""),
            "texto": texto[:160]}
    if suj == NENHUMA:
        nenhuma.append(item)
        continue
    if suj not in SUJEITOS:
        descartes.append({**item, "trava": "sujeito fora da lista do PDM"})
        continue
    if not termo or f" {termo} " not in f" {normalizar(texto)} ":
        descartes.append({**item, "trava": "termo nao esta escrito no texto"})
        continue
    if len(termo.split()) < 2 and len(termo) < 6:
        descartes.append({**item, "trava": "termo curto demais para virar regra"})
        continue
    if classe_com({termo: suj}, texto) != SUJEITOS[suj]:
        descartes.append({**item, "trava": "aplicada ao texto, a regra nao leva a classe escolhida"})
        continue
    propostas[termo].append(item)

# consistencia: um termo, um sujeito
regras: dict[str, dict] = {}
for termo, itens in propostas.items():
    sujs = {i["sujeito"] for i in itens}
    if len(sujs) > 1:
        descartes.append({"termo": termo, "sujeito": sorted(sujs),
                          "origens": [c for i in itens for c in i["origens"]],
                          "trava": "o mesmo termo recebeu sujeitos diferentes"})
        continue
    regras[termo] = {"para": itens[0]["sujeito"], "id_pdm": SUJEITOS[itens[0]["sujeito"]],
                     "origens": [c for i in itens for c in i["origens"]],
                     "motivo": itens[0]["motivo"], "exemplo": itens[0]["texto"]}

# nao colide com a base
print("Conferindo colisao com os 23.554 textos da base...")
textos_base = [f" {normalizar(texto_do(r))} " for r in ler_base(a.base)]
for termo in list(regras):
    hits = sum(1 for t in textos_base if f" {termo} " in t)
    if hits:
        descartes.append({"termo": termo, "sujeito": regras[termo]["para"],
                          "origens": regras[termo]["origens"],
                          "trava": f"aparece em {hits} textos da base"})
        del regras[termo]

custo = (uso["entrada"] * p_ent + uso["saida"] * p_sai) / 1e6
saida = Path(a.saida or ART / "sujeito_aprendido.json")
saida.write_text(json.dumps({
    "gerado_em": datetime.now().isoformat(timespec="seconds"),
    "modelo": a.modelo, "versao_prompt": VERSAO_PROMPT,
    "aprendido_de": str(arq_dec.relative_to(RAIZ)) if arq_dec.is_relative_to(RAIZ) else str(arq_dec),
    "excluiu_gabarito": a.excluir_gabarito,
    "uso": {**uso, "custo_usd": round(custo, 4)},
    "regras": regras, "fora_do_pdm_confirmado": nenhuma, "descartadas": descartes,
}, ensure_ascii=False, indent=1), encoding="utf-8")

print(f"\nLLM ({a.modelo}): {uso['chamadas']} chamadas, {uso['cache']} do cache, "
      f"{uso['entrada']:,} tokens entrada, {uso['saida']:,} saida  ->  US$ {custo:.4f}")
print(f"Regras gravadas ....................... {len(regras)}")
for t, r in sorted(regras.items()):
    print(f"   {t:34s} -> {r['para']:24s} {r['id_pdm']}  ({len(r['origens'])} pedidos)")
print(f"Fora do PDM confirmado (NENHUMA) ...... {len(nenhuma)}")
print(f"Descartadas pelas travas .............. {len(descartes)}")
for d in descartes:
    print(f"   {str(d['termo']):34s} -> {str(d['sujeito']):24s} {d['trava']}")
print(f"Gravado: {saida}")
