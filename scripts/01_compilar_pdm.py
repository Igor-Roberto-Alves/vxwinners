"""Compila o PDM da planilha para artefatos/pdm.json.

O padrao nunca e digitado no codigo: 229 atributos escritos a mao e bug garantido,
e se a banca mudar o PDM o pipeline continua valido.

Uso: python 01_compilar_pdm.py [dados/03_padrao_cadastro_PDM.xlsx] [artefatos/pdm.json]
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm  # noqa: E402

ENTRADA = Path(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "dados/03_padrao_cadastro_PDM.xlsx")
SAIDA = Path(sys.argv[2] if len(sys.argv) > 2 else RAIZ / "artefatos/pdm.json")

pdm = Pdm.de_xlsx(ENTRADA)
pdm.salvar(SAIDA)
e = pdm.estatisticas()

print("=" * 78)
print("PDM COMPILADO".center(78))
print("=" * 78)
print(f"Classes ............................... {e['classes']:>6}")
print(f"Atributos ............................. {e['atributos']:>6}")
print(f"  obrigatorios ........................ {e['obrigatorios']:>6}")
print(f"  de vocabulario fechado .............. {e['vocabulario_fechado']:>6}"
      f"  ({100 * e['vocabulario_fechado'] / e['atributos']:.1f}% resolvem por dicionario)")
print(f"Nomes de atributo distintos ........... {e['nomes_distintos']:>6}"
      f"  (espaco de rotulos do BERT: {1 + 2 * e['nomes_distintos']} tags BIO)")
print(f"Classes por REFERENCIA DO FABRICANTE .. {e['classes_por_referencia']:>6}"
      f"  (identidade = fabricante + part number)")
print(f"Unidades validas ...................... {', '.join(e['unidades_validas'])}")
print()
print(f"Gravado em {SAIDA}")

faltando = [c.id_pdm for c in pdm.classes.values() if not c.ncm]
if faltando:
    print(f"\nAviso: classes sem NCM resolvido: {', '.join(faltando)}")
