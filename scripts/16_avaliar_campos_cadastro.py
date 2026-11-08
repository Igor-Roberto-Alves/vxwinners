"""Avalia grupo, NCM, fabricante e referencia contra o gabarito do time (evaluate.py).

Monta o CSV que o evaluate.py espera a partir da saida do pipeline, com a
mesma regra do pipeline para fabricante e referencia (valor extraido; senao a
coluna do ERP), e o da base original, para comparar. Grava
avaliacao/resultado_campos_cadastro.md.

Uso: uv run --no-project --with pandas --with openpyxl python scripts/16_avaliar_campos_cadastro.py
"""

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento import Pdm, ler_base  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
p.add_argument("--saida", default=str(RAIZ / "avaliacao/resultado_campos_cadastro.md"))
a = p.parse_args()
ART = Path(a.artefatos)

pdm = Pdm.carregar(ART / "pdm.json")
base = {str(r["CODIGO_MATERIAL"]): r for r in ler_base(RAIZ / "dados/01_base_materiais.xlsx")}
san = {x["CODIGO_MATERIAL"]: x for x in csv.DictReader((ART / "saneado_base.csv").open(encoding="utf-8"))}
dec = {}
with (ART / "decisoes_base.jsonl").open(encoding="utf-8") as fh:
    for linha in fh:
        j = json.loads(linha)
        dec[j["codigo"]] = {x["atributo"]: x["valor"] for x in j["decisoes"]}

COLS = ["CODIGO_MATERIAL", "GRUPO_MERCADORIA", "NCM", "FABRICANTE", "REFERENCIA_FABRICANTE"]
tmp = Path(tempfile.mkdtemp())
with (tmp / "base_original.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(COLS)
    for c, r in base.items():
        w.writerow([c] + [str(r.get(k, "") or "") for k in COLS[1:]])
with (tmp / "pipeline.csv").open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(COLS)
    for c, r in base.items():
        s, d = san.get(c, {}), dec.get(c, {})
        classe = pdm.classes.get(s.get("ID_PDM", ""))
        w.writerow([c, classe.grupo if classe else "", s.get("NCM_PDM", ""),
                    d.get("FABRICANTE") or str(r.get("FABRICANTE", "") or ""),
                    d.get("REFERENCIA FABRICANTE") or str(r.get("REFERENCIA_FABRICANTE", "") or "")])

subprocess.run([sys.executable, str(RAIZ / "evaluate.py"), "--paths",
                str(tmp / "base_original.csv"), str(tmp / "pipeline.csv"),
                "--saida", a.saida], check=True)
