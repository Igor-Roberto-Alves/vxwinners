"""Mostra quais caixas o PDM define para uma classe, e de onde isso vem.

As caixas NAO sao escolhidas pelo projeto: cada uma e uma linha da aba ATRIBUTOS
da planilha 03_padrao_cadastro_PDM.xlsx. PARAFUSO SEXTAVADO tem 7 caixas porque
a planilha tem 7 linhas com ID_PDM = PDM001.

Uso:
  python 00_ver_classe.py                      # lista as 44 classes e o nº de caixas
  python 00_ver_classe.py PDM001               # detalha uma classe pelo id
  python 00_ver_classe.py "parafuso sextavado" # ou pelo nome
  python 00_ver_classe.py --todas              # detalha todas
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm  # noqa: E402
from saneamento.caixas import LIVRE, NUMERICA, TEXTUAL, tipo_da_caixa  # noqa: E402
from saneamento.texto import normalizar  # noqa: E402

ART = RAIZ / "artefatos/pdm.json"
if not ART.exists():
    sys.exit(f"{ART} nao existe: rode scripts/01_compilar_pdm.py primeiro")
pdm = Pdm.carregar(ART)

args = [a for a in sys.argv[1:] if not a.startswith("--")]
todas = "--todas" in sys.argv


def detalhar(c):
    print("=" * 100)
    print(f"{c.id_pdm}  {c.rotulo()}")
    print("=" * 100)
    print(f"  grupo de mercadoria .... {c.grupo} ({pdm.grupos.get(c.grupo, '')})")
    print(f"  unidade padrao ......... {c.unidade}")
    print(f"  NCM .................... {', '.join(c.ncm) or '(condicional)'}")
    print(f"  identidade ............. {c.criterio}")
    if len(c.substantivos) > 1:
        print(f"  substantivos ({len(c.substantivos)}) ..... {', '.join(c.substantivos[:8])}"
              + (" ..." if len(c.substantivos) > 8 else ""))
    obrig = [a for a in c.atributos if a.obrigatorio]
    print(f"\n  CAIXAS: {len(c.atributos)}  "
          f"({len(obrig)} obrigatorias, {len(c.atributos) - len(obrig)} opcionais)")
    print(f"  -> cada uma e uma linha da aba ATRIBUTOS com ID_PDM = {c.id_pdm}\n")
    print(f"  {'#':<3} {'CAIXA':<24} {'TIPO':<9} {'OBR':<4} {'QUANDO':<22} VALORES / FORMATO")
    print("  " + "-" * 96)
    for a in sorted(c.atributos, key=lambda x: x.ordem):
        tipo = tipo_da_caixa(a)
        obr = "S" if a.obrigatorio else "-"
        quando = a.quando if normalizar(a.quando) != "SEMPRE" else ""
        if a.valores:
            detalhe = " | ".join(a.valores)
        else:
            detalhe = a.formato or "(texto livre)"
        print(f"  {a.ordem:<3} {a.nome:<24} {tipo:<9} {obr:<4} {quando[:22]:<22} {detalhe[:46]}")
        if len(detalhe) > 46:
            print(f"  {'':<3} {'':<24} {'':<9} {'':<4} {'':<22} {detalhe[46:140]}")
    conta = {t: sum(1 for a in c.atributos if tipo_da_caixa(a) == t)
             for t in (TEXTUAL, NUMERICA, LIVRE)}
    print(f"\n  por tipo: TEXTUAL {conta[TEXTUAL]} (casa por dicionario) | "
          f"NUMERICA {conta[NUMERICA]} (gramatica) | LIVRE {conta[LIVRE]} (precisa de BERT)")
    print()


if todas:
    for c in sorted(pdm.classes.values(), key=lambda x: x.id_pdm):
        detalhar(c)
elif args:
    alvo = normalizar(" ".join(args))
    achadas = [c for c in pdm.classes.values()
               if c.id_pdm == alvo or alvo in normalizar(c.rotulo())
               or any(alvo in normalizar(s) for s in c.substantivos)]
    if not achadas:
        sys.exit(f"nenhuma classe casa com {alvo!r}. Rode sem argumento para ver a lista.")
    for c in achadas:
        detalhar(c)
else:
    print("=" * 100)
    print("AS 44 CLASSES DO PDM E QUANTAS CAIXAS CADA UMA TEM".center(100))
    print("=" * 100)
    print("Fonte: dados/03_padrao_cadastro_PDM.xlsx, abas CLASSES e ATRIBUTOS\n")
    print(f"  {'ID':<8} {'SUJEITO':<36} {'GRUPO':<7} {'UN':<4} "
          f"{'CAIXAS':>7} {'OBRIG':>6} {'TEX':>4} {'NUM':>4} {'LIV':>4}")
    print("  " + "-" * 94)
    tot = Counter_tex = Counter_num = Counter_liv = tot_obrig = 0
    for c in sorted(pdm.classes.values(), key=lambda x: x.id_pdm):
        obrig = sum(1 for a in c.atributos if a.obrigatorio)
        tex = sum(1 for a in c.atributos if tipo_da_caixa(a) == TEXTUAL)
        num = sum(1 for a in c.atributos if tipo_da_caixa(a) == NUMERICA)
        liv = sum(1 for a in c.atributos if tipo_da_caixa(a) == LIVRE)
        rotulo = c.rotulo() if len(c.substantivos) == 1 else f"({len(c.substantivos)} substantivos)"
        print(f"  {c.id_pdm:<8} {rotulo[:36]:<36} {c.grupo:<7} {c.unidade:<4} "
              f"{len(c.atributos):>7} {obrig:>6} {tex:>4} {num:>4} {liv:>4}")
        tot += len(c.atributos); tot_obrig += obrig
        Counter_tex += tex; Counter_num += num; Counter_liv += liv
    print("  " + "-" * 94)
    print(f"  {'TOTAL':<8} {len(pdm.classes)} classes{'':<27} {'':<7} {'':<4} "
          f"{tot:>7} {tot_obrig:>6} {Counter_tex:>4} {Counter_num:>4} {Counter_liv:>4}")
    print(f"\n  Detalhar uma classe:  python {Path(__file__).name} PDM001")
    print(f"  Ou pelo nome:         python {Path(__file__).name} \"parafuso sextavado\"")
