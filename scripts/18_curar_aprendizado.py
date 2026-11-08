# -*- coding: utf-8 -*-
"""Cura o dicionario aprendido: separa traducao de interpretacao, sem apagar nada.

Uso:
  uv run --no-project --with pandas --with openpyxl python scripts/18_curar_aprendizado.py \
      [--entrada artefatos/aprendizado.json] \
      [--saida artefatos/aprendizado_curado.json] \
      [--sugestoes artefatos/aprendido_sugestoes.jsonl] \
      [--no-lugar]

Por que existe: as travas de `Aprendizado` sao de ESCRITA e o arquivo sobrevive
ao codigo. As 487 entradas gravadas antes delas continuariam sendo aplicadas
para sempre - entre elas ACIONAMENTO 'VOLANTE' -> 'ALAVANCA', com 6
confirmacoes, que reescrevia uma palavra escrita no texto.

O que ele faz, em ordem:

  1. `revalidar(pdm)`  descarta o que e verificavel contra o enum (rotulo
                       interno, gemeo numerico, trecho que serve a dois valores).
                       Essa parte apaga, e ja existia.
  2. `curar(pdm)`      REBAIXA (revisar=True, marca +interpretacao) o que nao da
                       para provar que e traducao: termo que nao aponta um unico
                       valor do enum, ou que e valor legitimo do mesmo atributo
                       em classe irma. Nao apaga: 'BUTT WELD' -> SOLDA TOPO BW
                       esta certo, so precisa de carimbo humano.
  3. grava o dicionario curado e a fila de sugestao (uma linha por entrada
     rebaixada ou em revisao), mais o .py de candidatos a `sinonimos.py`.

Por padrao escreve em `aprendizado_curado.json` e NAO toca no arquivo em uso -
assim a execucao de comparacao (antes/depois) e possivel. Com `--no-lugar`
sobrescreve o arquivo original.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from saneamento.aprendizado import (Aprendizado, MARCA_INTERPRETACAO)  # noqa: E402
from saneamento.pdm import Pdm  # noqa: E402

ART = RAIZ / "artefatos"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entrada", default=str(ART / "aprendizado.json"))
    ap.add_argument("--saida", default=str(ART / "aprendizado_curado.json"))
    ap.add_argument("--sugestoes", default=str(ART / "aprendido_sugestoes.jsonl"))
    ap.add_argument("--candidatos", default=str(ART / "aprendido_candidatos_sinonimos.py"))
    ap.add_argument("--pdm", default=str(ART / "pdm.json"))
    ap.add_argument("--no-lugar", action="store_true",
                    help="sobrescreve o dicionario original em vez de gravar copia")
    a = ap.parse_args()

    pdm = Pdm.carregar(a.pdm)
    d = Aprendizado(a.entrada, pdm=pdm)
    antes = len(d.entradas)
    em_revisao_antes = sum(1 for e in d.entradas.values() if e.revisar)
    print(f"dicionario: {antes} entradas ({em_revisao_antes} ja em revisao, "
          f"{antes - em_revisao_antes} aplicadas como regra)")

    # 1) o que o enum reprova: sai
    fora = d.revalidar(pdm)
    if fora:
        print(f"\n--- descartadas pelo enum ({len(fora)}) ---")
        for e, motivo in fora[:12]:
            print(f"  {e.atributo:20} {e.termo!r:34} -> {e.valor!r:30} {motivo}")
        if len(fora) > 12:
            print(f"  (+{len(fora) - 12})")

    # 2) o que nao da para provar que e traducao: rebaixa
    rebaixadas = d.curar(pdm)
    print(f"\n--- rebaixadas de regra para sugestao ({len(rebaixadas)}) ---")
    for e, motivo in sorted(rebaixadas, key=lambda t: -t[0].confirmacoes)[:20]:
        print(f"  {e.atributo:20} {e.termo!r:34} -> {e.valor!r:30} "
              f"conf={e.confirmacoes:<3} {motivo}")
    if len(rebaixadas) > 20:
        print(f"  (+{len(rebaixadas) - 20})")
    print("  motivos:", dict(Counter(m for _, m in rebaixadas)))

    # 3) grava
    destino = Path(a.entrada if a.no_lugar else a.saida)
    d.caminho = destino
    d.salvar()
    sugestoes = [e for e in d.entradas.values() if e.revisar]
    with open(a.sugestoes, "w", encoding="utf-8") as f:
        for e in sorted(sugestoes, key=lambda x: (x.atributo, x.termo)):
            f.write(json.dumps({
                "atributo": e.atributo, "termo": e.termo, "valor_sugerido": e.valor,
                "classes": e.classes, "confirmacoes": e.confirmacoes,
                "origem": e.fonte,
                "tipo": ("interpretacao" if MARCA_INTERPRETACAO in e.fonte
                         else "pouca confirmacao"),
                "decisao_humana": "", "comentario": "",
            }, ensure_ascii=False) + "\n")
    n_cand = d.exportar_para_curar(a.candidatos)

    depois = len(d.entradas)
    regra = depois - len(sugestoes)
    print(f"\n{destino}: {depois} entradas -> {regra} aplicaveis como regra, "
          f"{len(sugestoes)} como sugestao")
    print(f"{a.sugestoes}: {len(sugestoes)} linhas para decisao humana")
    print(f"{a.candidatos}: {n_cand} candidatos a sinonimos.py")
    if not a.no_lugar:
        print("\nO dicionario em uso NAO foi alterado. Para valer na proxima "
              f"extracao:\n  cp {destino} {a.entrada}")


if __name__ == "__main__":
    main()
