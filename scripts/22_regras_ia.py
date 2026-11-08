# -*- coding: utf-8 -*-
"""Publica tudo o que a IA decidiu na base, com a regra, a origem e onde valeu.

Uso:
  uv run --no-project --with pandas --with openpyxl python scripts/22_regras_ia.py \
      [--saida artefatos/regras_ia.json] [--max-linhas-ia 4000]

O dicionario aprendido (`aprendizado.json`) e a camada mais barata e a mais
perigosa do pipeline: uma pergunta feita ao LLM uma vez vira regra e passa a
decidir sozinha em centenas de registros. 'ACO ZINCADO' -> ACO CARBONO ZINCADO
foi respondido uma vez e aplicado em 255 linhas. Se a resposta estiver errada,
estao erradas as 255 - e, antes desta tela, nao havia como saber quais eram.

Este script liga as tres pontas de cada regra:

  origem      a linha (codigo de material) em que o termo foi lido. Vem de
              Entrada.origens quando o dicionario foi gravado com procedencia;
              das evidencias de artefatos/desempate_llm.jsonl quando a regra
              nasceu de um desempate desta execucao; e, para as regras antigas,
              fica como `derivada` - a linha mais antiga em que o termo aparece
              no texto e o atributo foi resolvido pelo dicionario. A tela diz
              qual e qual: derivada e pista, nao registro.
  aplicacoes  TODAS as linhas em que a regra decidiu, com o valor que ela
              gravou e o capital do item. O casamento usa a mesma funcao do
              pipeline (termo mais longo primeiro, valor revalidado contra o
              enum), e nao uma reimplementacao.
  decisoes    o resto da interferencia de IA, por linha: desempate do LLM,
              deteccao de ausente, BERT e BERT de desempate.

Entradas: artefatos/aprendizado.json, aprendizado_curado.json (opcional),
decisoes_base.jsonl, desempate_llm.jsonl, saneado_base.csv, plano_juncao.csv e
dados/01_base_materiais.xlsx.

Saida: artefatos/regras_ia.json e uma copia em frontend/dados/, que o servidor
publica em /frontend/dados/regras_ia.json.
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefatos"
sys.path.insert(0, str(RAIZ / "src"))

from saneamento.aprendizado import Aprendizado          # noqa: E402
from saneamento.texto import normalizar                 # noqa: E402

# Fontes de decisao que sao interferencia de IA, e o que cada uma significa na
# tela. `aprendido` e a unica que tem regra por tras - as outras decidiram
# naquela linha so.
FONTES_IA = {
    "aprendido": "regra do dicionario aprendido",
    "llm": "desempate direto do LLM",
    "llm_deteccao": "deteccao de ausente pelo LLM",
    "bert": "recorte do BERT",
    "bert_desempata": "BERT desempatando a regra",
}


def num_f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def main():
    ap_cli = argparse.ArgumentParser()
    ap_cli.add_argument("--saida", default=str(ART / "regras_ia.json"))
    ap_cli.add_argument("--max-linhas-ia", type=int, default=4000,
                        help="quantas decisoes de IA sem regra publicar (as de maior capital)")
    a = ap_cli.parse_args()

    import pandas as pd            # tardio: so a leitura do .xlsx precisa

    # ------------------------------------------------------------------ base
    base = pd.read_excel(RAIZ / "dados/01_base_materiais.xlsx",
                         sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
    erp = {}
    for _, r in base.iterrows():
        cod = str(r["CODIGO_MATERIAL"]).strip()
        estoque, preco = num_f(r["ESTOQUE_ATUAL"]), num_f(r["PRECO_MEDIO_UNITARIO"])
        erp[cod] = {
            "curta": r["DESCRICAO_CURTA"],
            "texto": r["DESCRICAO_LONGA"] or r["DESCRICAO_CURTA"],
            "centro": r["CENTRO"], "status": r["STATUS"],
            "estoque": estoque, "capital": round(estoque * preco, 2),
            "criado": (r["DATA_CRIACAO"] or "")[:10],
        }

    san = {}
    with open(ART / "saneado_base.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            san[r["CODIGO_MATERIAL"]] = r

    def info(cod, **extra):
        e = erp.get(cod, {})
        return {"codigo": cod, "id_pdm": (san.get(cod) or {}).get("ID_PDM", ""),
                "descricao": e.get("curta", ""), "capital": e.get("capital", 0.0),
                "centro": e.get("centro", ""), "status": e.get("status", ""),
                "criado": e.get("criado", ""), **extra}

    # -------------------------------------------------------------- dicionario
    dic = Aprendizado(ART / "aprendizado.json")
    curado = {}
    arq_curado = ART / "aprendizado_curado.json"
    if arq_curado.exists():
        for item in json.loads(arq_curado.read_text(encoding="utf-8")).get("entradas", []):
            curado[f'{item["atributo"]}|{item["termo"]}'] = item

    def entrada_que_casou(atributo: str, valor: str, texto: str):
        """Qual entrada do dicionario produziu este valor neste texto.

        Mesma regra de Aprendizado.consultar/origem: percorre o indice do proprio
        objeto (termo mais longo primeiro) e exige que o termo apareca no texto
        normalizado. Reimplementar o casamento aqui daria uma atribuicao
        plausivel e errada em quem tem termo contido em outro ('INOX' dentro de
        'ACO INOX 316').
        """
        t = f" {normalizar(texto)} "
        alvo = normalizar(valor)
        for e in dic._por_atributo(atributo):
            if normalizar(e.valor) == alvo and f" {e.termo} " in t:
                return e
        return None

    # --------------------------------------------- origem vinda do desempate
    # Quando a regra nasceu de um desempate desta execucao, a linha esta
    # registrada: o artefato guarda codigo + atributo + valor + evidencia.
    origem_desempate = defaultdict(list)
    arq_des = ART / "desempate_llm.jsonl"
    if arq_des.exists():
        with open(arq_des, encoding="utf-8") as f:
            for linha in f:
                d = json.loads(linha)
                for x in d.get("aceitos", []):
                    termo = normalizar(x.get("evidencia") or "")
                    if termo:
                        origem_desempate[f'{x["atributo"]}|{termo}'].append(
                            (d["codigo"], x.get("valor")))

    # ------------------------------------------------- varredura das decisoes
    aplicacoes = defaultdict(list)       # chave da regra -> linhas onde valeu
    sem_ligacao = []                     # fonte 'aprendido' que nao casou regra
    linhas_ia = []                       # interferencia de IA sem regra por tras
    por_fonte = Counter()
    codigos_com_ia = set()

    with open(ART / "decisoes_base.jsonl", encoding="utf-8") as f:
        for linha in f:
            d = json.loads(linha)
            cod = d["codigo"]
            texto = (san.get(cod) or {}).get("DESCRICAO_ORIGINAL") or \
                erp.get(cod, {}).get("texto", "")
            for x in d["decisoes"]:
                fonte = x["fonte"]
                if fonte not in FONTES_IA or not x.get("valor"):
                    continue
                por_fonte[fonte] += 1
                codigos_com_ia.add(cod)
                if fonte == "aprendido":
                    e = entrada_que_casou(x["atributo"], x["valor"], texto)
                    if e is None:
                        sem_ligacao.append(info(cod, atributo=x["atributo"],
                                                valor=x["valor"]))
                        continue
                    aplicacoes[e.chave].append(info(
                        cod, atributo=x["atributo"], valor=x["valor"],
                        confianca=x.get("confianca"), estado=x.get("estado", "")))
                else:
                    linhas_ia.append(info(
                        cod, atributo=x["atributo"], valor=x["valor"], fonte=fonte,
                        evidencia=x.get("evidencia", ""), motivo=x.get("motivo", ""),
                        confianca=x.get("confianca"), estado=x.get("estado", "")))

    linhas_ia.sort(key=lambda x: -x["capital"])
    n_linhas_ia = len(linhas_ia)
    linhas_ia = linhas_ia[:a.max_linhas_ia]

    # ------------------------------------------------------------- as regras
    regras = []
    conta_origem = Counter()
    for chave, e in dic.entradas.items():
        usos = sorted(aplicacoes.get(chave, []), key=lambda x: -x["capital"])

        # 1. origem registrada pelo proprio dicionario (execucoes novas)
        origens, tipo = [], "ausente"
        if getattr(e, "origens", None):
            origens = [info(c, evidencia=e.termo) for c in e.origens]
            tipo = "registrada"
        # 2. origem no desempate desta execucao
        elif origem_desempate.get(chave):
            origens = [info(c, evidencia=e.termo, valor=v)
                       for c, v in origem_desempate[chave][:20]]
            tipo = "desempate"
        # 3. regra antiga: a linha mais antiga em que a regra vale hoje. E pista,
        #    nao registro, e vai rotulada assim na tela.
        elif usos:
            antigos = sorted(usos, key=lambda x: (x.get("criado") or "9999", x["codigo"]))
            origens = antigos[:3]
            tipo = "derivada"
        conta_origem[tipo] += 1

        c = curado.get(chave)
        regras.append({
            "id": chave, "atributo": e.atributo, "termo": e.termo, "valor": e.valor,
            "fonte": e.fonte, "confirmacoes": e.confirmacoes, "classes": e.classes,
            "revisar": e.revisar, "primeira_vez": e.primeira_vez,
            # o curador (scripts/18) rebaixa o que nao da para provar que e
            # traducao: quando ele discorda do arquivo em uso, a tela mostra
            "curado_rebaixou": bool(c and c.get("revisar") and not e.revisar),
            "curado_fonte": (c or {}).get("fonte", ""),
            "origem_tipo": tipo, "origens": origens, "n_origens": len(origens),
            "aplicacoes": usos, "n_aplicacoes": len(usos),
            "capital": round(sum(x["capital"] for x in usos), 2),
        })

    regras.sort(key=lambda r: (-r["n_aplicacoes"], -r["capital"]))

    plano = []
    arq_plano = ART / "plano_juncao.csv"
    if arq_plano.exists():
        with open(arq_plano, newline="", encoding="utf-8") as f:
            plano = list(csv.DictReader(f))
    llm_juncao = [r for r in plano if r.get("DEPENDE_DE_LLM") not in ("", "0", "False")]

    saida = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": {
            "dicionario": "artefatos/aprendizado.json",
            "curado": "artefatos/aprendizado_curado.json",
            "decisoes": "artefatos/decisoes_base.jsonl",
            "desempate": "artefatos/desempate_llm.jsonl",
            "capital": "dados/01_base_materiais.xlsx (ESTOQUE_ATUAL × PRECO_MEDIO_UNITARIO)",
        },
        "resumo": {
            "regras": len(regras),
            "regras_usadas": sum(1 for r in regras if r["n_aplicacoes"]),
            "regras_em_revisao": sum(1 for r in regras if r["revisar"]),
            "regras_uma_confirmacao": sum(1 for r in regras if r["confirmacoes"] == 1),
            "regras_com_conflito": sum(1 for r in regras if "conflito" in r["fonte"]),
            "regras_curado_rebaixou": sum(1 for r in regras if r["curado_rebaixou"]),
            "aplicacoes": sum(r["n_aplicacoes"] for r in regras),
            "aplicacoes_sem_ligacao": len(sem_ligacao),
            "capital_em_regras": round(sum(r["capital"] for r in regras), 2),
            "origem": dict(conta_origem),
            "linhas_com_ia": len(codigos_com_ia),
            "decisoes_por_fonte": {k: por_fonte.get(k, 0) for k in FONTES_IA},
            "rotulo_por_fonte": FONTES_IA,
            "decisoes_ia_sem_regra": n_linhas_ia,
            "decisoes_ia_publicadas": len(linhas_ia),
            "juncao_com_llm": {
                "codigos": len(llm_juncao),
                "chaves": len({r["CHAVE"] for r in llm_juncao}),
            },
        },
        "regras": regras,
        "aplicacoes_sem_ligacao": sorted(sem_ligacao, key=lambda x: -x["capital"])[:200],
        "decisoes_ia": linhas_ia,
    }

    arq = Path(a.saida)
    arq.write_text(json.dumps(saida, ensure_ascii=False) + "\n", encoding="utf-8")
    copia = RAIZ / "frontend/dados/regras_ia.json"
    copia.parent.mkdir(parents=True, exist_ok=True)
    copia.write_text(arq.read_text(encoding="utf-8"), encoding="utf-8")

    r = saida["resumo"]
    print(f"regras no dicionario: {r['regras']} ({r['regras_usadas']} usadas, "
          f"{r['regras_em_revisao']} em revisao, {r['regras_uma_confirmacao']} com "
          f"uma confirmacao so)")
    print(f"aplicacoes ligadas a uma regra: {r['aplicacoes']} "
          f"({r['aplicacoes_sem_ligacao']} sem ligacao) · "
          f"R$ {r['capital_em_regras']:,.2f} em estoque"
          .replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"origem da regra: " + " · ".join(f"{k}={v}" for k, v in
                                            sorted(conta_origem.items())))
    print(f"decisoes de IA sem regra: {r['decisoes_ia_sem_regra']} "
          f"({r['decisoes_ia_publicadas']} publicadas)")
    print(f"linhas da base com alguma interferencia de IA: {r['linhas_com_ia']}")
    print(f"\n{arq}  ({arq.stat().st_size / 1e6:.1f} MB)")
    print(f"{copia}  (servido em /frontend/dados/regras_ia.json)")


if __name__ == "__main__":
    main()
