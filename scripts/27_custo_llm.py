"""Quanto o projeto gastou de LLM, e quanto gastaria se o LLM fizesse tudo.

A arquitetura do pipeline e uma aposta de custo: as camadas baratas (regras,
gazetteer, gramatica, dicionario, BERT) resolvem a maioria das caixas e o LLM
entra so no residuo que elas nao fecharam. Este script mede as duas pontas dessa
aposta com numeros reproduziveis:

  1. GASTO REAL - o que cada etapa de LLM custou, por execucao registrada.
  2. CONTRAFACTUAL - o que custaria a MESMA base se o LLM fosse a unica camada:
     uma chamada por registro para a classe, outra para os atributos, e os campos
     de identidade preenchidos por LLM em vez do vencedor barato do benchmark.

O contrafactual NAO e um palpite de regra de tres. Ele monta o prompt de verdade
(o mesmo SISTEMA, o mesmo _prompt e o mesmo schema de tool use que src/saneamento/llm.py
manda ao Bedrock) para cada um dos 23.554 registros, conta os caracteres e converte
em token por uma razao MEDIDA, nao assumida:

  as 37 chamadas da rodada artefatos/medicao_pedidos/3_bert_llm/ sao as unicas do
  projeto com tokens reais registrados em log (125.402 de entrada, 9.284 de saida,
  0 do cache). Reconstruir esses 37 prompts da a razao caractere/token deste
  formato de prompt. Ela fica em ~2,1 na entrada - o prompt e denso em numero,
  pontuacao e valor de enum, e a convencao de 3,5 caracteres por token dos scripts
  12 e 24 subestima o token em ~40%. (O script 11 erra por outro motivo: assume 220
  tokens fixos por termo, ignorando o proprio SISTEMA e o enum do atributo. Ver
  docs/16-custo-de-llm.md, secao 2.)

Uso:
  python scripts/27_custo_llm.py                  # tabela + artefatos/custo_llm.json
  python scripts/27_custo_llm.py --execucoes 12   # com N reexecucoes do pipeline
  python scripts/27_custo_llm.py --amostra 2000   # mais rapido, extrapola a amostra

Nao chama o Bedrock: nao gasta nada para dizer quanto se gastaria.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento.dados import ler_base, ler_pedidos  # noqa: E402
from saneamento.llm import SISTEMA, _ferramenta, _prompt  # noqa: E402
from saneamento.pdm import Pdm  # noqa: E402
from saneamento.texto import juntar  # noqa: E402

# USD por milhao de token (entrada, saida). Fonte: preenchimento/bedrock_util.py,
# que e a tabela usada no benchmark das 10 solucoes.
PRECOS = {
    "haiku-4-5": (1.00, 5.00),
    "sonnet-5": (2.00, 10.00),
    "opus-5": (5.00, 25.00),
    "fable-5": (10.00, 50.00),
}
MODELO_DO_PIPELINE = "haiku-4-5"

# (leitura de cache, escrita de cache) em USD por milhao de token, para o modelo do
# pipeline. Fonte: backend/app/llm/cliente.py. O cliente atual (boto3 converse, em
# src/saneamento/llm.py) NAO usa prompt caching - ver docs/00-estado-do-projeto.md,
# secao de pendencias. Entra aqui como sensibilidade: e o maior desconto que o
# contrafactual poderia receber, e ignora-lo inflaria a comparacao.
CACHE_LEITURA, CACHE_ESCRITA = 0.10, 1.25

# ---------------------------------------------------------------- gasto real
#
# Toda linha aqui e custo de chamada que JA aconteceu, com a fonte do numero.
# "producao" = etapa que roda no pipeline e cujo resultado esta nos artefatos;
# "pesquisa" = medicao que escolheu uma solucao e nao se repete por cliente.
#
# "perguntas" e nao "chamadas": o 08_preencher.py manda os itens de FABRICANTE em
# LOTE ("Itens:\n" + lista), entao ali 12.909 e o numero de campos perguntados, nao
# de requisicoes. Perguntas e a unidade comparavel com o contrafactual, que tambem
# poderia ser batelado.
MEDIDO = [
    # (etapa, natureza, perguntas, custo_usd, fonte)
    ("11 · canonizar termos que o PDM recusou", "producao", 939, 1.32,
     "docs/11-rodar-llm.md, primeira execucao"),
    ("10 · desempate de CONFLITO e AMBÍGUO", "producao", 1370, 5.53,
     "docs/11-rodar-llm.md, primeira execucao"),
    ("12 · detecção de dado genérico (caixas com sinal)", "producao", 1919, 2.92,
     "docs/12-dado-generico.md, secao 1"),
    ("12 · detecção de dado genérico (todas as caixas)", "producao", 6382, 9.83,
     "docs/12-dado-generico.md, secao 6"),
    ("08 · preencher FABRICANTE nos faltantes (Sonnet 5, em lote)", "producao", 12909, 20.45,
     "preenchimento/saida/resumo_preenchimento.json"),
    ("24 · aprender tradução de classe (catálogo em inglês)", "producao", 38, 0.13,
     "avaliacao/slides_camadas.html, 38 perguntas"),
    ("04 · os 520 pedidos com todas as camadas ligadas", "producao", 38, 0.17,
     "artefatos/medicao_pedidos/3_bert_llm/execucao.log"),
]

# ------------------------------------------------------------------ opcoes
p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--pedidos-arquivo", default=str(RAIZ / "dados/02_pedidos_cadastro.xlsx"))
p.add_argument("--benchmark", default=str(RAIZ / "preenchimento/benchmark.csv"))
p.add_argument("--execucoes", type=int, default=1,
               help="quantas vezes o pipeline inteiro seria reexecutado")
p.add_argument("--amostra", type=int, default=0,
               help="mede N registros e extrapola, em vez dos 23.554")
p.add_argument("--semente", type=int, default=20261108)
p.add_argument("--saida", default=None, help="padrao: <artefatos>/custo_llm.json")
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")


def texto_do(reg: dict) -> str:
    """O MESMO texto que Pipeline.processar entrega as camadas."""
    return juntar(*(str(reg.get(c, "") or "") for c in
                    ("DESCRICAO_LONGA", "DESCRICAO_CURTA", "FABRICANTE",
                     "REFERENCIA_FABRICANTE")))


def custo(tok_entrada: float, tok_saida: float, modelo: str = MODELO_DO_PIPELINE) -> float:
    p_ent, p_sai = PRECOS[modelo]
    return (tok_entrada * p_ent + tok_saida * p_sai) / 1e6


# ============================================================ 1. CALIBRACAO
#
# A unica rodada do projeto com tokens reais em log. Reconstruir os prompts dela
# converte caractere em token sem depender de tokenizador nem de chamada nova.
TOKENS_REAIS_ENTRADA, TOKENS_REAIS_SAIDA, CHAMADAS_REAIS = 125402, 9284, 37
ESCALAVEIS = {"CONFLITO", "AMBIGUO", "INCERTO", "INVALIDO"}

print("1. CALIBRACAO  (caractere -> token, medida em chamada real)")
print("   fonte: artefatos/medicao_pedidos/3_bert_llm/, 37 chamadas, 0 do cache")

pedidos = {r["CODIGO_MATERIAL"]: r for r in ler_pedidos(a.pedidos_arquivo)}
dec_ped = ART / "medicao_pedidos/3_bert_llm/decisoes_pedidos.jsonl"
cal_ent = cal_sai = cal_n = 0
for linha in dec_ped.open(encoding="utf-8"):
    d = json.loads(linha)
    if not d.get("escalado"):
        continue
    cal_n += 1
    classe = pdm.classes[d["id_pdm"]]
    texto = texto_do(pedidos[d["codigo"]])
    foco = [x["atributo"] for x in d["decisoes"]
            if str(x.get("fonte", "")).startswith("llm") or x.get("estado") in ESCALAVEIS]
    cal_ent += len(SISTEMA + _prompt(classe, texto, foco, ["caixas em duvida: x"])
                   + json.dumps(_ferramenta(classe), ensure_ascii=False))
    # A resposta real traz TODOS os atributos da classe, null incluido, mais as
    # evidencias dos que foram preenchidos.
    por = {x["atributo"]: x for x in d["decisoes"]}
    vals = {at.nome: (por[at.nome]["valor"]
                      if at.nome in por and str(por[at.nome].get("fonte", "")).startswith("llm")
                      else None)
            for at in sorted(classe.atributos, key=lambda x: x.ordem)}
    evid = {k: por[k].get("evidencia", "") for k, v in vals.items() if v and k in por}
    cal_sai += len(json.dumps({"atributos": vals, "evidencias": evid}, ensure_ascii=False))

if cal_n != CHAMADAS_REAIS:
    print(f"   ATENCAO: {cal_n} escalados reconstruidos, {CHAMADAS_REAIS} chamadas no log. "
          "A calibracao so vale se forem o mesmo conjunto.")

CT_ENTRADA = cal_ent / TOKENS_REAIS_ENTRADA
CT_SAIDA = cal_sai / TOKENS_REAIS_SAIDA
print(f"   entrada ... {cal_ent:>9,} caracteres / {TOKENS_REAIS_ENTRADA:>7,} tokens "
      f"= {CT_ENTRADA:.3f} car/token")
print(f"   saida ..... {cal_sai:>9,} caracteres / {TOKENS_REAIS_SAIDA:>7,} tokens "
      f"= {CT_SAIDA:.3f} car/token")
print(f"   (a convencao de 3,5 car/token dos scripts 12 e 24 conta "
      f"{1 - CT_ENTRADA / 3.5:.0%} menos token do que o real: o token verdadeiro e "
      f"{3.5 / CT_ENTRADA:.2f}x a estimativa deles)")
print()

# ============================================================ 2. GASTO REAL
print("2. GASTO REAL DE LLM  (perguntas que de fato foram feitas ao modelo)")
real_producao = sum(c for _, nat, _, c, _ in MEDIDO if nat == "producao")
real_chamadas = sum(n for _, nat, n, _, _ in MEDIDO if nat == "producao")
for etapa, nat, n, c, fonte in MEDIDO:
    print(f"   {etapa:<52} {n:>7,} perguntas  US$ {c:>7.2f}   {fonte}")
print(f"   {'TOTAL em producao':<52} {real_chamadas:>7,} perguntas  US$ {real_producao:>7.2f}")

# O benchmark das 10 solucoes x 4 campos: custo de PESQUISA, pago uma vez para
# escolher a solucao de cada campo. Nao se repete por cliente.
bench = list(csv.DictReader(Path(a.benchmark).open(encoding="utf-8")))
bench_usd = sum(float(r["custo_teste_usd"] or 0) for r in bench)
print(f"   {'+ benchmark das 10 solucoes x 4 campos (pesquisa)':<52} "
      f"{'':>7}           US$ {bench_usd:>7.2f}   preenchimento/benchmark.csv")
print(f"   {'TOTAL do projeto':<52} {'':>7}           US$ {real_producao + bench_usd:>7.2f}")
print()

# ================================================ 3. CONTRAFACTUAL: LLM EM TUDO
print("3. CONTRAFACTUAL: o LLM como unica camada, nos mesmos 23.554 registros")
registros = ler_base(a.base)
# classe de cada registro: a que o pipeline decidiu, lida da trilha de decisoes
classe_de = {}
for linha in (ART / "decisoes_base.jsonl").open(encoding="utf-8"):
    d = json.loads(linha)
    if d.get("id_pdm"):
        classe_de[d["codigo"]] = d["id_pdm"]

# valores que o pipeline produziu, para dimensionar a SAIDA que o LLM teria de escrever
valores_de: dict[str, dict] = {}
for linha in (ART / "decisoes_base.jsonl").open(encoding="utf-8"):
    d = json.loads(linha)
    valores_de[d["codigo"]] = {x["atributo"]: (x.get("valor"), x.get("evidencia", ""))
                               for x in d.get("decisoes", [])}

n_base = len(registros)
amostra = list(registros)
if a.amostra and a.amostra < n_base:
    random.Random(a.semente).shuffle(amostra)
    amostra = amostra[: a.amostra]
fator_base = n_base / len(amostra)
# atributos so existem para registro que casa uma classe do PDM; a classe, ao
# contrario, teria de ser perguntada para todos - inclusive os 37 FORA_DO_PDM.
alvos = [r for r in amostra if classe_de.get(str(r.get("CODIGO_MATERIAL", "")))]
n_total = sum(1 for r in registros if classe_de.get(str(r.get("CODIGO_MATERIAL", ""))))
fator = n_total / len(alvos)

# ---- 3a. atributos: uma chamada por registro, sem camada nenhuma antes
#
# Sem as camadas baratas nao existe "foco": nada foi escalado, porque nada foi
# lido. O prompt vai com a classe inteira e o modelo responde todas as caixas.
# O prompt tem duas partes, e a divisao importa para a sensibilidade de cache:
# o PREFIXO (SISTEMA + lista de atributos da classe + schema do tool use) depende
# so da classe e repete em todo registro dela; o SUFIXO e o texto do registro, que
# _prompt() poe no fim. Por isso prefixo = _prompt(classe, "", [], []).
at_ent = at_sai = 0
prefixo_chars: dict[str, int] = {}
at_prefixo = at_sufixo = 0
for r in alvos:
    cod = str(r.get("CODIGO_MATERIAL", ""))
    cid = classe_de[cod]
    classe = pdm.classes[cid]
    texto = texto_do(r)
    if cid not in prefixo_chars:
        prefixo_chars[cid] = len(SISTEMA + _prompt(classe, "", [], [])
                                 + json.dumps(_ferramenta(classe), ensure_ascii=False))
    at_prefixo += prefixo_chars[cid]
    at_sufixo += len(texto)
    at_ent += prefixo_chars[cid] + len(texto)
    vs = valores_de.get(cod, {})
    vals = {at.nome: (vs.get(at.nome, (None, ""))[0] or None)
            for at in sorted(classe.atributos, key=lambda x: x.ordem)}
    evid = {k: vs.get(k, (None, ""))[1] for k, v in vals.items() if v}
    at_sai += len(json.dumps({"atributos": vals, "evidencias": evid}, ensure_ascii=False))

at_tok_ent = at_ent * fator / CT_ENTRADA
at_tok_sai = at_sai * fator / CT_SAIDA
at_usd = custo(at_tok_ent, at_tok_sai)

# ---- 3b. classe: uma chamada por registro contra a lista fechada de sujeitos
#
# Mesmo formato do scripts/24_aprender_classes_llm.py, que e a unica medicao de
# classe por LLM que o projeto tem.
SUJEITOS = sorted({f"{s} {q}".strip()
                   for c in pdm.classes.values()
                   for s in c.substantivos
                   for q in (c.qualificadores or [""])})
SIS_CLASSE = ("Voce classifica itens de pedidos de cadastro de materiais industriais "
              "contra uma lista FECHADA de sujeitos do padrao (PDM), em portugues. "
              "Ache o trecho que NOMEIA o tipo do item, escolha o sujeito do PDM "
              "correspondente e responda NENHUMA se nao for nenhum deles.")
LISTA_SUJEITOS = "\n".join(f"- {s}" for s in SUJEITOS) + "\n- NENHUMA"
FERRAMENTA_CLASSE = len(json.dumps({"termo": "", "sujeito": SUJEITOS, "motivo": ""},
                                   ensure_ascii=False))
cl_prefixo_chars = len(SIS_CLASSE) + len(LISTA_SUJEITOS) + FERRAMENTA_CLASSE + 40
cl_ent = sum(cl_prefixo_chars + len(texto_do(r)) for r in amostra)
cl_sufixo = sum(len(texto_do(r)) for r in amostra)
# saida: termo + sujeito + uma frase de motivo. 80 caracteres e o tamanho medido
# nas 38 respostas de artefatos/sujeito_aprendido.json.
cl_sai = 80 * len(amostra)
cl_tok_ent = cl_ent * fator_base / CT_ENTRADA
cl_tok_sai = cl_sai * fator_base / CT_SAIDA
cl_usd = custo(cl_tok_ent, cl_tok_sai)

# ---- 3c. campos de identidade por LLM em todos os registros
#
# Aqui nao ha nada a estimar: o benchmark mediu os quatro campos com o MESMO
# modelo do pipeline (llm_fewshot_haiku), com tokens reais em preenchimento/benchmark.csv.
# Basta trazer o token por predicao para a base inteira. A pergunta e o teto - o
# campo todo, nao so o faltante - porque sem camada barata nao se sabe o que falta.
CAMPOS = ["FABRICANTE", "REFERENCIA_FABRICANTE", "NCM", "GRUPO_MERCADORIA"]
ident = []
for campo in CAMPOS:
    linhas = [r for r in bench if r["campo"] == campo]
    hk = next(r for r in linhas if r["solucao"] == "llm_fewshot_haiku")
    n_teste = float(hk["n_teste"])
    tok_ent = float(hk["tokens_in"]) / n_teste * n_base
    tok_sai = float(hk["tokens_out"]) / n_teste * n_base
    # a solucao que o projeto de fato aplicou: o top1 mais alto do campo
    aplicada = max(linhas, key=lambda r: float(r["top1"]))
    ident.append({
        "campo": campo, "solucao": hk["solucao"], "top1": float(hk["top1"]),
        "tokens_entrada": round(tok_ent), "tokens_saida": round(tok_sai),
        "usd_base_inteira": custo(tok_ent, tok_sai),
        "aplicada": aplicada["solucao"], "aplicada_top1": float(aplicada["top1"]),
        "aplicada_usd_por_1k": float(aplicada["usd_por_1k"]),
        "aplicada_usd_base_inteira": float(aplicada["usd_por_1k"]) * n_base / 1000,
    })
ident_usd = sum(x["usd_base_inteira"] for x in ident)
ident_tok = (sum(x["tokens_entrada"] for x in ident), sum(x["tokens_saida"] for x in ident))

print(f"   medido em {len(amostra):,} registros, extrapolado para {n_base:,} "
      f"(fator {fator_base:.3f}); atributos so nos {n_total:,} que casam classe do PDM")
print(f"   a · atributos, 1 chamada por registro .... "
      f"{at_tok_ent/1e6:>7.2f}M entrada + {at_tok_sai/1e6:>5.2f}M saida  US$ {at_usd:>8.2f}")
print(f"   b · classe, 1 chamada por registro ....... "
      f"{cl_tok_ent/1e6:>7.2f}M entrada + {cl_tok_sai/1e6:>5.2f}M saida  US$ {cl_usd:>8.2f}")
for x in ident:
    print(f"   c · {x['campo']:<22} .............. "
          f"{x['tokens_entrada']/1e6:>7.2f}M entrada + {x['tokens_saida']/1e6:>5.2f}M saida  "
          f"US$ {x['usd_base_inteira']:>8.2f}   "
          f"(top1 {x['top1']:.3f}; aplicado: {x['aplicada']} {x['aplicada_top1']:.3f} por "
          f"US$ {x['aplicada_usd_base_inteira']:.2f})")
total_contra = at_usd + cl_usd + ident_usd
chamadas_contra = n_total + n_base + len(CAMPOS) * n_base
print(f"   {'TOTAL, uma execucao, Haiku 4.5':<44}"
      f"{(at_tok_ent+cl_tok_ent+ident_tok[0])/1e6:>7.2f}M entrada + "
      f"{(at_tok_sai+cl_tok_sai+ident_tok[1])/1e6:>5.2f}M saida  US$ {total_contra:>8.2f}")
print(f"   perguntas: {chamadas_contra:,} contra {real_chamadas:,} que o projeto fez "
      f"({chamadas_contra/real_chamadas:.1f}x)")
# Afericao: o item (a) e a MESMA chamada do scripts/10_desempatar_llm.py, so que
# em todos os registros. O custo por registro dos dois tem de bater.
print(f"   afericao: US$ {at_usd / n_total:.5f} por registro em (a) contra "
      f"US$ {5.53 / 1370:.5f} medido no desempate real de 1.370 registros")
print()

# ======================================= 4. OS DOIS EIXOS QUE MULTIPLICAM
TOK_ENT = at_tok_ent + cl_tok_ent + ident_tok[0]
TOK_SAI = at_tok_sai + cl_tok_sai + ident_tok[1]
por_modelo = {m: custo(TOK_ENT, TOK_SAI, m) for m in PRECOS}

print("4. O QUE MULTIPLICA O CONTRAFACTUAL")
print("   a · modelo: os mesmos tokens no preco de tabela de cada um")
for modelo, t in por_modelo.items():
    marca = "  <- o que o pipeline usa" if modelo == MODELO_DO_PIPELINE else ""
    print(f"       {modelo:<10} US$ {t:>9.2f}   {t/max(total_contra, 1e-9):>5.1f}x{marca}")
print("   b · reexecucao: o cache em disco e o dicionario aprendido tornam a 2a")
print("       execucao gratuita; sem camada barata, cada execucao paga de novo")
for n in sorted({1, 2, a.execucoes}):
    print(f"       {n:>3} execucao(oes)  US$ {total_contra * n:>9.2f}"
          + ("   (as 2 rodadas do teste de determinismo)" if n == 2 else ""))

# ---- 4c. o desconto que o contrafactual teria: prompt caching
#
# O prefixo (SISTEMA + atributos da classe + schema) repete em todo registro da
# mesma classe. Com prompt caching e a execucao agrupada por classe, ele e escrito
# uma vez por classe e lido nas demais. Nao esta implementado (o cliente usa boto3
# converse sem cachePoint), e por isso entra como sensibilidade, nao como numero.
p_ent, p_sai = PRECOS[MODELO_DO_PIPELINE]
at_pref_tok = at_prefixo * fator / CT_ENTRADA
at_pref_tok_unico = sum(prefixo_chars.values()) / CT_ENTRADA
at_suf_tok = at_sufixo * fator / CT_ENTRADA
at_usd_cache = ((at_pref_tok_unico * CACHE_ESCRITA + at_pref_tok * CACHE_LEITURA
                 + at_suf_tok * p_ent) + at_tok_sai * p_sai) / 1e6
cl_pref_tok = cl_prefixo_chars * n_base / CT_ENTRADA
cl_suf_tok = cl_sufixo * fator_base / CT_ENTRADA
cl_usd_cache = ((cl_prefixo_chars / CT_ENTRADA * CACHE_ESCRITA
                 + cl_pref_tok * CACHE_LEITURA + cl_suf_tok * p_ent)
                + cl_tok_sai * p_sai) / 1e6
total_cache = at_usd_cache + cl_usd_cache + ident_usd
print("   c · prompt caching (desconto, nao implementado): o prefixo repete em")
print(f"       todo registro da classe - {at_pref_tok/1e6:.1f}M dos {at_tok_ent/1e6:.1f}M tokens")
print(f"       de (a) e {cl_pref_tok/1e6:.1f}M dos {cl_tok_ent/1e6:.1f}M de (b) sao prefixo")
print(f"       atributos US$ {at_usd:>8.2f} -> US$ {at_usd_cache:>8.2f}")
print(f"       classe    US$ {cl_usd:>8.2f} -> US$ {cl_usd_cache:>8.2f}")
print(f"       TOTAL     US$ {total_contra:>8.2f} -> US$ {total_cache:>8.2f}  "
      f"(campos de identidade sem modelar)")
print("       O desconto vale para os DOIS lados: as chamadas do residuo tem o mesmo")
print("       prefixo e cairiam na mesma proporcao. A razao entre os dois se mantem,")
print("       e por isso a comparacao honesta e sem cache dos dois lados.")
print()

# ===================================================== 5. A COMPARACAO FINAL
razao = total_contra / real_producao if real_producao else 0
print("5. A APOSTA DA ARQUITETURA")
# O custo e metade do argumento. A outra metade esta no benchmark: em 3 dos 4
# campos de identidade a solucao barata GANHA do LLM no top1. Pagar mais caro
# para acertar menos e o resultado medido, nao uma opiniao de arquitetura.
perdeu = [x for x in ident if x["aplicada_top1"] > x["top1"] and not x["aplicada"].startswith("llm_")]
print(f"   em {len(perdeu)} dos {len(ident)} campos de identidade a solucao barata GANHA do LLM:")
for x in perdeu:
    print(f"     {x['campo']:<22} {x['aplicada']:<12} {x['aplicada_top1']:.3f} por "
          f"US$ {x['aplicada_usd_base_inteira']:>6.2f}  contra  "
          f"llm_fewshot_haiku {x['top1']:.3f} por US$ {x['usd_base_inteira']:.2f}")
print(f"   gasto real em producao ................... US$ {real_producao:>9.2f}")
print(f"   LLM como unica camada, uma execucao ...... US$ {total_contra:>9.2f}   {razao:.1f}x mais")
# A comparacao direta: mesma tarefa dos dois lados (ler atributo, decidir classe).
# Do gasto real entram as etapas 11, 10, 12, 24 e 04; o resto e campo de identidade.
real_leitura = sum(c for e_, _, _, c, _ in MEDIDO if e_.split(" ")[0] != "08")
print(f"   so a leitura de atributos e classe ....... US$ {at_usd + cl_usd:>9.2f} contra "
      f"US$ {real_leitura:.2f} medidos ({(at_usd + cl_usd) / real_leitura:.1f}x) - "
      "a comparacao direta, mesma tarefa")
print(f"   economia por execucao .................... US$ {total_contra - real_producao:>9.2f}")
print(f"   por registro: US$ {real_producao / n_base:.5f} contra "
      f"US$ {total_contra / n_base:.5f}")
print()

saida = Path(a.saida or ART / "custo_llm.json")
saida.write_text(json.dumps({
    "gerado_por": "scripts/27_custo_llm.py",
    "modelo_do_pipeline": MODELO_DO_PIPELINE,
    "precos_usd_por_milhao_de_token": PRECOS,
    "calibracao": {
        "fonte": "artefatos/medicao_pedidos/3_bert_llm/execucao.log",
        "chamadas": cal_n, "tokens_entrada": TOKENS_REAIS_ENTRADA,
        "tokens_saida": TOKENS_REAIS_SAIDA,
        "caracteres_por_token_entrada": round(CT_ENTRADA, 4),
        "caracteres_por_token_saida": round(CT_SAIDA, 4),
    },
    "gasto_real": {
        "etapas": [{"etapa": e, "natureza": nat, "perguntas": n, "usd": c, "fonte": f}
                   for e, nat, n, c, f in MEDIDO],
        "usd_producao": round(real_producao, 2),
        "perguntas_producao": real_chamadas,
        "usd_benchmark_pesquisa": round(bench_usd, 2),
        "usd_total_projeto": round(real_producao + bench_usd, 2),
    },
    "contrafactual_llm_em_tudo": {
        "registros_da_base": n_base, "registros_com_classe_do_pdm": n_total,
        "amostra_medida": len(amostra),
        "atributos": {"tokens_entrada": round(at_tok_ent), "tokens_saida": round(at_tok_sai),
                      "usd": round(at_usd, 2)},
        "classe": {"tokens_entrada": round(cl_tok_ent), "tokens_saida": round(cl_tok_sai),
                   "usd": round(cl_usd, 2)},
        "campos_de_identidade": ident,
        "tokens_entrada": round(TOK_ENT), "tokens_saida": round(TOK_SAI),
        "perguntas": chamadas_contra,
        "usd_uma_execucao": round(total_contra, 2),
        "usd_por_modelo": {m: round(v, 2) for m, v in por_modelo.items()},
        "com_prompt_caching": {
            "implementado": False,
            "fonte_dos_precos": "backend/app/llm/cliente.py",
            "usd_leitura_cache": CACHE_LEITURA, "usd_escrita_cache": CACHE_ESCRITA,
            "atributos_usd": round(at_usd_cache, 2), "classe_usd": round(cl_usd_cache, 2),
            "usd_uma_execucao": round(total_cache, 2),
            "nota": "campos de identidade nao modelados; tambem cairiam",
        },
    },
    "razao": {
        "contrafactual_sobre_real": round(razao, 1),
        "leitura_usd_real": round(real_leitura, 2),
        "leitura_usd_contrafactual": round(at_usd + cl_usd, 2),
        "leitura_razao": round((at_usd + cl_usd) / real_leitura, 1),
        "usd_por_registro_real": round(real_producao / n_base, 5),
        "usd_por_registro_contrafactual": round(total_contra / n_base, 5),
    },
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"gravado em {saida}")
