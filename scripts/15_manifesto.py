"""Grava artefatos/manifesto.json: de onde saiu cada numero desta execucao.

Commit do codigo, hash das entradas que mudam o resultado (PDM, dicionario
aprendido, modelo BERT, respostas do LLM ja gravadas) e as contagens finais.
Duas execucoes com o mesmo manifesto de entrada tem de dar as mesmas contagens.

Uso: python 15_manifesto.py [--artefatos artefatos]
"""

import argparse
import csv
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(RAIZ / "artefatos"))
a = p.parse_args()
ART = Path(a.artefatos)


def sha(caminho: Path) -> str | None:
    if not caminho.exists():
        return None
    h = hashlib.sha256()
    with caminho.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()[:16]


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


entradas = {
    "base": sha(RAIZ / "dados/01_base_materiais.xlsx"),
    "pdm_xlsx": sha(RAIZ / "dados/03_padrao_cadastro_PDM.xlsx"),
    "pdm_json": sha(ART / "pdm.json"),
    "aprendizado": sha(ART / "aprendizado.json"),
    "bert_config": sha(ART / "modelo_bert/config.json"),
    "bert_pesos": sha(ART / "modelo_bert/model.safetensors"),
    "desempate_llm": sha(ART / "desempate_llm.jsonl"),
    "deteccao_ausentes": sha(ART / "deteccao_ausentes.jsonl"),
}
saidas = {nome: sha(ART / nome) for nome in
          ("saneado_base.csv", "decisoes_base.jsonl", "plano_juncao.csv",
           "completacoes_sugeridas.jsonl")}

contagens = {}
san = ART / "saneado_base.csv"
if san.exists():
    linhas = list(csv.DictReader(san.open(encoding="utf-8")))
    estados = Counter(r["ESTADO"] for r in linhas)
    contagens = {
        "registros": len(linhas),
        "estados": dict(estados),
        "saneado_completo": sum(1 for r in linhas if r["ESTADO"] == "SANEADO" and r.get("COMPLETO") == "1"),
        "chaves_fechadas": sum(1 for r in linhas if r["CHAVE_IDENTIDADE"]),
        "registros_com_valor_do_llm": sum(1 for r in linhas if r.get("DECIDIDO_POR_LLM")),
        "registros_pendentes_por_llm": sum(1 for r in linhas if r.get("PENDENTE_POR_LLM")),
    }
plano = ART / "plano_juncao.csv"
if plano.exists():
    pl = list(csv.DictReader(plano.open(encoding="utf-8")))
    contagens["codigos_bloqueados"] = sum(1 for r in pl if r["ACAO"] == "BLOQUEADO")
    contagens["clusters"] = sum(1 for r in pl if r["ACAO"] == "MANTER ATIVO")
    contagens["clusters_que_dependem_do_llm"] = sum(
        1 for r in pl if r["ACAO"] == "MANTER ATIVO" and r.get("DEPENDE_DE_LLM") == "1")

manifesto = {
    "gerado_em": datetime.now().isoformat(timespec="seconds"),
    "commit": git("rev-parse", "--short", "HEAD"),
    "codigo_alterado_sem_commit": bool(git("status", "--porcelain", "src", "scripts")),
    "entradas": entradas,
    "saidas": saidas,
    "contagens": contagens,
}
(ART / "manifesto.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(manifesto["contagens"], ensure_ascii=False, indent=1))
print(f"\nGravado: {ART / 'manifesto.json'}")
