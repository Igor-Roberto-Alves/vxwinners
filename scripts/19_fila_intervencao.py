# -*- coding: utf-8 -*-
"""Monta a fila de intervencao humana da interface, com sugestao por campo.

Uso:
  uv run --no-project --with pandas --with openpyxl python scripts/19_fila_intervencao.py \
      [--limite 500] [--saida artefatos/fila_intervencao.json]

Por que existe: o pipeline ja sabe (a) onde a caixa ficou vazia, (b) se o dado
esta AUSENTE do texto ou PERDIDO dentro dele, e (c) quais valores do PDM sao
provaveis, com probabilidade e suporte. Isso estava em tres .jsonl que ninguem
abre. Aqui vira uma fila ordenada por capital em risco, com a acao certa para
cada campo, que a interface consome.

Entradas
--------
  artefatos/saneado_base.csv            estado, completude, pendencias, conflitos
  artefatos/deteccao_ausentes.jsonl     AUSENTE | PERDIDO | PRESENTE_FORA_DO_PADRAO
  artefatos/completacoes_sugeridas.jsonl  candidatos (valor, probabilidade), banda, pergunta
  dados/01_base_materiais.xlsx          estoque e preco medio, para priorizar

Classificacao da acao, que e o que a interface mostra como botao:

  um_clique   o valor esta decidido e e so confirmar. Dois casos: PERDIDO (o
              texto traz o valor e o pipeline nao leu - 'SECAO 4MM' que e 4MM2),
              e candidato unico ou provavel acima de 90%.
  escolher    ha dois ou mais candidatos plausiveis (bandas INCLINADA e ABERTA):
              a pessoa decide, com a probabilidade e o trecho do texto a vista.
  sem_pista   o texto traz algo fora do padrao e nenhum candidato se sustenta:
              precisa de quem conhece o item.
  enriquecer  o texto nao traz o dado (AUSENTE). Nao e trabalho de leitura:
              sai da fila de intervencao e vai para fonte externa.

Saida: artefatos/fila_intervencao.json e uma copia em frontend/dados/, que o
servidor do time ja publica em /frontend/dados/fila_intervencao.json.
"""
import argparse
import csv
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefatos"

LIMIAR_PROVAVEL = 0.90          # acima disso, candidato provavel e um clique
RE_VALIDO = re.compile(r"valido:\s*(.+)$", re.I)


def acao_de(veredito: str, banda: str, candidatos: list) -> str:
    if veredito == "AUSENTE":
        return "enriquecer"
    if veredito == "PERDIDO":
        return "um_clique"
    if banda in ("UNICO",):
        return "um_clique"
    if banda == "PROVAVEL":
        topo = candidatos[0][1] if candidatos else 0
        return "um_clique" if topo >= LIMIAR_PROVAVEL else "escolher"
    if banda in ("INCLINADA", "ABERTA"):
        return "escolher"
    return "sem_pista"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limite", type=int, default=500,
                    help="itens exportados (os de maior capital); o resumo conta todos")
    ap.add_argument("--saida", default=str(ART / "fila_intervencao.json"))
    a = ap.parse_args()

    # --- estado e pendencia de cada item -----------------------------------
    san = {}
    with open(ART / "saneado_base.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            san[r["CODIGO_MATERIAL"]] = r
    if not san:
        sys.exit("saneado_base.csv vazio: rode a extracao antes")

    # --- capital em risco, para ordenar a fila ------------------------------
    # pandas importado aqui, nao no topo: a classificacao da acao (`acao_de`) e a
    # parte com regra de negocio e e testada no .venv do projeto, que nao tem
    # pandas - so a leitura do .xlsx precisa dele.
    import pandas as pd

    base = pd.read_excel(RAIZ / "dados/01_base_materiais.xlsx",
                         sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
    cap, texto = {}, {}
    for _, r in base.iterrows():
        cod = str(r["CODIGO_MATERIAL"]).strip()
        try:
            est = float(r["ESTOQUE_ATUAL"] or 0)
            pre = float(r["PRECO_MEDIO_UNITARIO"] or 0)
        except ValueError:
            est = pre = 0.0
        cap[cod] = est * pre
        texto[cod] = (r["DESCRICAO_LONGA"] or r["DESCRICAO_CURTA"] or "").strip()

    # --- campos que precisam de decisao ------------------------------------
    campos = defaultdict(dict)        # codigo -> atributo -> dict
    for linha in open(ART / "deteccao_ausentes.jsonl", encoding="utf-8"):
        if not linha.strip():
            continue
        r = json.loads(linha)
        cod, atr = str(r["codigo"]), r["atributo"]
        nota = r.get("nota") or ""
        m = RE_VALIDO.search(nota)
        campos[cod][atr] = {
            "atributo": atr, "veredito": r["veredito"], "trecho": r.get("trecho") or "",
            "nota": nota, "sinal": r.get("sinal") or "",
            "candidatos": [[m.group(1).strip(), 1.0]] if m else [],
            "banda": "", "suporte": 0, "pergunta": "",
        }

    for linha in open(ART / "completacoes_sugeridas.jsonl", encoding="utf-8"):
        if not linha.strip():
            continue
        r = json.loads(linha)
        cod, atr = str(r["codigo"]), r["atributo"]
        c = campos[cod].get(atr) or {"atributo": atr, "veredito": r["veredito"],
                                     "trecho": "", "nota": "", "sinal": ""}
        cands = [[v, round(float(p), 3)] for v, p in (r.get("candidatos") or [])]
        c.update({"trecho": r.get("trecho") or c.get("trecho", ""),
                  "nota": r.get("nota") or c.get("nota", ""),
                  "candidatos": cands or c.get("candidatos", []),
                  "banda": r.get("banda") or "", "suporte": r.get("suporte") or 0,
                  "pergunta": r.get("pergunta") or ""})
        campos[cod][atr] = c

    # --- monta os itens -----------------------------------------------------
    itens, resumo_acao, resumo_banda, resumo_campo = [], Counter(), Counter(), Counter()
    capital_fila = 0.0
    for cod, atrs in campos.items():
        s = san.get(cod)
        if s is None:
            continue
        lista = []
        for atr, c in sorted(atrs.items()):
            c["acao"] = acao_de(c["veredito"], c["banda"], c["candidatos"])
            resumo_acao[c["acao"]] += 1
            if c["banda"]:
                resumo_banda[c["banda"]] += 1
            if c["acao"] != "enriquecer":
                resumo_campo[atr] += 1
            lista.append(c)
        acionaveis = [c for c in lista if c["acao"] != "enriquecer"]
        if not acionaveis:
            continue
        capital_fila += cap.get(cod, 0.0)
        itens.append({
            "codigo": cod, "id_pdm": s["ID_PDM"], "estado": s["ESTADO"],
            "substantivo": s["SUBSTANTIVO"], "qualificador": s["QUALIFICADOR"],
            "completude": float(s["COMPLETUDE"] or 0),
            "conflitos": s["CONFLITOS"], "discordancia": float(s["DISCORDANCIA"] or 0),
            "escalado_llm": s["ESCALADO_LLM"] not in ("", "0"),
            "texto": texto.get(cod, s["DESCRICAO_ORIGINAL"]),
            "descricao_pdm": s["DESCRICAO_PDM"],
            "capital": round(cap.get(cod, 0.0), 2),
            "campos": lista,
            "n_um_clique": sum(1 for c in lista if c["acao"] == "um_clique"),
            "n_escolher": sum(1 for c in lista if c["acao"] == "escolher"),
            "n_sem_pista": sum(1 for c in lista if c["acao"] == "sem_pista"),
            "n_enriquecer": sum(1 for c in lista if c["acao"] == "enriquecer"),
        })

    itens.sort(key=lambda i: (-i["capital"], i["codigo"]))
    exportados = itens[:a.limite]

    saida = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": {
            "saneado": "artefatos/saneado_base.csv",
            "deteccao": "artefatos/deteccao_ausentes.jsonl",
            "sugestoes": "artefatos/completacoes_sugeridas.jsonl",
            "capital": "dados/01_base_materiais.xlsx (estoque x preco medio)",
        },
        "limiar_provavel": LIMIAR_PROVAVEL,
        "resumo": {
            "itens_na_fila": len(itens),
            "itens_exportados": len(exportados),
            "campos_por_acao": dict(resumo_acao),
            "campos_por_banda": dict(resumo_banda),
            "campos_mais_frequentes": resumo_campo.most_common(10),
            "capital_na_fila": round(capital_fila, 2),
            "capital_exportado": round(sum(i["capital"] for i in exportados), 2),
            "itens_em_revisao_humana": sum(1 for s in san.values()
                                           if s["ESTADO"] == "REVISAO_HUMANA"),
            "itens_na_base": len(san),
        },
        "itens": exportados,
    }
    Path(a.saida).write_text(json.dumps(saida, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    copia = RAIZ / "frontend/dados/fila_intervencao.json"
    copia.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.saida, copia)

    r = saida["resumo"]
    print(f"itens na fila: {r['itens_na_fila']:,} "
          f"(exportados {r['itens_exportados']:,}, os de maior capital)")
    print(f"campos por acao: {r['campos_por_acao']}")
    print(f"capital na fila: R$ {r['capital_na_fila']:,.2f}")
    print(f"em revisao humana (conflito): {r['itens_em_revisao_humana']}")
    print(f"\n{a.saida}")
    print(f"{copia}  (servido em /frontend/dados/fila_intervencao.json)")


if __name__ == "__main__":
    main()
