"""Divide as linhas em caixas e mostra a grade resultante.

Uso:
  # so regras (literal + gramatica), sem embedding e sem BERT
  python 05_encaixotar.py --limite 500 --sem-embedding

  # com embedding canonizando as caixas textuais
  python 05_encaixotar.py --limite 500

  # com BERT recortando (exige artefatos/modelo_bert)
  python 05_encaixotar.py --limite 500 --com-bert

  # imprime a grade de codigos especificos
  python 05_encaixotar.py --ver 12711820,27827726,13634321
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, ler_base, ler_pedidos  # noqa: E402
from saneamento.caixas import ALTA, BAIXA, BANDA_LLM, EXATA, VAZIA  # noqa: E402
from saneamento.encaixotador import Encaixotador  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--base", default=str(RAIZ / "dados/01_base_materiais.xlsx"))
p.add_argument("--pedidos", action="store_true")
p.add_argument("--limite", type=int, default=500)
p.add_argument("--sem-embedding", action="store_true")
p.add_argument("--com-bert", action="store_true")
p.add_argument("--ver", default="", help="codigos separados por virgula")
p.add_argument("--exemplos", type=int, default=4)
a = p.parse_args()

ART = Path(a.artefatos)
pdm = Pdm.carregar(ART / "pdm.json")

canon = None
if not a.sem_embedding:
    from saneamento.embeddings import CanonizadorSemantico, Codificador

    cod = Codificador(cache=ART / "cache_emb.json")
    canon = CanonizadorSemantico(cod)

bert = None
if a.com_bert:
    from saneamento import ExtratorBert

    d = ART / "modelo_bert"
    if not d.exists():
        sys.exit(f"modelo nao encontrado em {d}: ver docs/03-treinar-bert.md")
    bert = ExtratorBert(pdm.nomes_atributos).carregar(d)

enc = Encaixotador(pdm, bert=bert, canonizador=canon)

registros = ler_pedidos(RAIZ / "dados/02_pedidos_cadastro.xlsx") if a.pedidos else ler_base(a.base)
if a.ver:
    alvos = {c.strip() for c in a.ver.split(",")}
    registros = [r for r in registros if str(r.get("CODIGO_MATERIAL")) in alvos]
elif a.limite:
    registros = registros[: a.limite]

print("=" * 90)
print("ENCAIXOTAMENTO".center(90))
print("=" * 90)
print(f"Registros ............................. {len(registros):,}")
print(f"Camada literal + gramatica ............ ativa")
print(f"Camada embedding ...................... {'ativa' if canon else 'DESLIGADA'}")
print(f"Camada BERT (recorte) ................. {'ativa' if bert else 'DESLIGADA'}")
print()

grades = [enc.encaixotar(r) for r in registros]
com_classe = [g for g in grades if g.id_pdm]

# ------------------------------------------------------------------ exemplos

LARG = 22


def mostrar(g):
    print("-" * 90)
    print(f"  codigo {g.codigo}   classe {g.id_pdm}   sujeito: {g.substantivo} {g.qualificador}".rstrip())
    print(f"  linha crua: {g.texto[:300]}")
    if g.grupo_corrigido:
        print("  (grupo de mercadoria corrigido: nenhuma classe do grupo original casava)")
    print()
    print(f"  {'CAIXA':<{LARG}} {'TIPO':<9} {'VALOR':<30} {'BANDA':<10} FONTE")
    for c in g.caixas.values():
        marca = "*" if c.obrigatoria else " "
        valor = c.valor if c.valor else ("<vazia>" if not c.bruto else f"? {c.bruto[:26]}")
        print(f" {marca}{c.atributo:<{LARG}} {c.tipo:<9} {str(valor)[:30]:<30} {c.banda:<10} {c.fonte}")
        if c.motivo:
            print(f"   {'':<{LARG}} {'':<9} -> {c.motivo[:70]}")
    print(f"\n  completude dos obrigatorios: {g.completude:.0%}"
          f"   tudo_bate: {g.tudo_bate}"
          f"   caixas para LLM: {g.para_llm or '-'}")
    if g.pendentes:
        print(f"  pendentes: {', '.join(g.pendentes)}")
    if g.sobra:
        print(f"  sobra (texto fora de toda caixa): {g.sobra[:120]}")
    print()


if a.ver:
    for g in grades:
        mostrar(g)
else:
    # um exemplo de cada situacao, para a grade ser julgada de verdade
    vistos = set()
    for rotulo, cond in (
        ("TUDO BATE (nao chama LLM)", lambda g: g.tudo_bate),
        ("TEM CAIXA NA BANDA DO LLM", lambda g: bool(g.para_llm)),
        ("TEM PENDENCIA (dado ausente)", lambda g: bool(g.pendentes) and not g.para_llm),
        ("SOBRA GRANDE (recorte perdeu texto)", lambda g: len(g.sobra) > 40),
    ):
        achados = [g for g in com_classe if cond(g) and g.codigo not in vistos]
        if not achados:
            continue
        print("#" * 90)
        print(f"### {rotulo}")
        for g in achados[: a.exemplos]:
            vistos.add(g.codigo)
            mostrar(g)

# ------------------------------------------------------------------ agregado

c = enc.contadores
total_caixas = c.caixas
obrig = [cx for g in com_classe for cx in g.obrigatorias]

print("#" * 90)
print("AGREGADO".center(90))
print("#" * 90)
print(f"Linhas encaixotadas ................... {len(com_classe):>8,}  "
      f"({100 * len(com_classe) / max(len(grades), 1):.1f}%)")
print(f"Linhas sem classe do PDM .............. {c.sem_classe:>8,}")
print(f"Caixas criadas ........................ {total_caixas:>8,}")
print(f"  obrigatorias ........................ {len(obrig):>8,}")
print()
print(f"Linhas em que TUDO BATE (sem LLM) ..... {c.tudo_bate:>8,}  "
      f"({100 * c.tudo_bate / max(len(com_classe), 1):.1f}%)")
print(f"Linhas com caixa na banda do LLM ...... {c.com_banda_llm:>8,}  "
      f"({100 * c.com_banda_llm / max(len(com_classe), 1):.1f}%)")

print("\nCaixas obrigatorias por banda:")
bandas = Counter(cx.banda for cx in obrig)
for b in (EXATA, ALTA, BANDA_LLM, BAIXA, VAZIA):
    n = bandas.get(b, 0)
    print(f"   {b:<12} {n:>8,}  {100 * n / max(len(obrig), 1):>5.1f}%")

print("\nCaixas obrigatorias cheias, por fonte:")
fontes = Counter(cx.fonte for cx in obrig if cx.cheia)
for f, n in fontes.most_common():
    print(f"   {f:<14} {n:>8,}  {100 * n / max(len(obrig), 1):>5.1f}%")

print("\nPor tipo de caixa (obrigatorias):")
for tipo in ("TEXTUAL", "NUMERICA", "LIVRE"):
    doTipo = [cx for cx in obrig if cx.tipo == tipo]
    if not doTipo:
        continue
    cheias = sum(1 for cx in doTipo if cx.cheia)
    print(f"   {tipo:<9} {len(doTipo):>7,} caixas   {100 * cheias / len(doTipo):>5.1f}% cheias")

compl = [g.completude for g in com_classe]
if compl:
    print(f"\nCompletude media dos obrigatorios ..... {sum(compl) / len(compl):.3f}")

if canon:
    cod.salvar_cache()

saida = ART / ("caixas_pedidos.jsonl" if a.pedidos else "caixas_base.jsonl")
with saida.open("w", encoding="utf-8") as fh:
    for g in grades:
        fh.write(json.dumps(g.como_dict(), ensure_ascii=False) + "\n")
print(f"\nGravado: {saida}")
