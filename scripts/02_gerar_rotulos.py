"""Gera o dataset de treino do BERT a partir dos rotulos que a propria base ja traz.

59,9% dos registros tem pares explicitos "ATRIBUTO: VALOR" na descricao longa.
O nome do atributo e REMOVIDO do texto de treino: se ficasse, o modelo aprenderia
so a copiar o que vem depois dos dois pontos, e seria inutil nos registros
telegraficos, que sao o alvo.

Uso: python 02_gerar_rotulos.py [dados/01_base_materiais.xlsx] [artefatos/]
"""

import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import GeradorRotulos, Pdm, ler_base  # noqa: E402

BASE = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "dados/01_base_materiais.xlsx")
DESTINO = Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "artefatos")
DROPOUT = 0.15   # descarta atributo as vezes: ensina a deixar slot vazio

pdm = Pdm.carregar(DESTINO / "pdm.json")
registros = ler_base(BASE)
print(f"Base lida: {len(registros)} registros")

ger = GeradorRotulos(pdm)
exemplos = ger.gerar(registros, dropout=DROPOUT)
ger.salvar(exemplos, DESTINO / "rotulos.jsonl")

lidos = GeradorRotulos.ler(DESTINO / "rotulos.jsonl")
treino, val = GeradorRotulos.dividir(lidos, validacao=0.1)
GeradorRotulos.salvar([], DESTINO / "treino.jsonl")  # garante arquivo limpo
with (DESTINO / "treino.jsonl").open("w", encoding="utf-8") as fh:
    import json
    for e in treino:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")
with (DESTINO / "validacao.jsonl").open("w", encoding="utf-8") as fh:
    import json
    for e in val:
        fh.write(json.dumps(e, ensure_ascii=False) + "\n")

tags = Counter(r for e in exemplos for r in e.rotulos if r != "O")
atributos = Counter(r.split("-", 1)[1] for r in tags.elements())
por_classe = Counter(e.id_pdm for e in exemplos)

print()
print("=" * 78)
print("ROTULOS GRATUITOS (DISTANT SUPERVISION)".center(78))
print("=" * 78)
print(f"Registros auto-rotulados .............. {len(exemplos):>7,}"
      f"  ({100 * len(exemplos) / len(registros):.1f}% da base)")
print(f"Anotacoes atributo-valor .............. {sum(tags.values()):>7,}")
print(f"Atributos distintos cobertos .......... {len(atributos):>7}  de {len(pdm.nomes_atributos)}")
print(f"Tokens por exemplo (media) ............ {sum(len(e.tokens) for e in exemplos) / len(exemplos):>7.1f}")
print(f"Treino / validacao .................... {len(treino):>7,} / {len(val):,}  (split por codigo)")
print()
print("Top 15 atributos com mais exemplos:")
for nome, n in atributos.most_common(15):
    print(f"   {nome:34s} {n:>7,}")
print()
print("Classes com mais exemplos:")
for cid, n in por_classe.most_common(8):
    c = pdm.classes[cid]
    print(f"   {cid}  {c.rotulo():38s} {n:>6,}")

sem_exemplo = [n for n in pdm.nomes_atributos if n not in atributos]
if sem_exemplo:
    print(f"\nAtributos sem nenhum exemplo ({len(sem_exemplo)}): dependem de regra e LLM")
    print("   " + ", ".join(sem_exemplo[:20]) + (" ..." if len(sem_exemplo) > 20 else ""))
