# -*- coding: utf-8 -*-
"""Publica para a interface o que o saneamento decidiu, codigo por codigo.

Uso:
  uv run --no-project --with pandas --with openpyxl python scripts/21_juncao_ncm.py \
      [--max-reformatados 400] [--saida artefatos/juncao_ncm.json]

O Radar ja mostrava os agregados ("R$ 30,24 mi consolidaveis em 1.991 grupos",
"1.104 NCM corrigidos"), mas a tela de Clusters trazia sete grupos escritos a mao
dentro do HTML e nao havia lugar nenhum para ver QUAIS codigos foram juntados e
QUAIS NCMs mudaram. Um numero agregado que ninguem consegue abrir nao da para
auditar, e e justo o que o tributario e o almoxarifado precisam conferir.

Este script le o plano de juncao e o saneado e escreve um JSON com as duas listas
completas, cada linha com o antes e o depois:

  grupos        1.991 grupos de identidade: o codigo que FICA, os que SAEM e o
                motivo (chave de identidade), com saldo, capital e centros
  ncm_trocado   NCM alterado item a item, separado por tipo de mudanca:
                  trocado      digitos diferentes -> decisao fiscal, exige aprovacao
                  preenchido   entrou vazio, derivado da classe PDM
                  reformatado  mesmos digitos, so a pontuacao (amostra por capital)

Entradas: artefatos/plano_juncao.csv, artefatos/saneado_base.csv,
dados/01_base_materiais.xlsx e, se existir, artefatos/radar.json (de onde vem a
precisao medida da juncao no gabarito, para a tela nao ter de repetir a conta).

Saida: artefatos/juncao_ncm.json e uma copia em frontend/dados/, que
./rodar.sh ja publica em /frontend/dados/juncao_ncm.json.
"""
import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefatos"


def digitos(s: str) -> str:
    return "".join(c for c in (s or "") if c.isdigit())


def tipo_mudanca(de: str, para: str) -> str:
    """Classifica a mudanca de NCM pelo que ela significa, nao pelo texto.

    A diferenca importa: 'reformatado' e cosmetico (84314929 -> 8431.49.29) e o
    tributario nao precisa olhar; 'trocado' muda a tributacao do item e nao pode
    sair daqui sem assinatura.
    """
    de, para = (de or "").strip(), (para or "").strip()
    if not para:
        return "sem_ncm" if not de else ""
    if not de:
        return "preenchido"
    if digitos(de) != digitos(para):
        return "trocado"
    return "reformatado" if de != para else ""


def le_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def enxuto(d: dict) -> dict:
    """Tira do JSON as chaves vazias: a tela le undefined como vazio do mesmo jeito.

    Sao 4.667 codigos publicados e boa parte dos campos nao se aplica (o codigo
    que fica nao tem USAR, a maioria nao tem motivo de unidade). Guardar o nome
    da chave para dizer "nada aqui" custava ~1,5 MB no arquivo que a tela baixa.

    O teste e campo a campo e nao por `in (...)`: em Python `0.0 == False`, e um
    `v not in ("", [], False)` apagaria silenciosamente todo estoque e capital
    zerados - exatamente os codigos parados que a tela precisa mostrar.
    """
    return {k: v for k, v in d.items()
            if not (v == "" or v == [] or v is False or v is None)}


def num_f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def precisao_do_radar():
    """A precisao da juncao medida no gabarito, se o Radar ja foi gerado.

    Vem de la em vez de ser recalculada para os dois numeros nao poderem
    divergir: a conta vive em scripts/20_radar.py, com o intervalo de Wilson.
    """
    arq = ART / "radar.json"
    if not arq.exists():
        return None
    try:
        radar = json.loads(arq.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    for e in radar.get("eficacia") or []:
        if "junção" in e.get("rotulo", ""):
            return {"valor": e.get("valor"), "detalhe": e.get("detalhe"),
                    "origem": e.get("origem")}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-reformatados", type=int, default=400,
                    help="quantos NCM so reformatados publicar (os de maior capital); "
                         "a contagem total vai sempre inteira")
    ap.add_argument("--saida", default=str(ART / "juncao_ncm.json"))
    a = ap.parse_args()

    import pandas as pd            # tardio: so a leitura do .xlsx precisa

    base = pd.read_excel(RAIZ / "dados/01_base_materiais.xlsx",
                         sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
    erp = {}
    for _, r in base.iterrows():
        cod = str(r["CODIGO_MATERIAL"]).strip()
        estoque, preco = num_f(r["ESTOQUE_ATUAL"]), num_f(r["PRECO_MEDIO_UNITARIO"])
        erp[cod] = {
            "descricao": r["DESCRICAO_LONGA"] or r["DESCRICAO_CURTA"],
            "curta": r["DESCRICAO_CURTA"],
            "unidade": r["UNIDADE_MEDIDA"], "ncm": r["NCM"],
            "grupo": r["GRUPO_MERCADORIA"], "fabricante": r["FABRICANTE"],
            "referencia": r["REFERENCIA_FABRICANTE"], "centro": r["CENTRO"],
            "status": r["STATUS"], "estoque": estoque, "preco": preco,
            "capital": round(estoque * preco, 2),
        }

    san = {r["CODIGO_MATERIAL"]: r for r in le_csv(ART / "saneado_base.csv")}
    plano = le_csv(ART / "plano_juncao.csv")

    # ---------------------------------------------------------------- grupos
    # O plano tem uma linha por codigo; a CHAVE (chave de identidade do PDM) e o
    # que diz que dois codigos sao a mesma peca. Em cada chave existe exatamente
    # um MANTER ATIVO - e esse o codigo que fica.
    por_chave = {}
    for r in plano:
        por_chave.setdefault(r["CHAVE"], []).append(r)

    grupos = []
    for chave, linhas in por_chave.items():
        mantido = next((r for r in linhas if r["ACAO"] == "MANTER ATIVO"), None)
        bloqueados = [r for r in linhas if r["ACAO"] == "BLOQUEADO"]
        if not mantido or not bloqueados:
            continue                                  # grupo de um codigo: nada a juntar

        codigos = []
        for r in [mantido] + sorted(bloqueados, key=lambda x: -erp.get(x["CODIGO"], {}).get("capital", 0)):
            cod = r["CODIGO"]
            e = erp.get(cod, {})
            s = san.get(cod, {})
            ncm_de = s.get("NCM_ORIGINAL", e.get("ncm", ""))
            ncm_para = s.get("NCM_PDM", "")
            codigos.append(enxuto({
                "codigo": cod,
                "acao": "mantem" if r["ACAO"] == "MANTER ATIVO" else "bloqueia",
                "usar": r["USAR"],
                "descricao": e.get("descricao", ""),
                "unidade_de": s.get("UNIDADE_ORIGINAL", e.get("unidade", "")),
                "unidade_para": s.get("UNIDADE_PDM", ""),
                "unidade_motivo": s.get("UNIDADE_MOTIVO", ""),
                "ncm_de": ncm_de, "ncm_para": ncm_para,
                "ncm_motivo": s.get("NCM_MOTIVO", ""),
                "ncm_mudanca": tipo_mudanca(ncm_de, ncm_para),
                "grupo_mercadoria": e.get("grupo", ""),
                "grupo_corrigido": s.get("GRUPO_CORRIGIDO", "0") not in ("", "0"),
                "fabricante": e.get("fabricante", ""),
                "referencia": e.get("referencia", ""),
                "centro": e.get("centro", ""), "status": e.get("status", ""),
                "estoque": e.get("estoque", 0.0), "preco": e.get("preco", 0.0),
                "capital": e.get("capital", 0.0),
            }))

        # o capital que a juncao libera e o dos codigos que SAEM: o saldo do
        # codigo que fica continua sendo estoque necessario, nao economia
        liberado = sum(c["capital"] for c in codigos if c["acao"] == "bloqueia")
        partes = chave.split("|")
        trocas_ncm = sum(1 for c in codigos
                         if c.get("ncm_mudanca") in ("trocado", "preenchido"))
        ncms = {digitos(c.get("ncm_de")) for c in codigos if c.get("ncm_de")}
        unidades = {c.get("unidade_de") for c in codigos if c.get("unidade_de")}

        grupos.append({
            "chave": chave,
            "id_pdm": partes[0] if partes else "",
            "titulo": " ".join(partes[1:]) or chave,
            "descricao_pdm": mantido["DESCRICAO_PDM"],
            "fica": mantido["CODIGO"],
            "saem": [c["codigo"] for c in codigos if c["acao"] == "bloqueia"],
            "n": len(codigos),
            "centros": sorted({c.get("centro") for c in codigos if c.get("centro")}),
            "estoque_consolidado": num_f(mantido["ESTOQUE_CONSOLIDADO"]),
            "unidade": codigos[0].get("unidade_para") or codigos[0].get("unidade_de", ""),
            "capital_liberado": round(liberado, 2),
            "capital_total": round(sum(c["capital"] for c in codigos), 2),
            "saem_com_saldo": sum(1 for c in codigos
                                  if c["acao"] == "bloqueia" and c["estoque"] > 0),
            "depende_de_llm": any(r.get("DEPENDE_DE_LLM") not in ("", "0", "False")
                                  for r in linhas),
            "llm_na_chave": sorted({r["LLM_NA_CHAVE"] for r in linhas
                                    if r.get("LLM_NA_CHAVE")}),
            # divergencias que a juncao expoe: o mesmo item cadastrado com NCM ou
            # unidade diferente em cada centro
            "ncm_divergente": len(ncms) > 1,
            "unidade_divergente": len(unidades) > 1,
            "ncm_trocas": trocas_ncm,
            "codigos": codigos,
        })

    grupos.sort(key=lambda g: -g["capital_liberado"])

    # ------------------------------------------------------------------- NCM
    em_grupo = {c["codigo"]: g["chave"] for g in grupos for c in g["codigos"]}
    trocado, preenchido, reformatado = [], [], []
    sem_ncm = inalterado = 0
    for cod, s in san.items():
        de, para = s.get("NCM_ORIGINAL", ""), s.get("NCM_PDM", "")
        t = tipo_mudanca(de, para)
        if t == "sem_ncm":
            sem_ncm += 1
            continue
        if not t:
            inalterado += 1
            continue
        e = erp.get(cod, {})
        linha = enxuto({
            "codigo": cod, "tipo": t,
            "de": de, "para": para, "motivo": s.get("NCM_MOTIVO", ""),
            "id_pdm": s.get("ID_PDM", ""),
            # a descricao do ERP, nao a DESCRICAO_CURTA_PDM: quem confere uma
            # troca de NCM precisa reconhecer o item como ele esta cadastrado, e
            # a curta do PDM corta no atributo pendente ("VALVULA ESFERA;
            # DIAMETRO NOMINAL:"), que nao identifica nada
            "descricao": e.get("curta") or s.get("DESCRICAO_CURTA_PDM", ""),
            "unidade": s.get("UNIDADE_PDM") or e.get("unidade", ""),
            "centro": e.get("centro", ""), "status": e.get("status", ""),
            "estoque": e.get("estoque", 0.0), "capital": e.get("capital", 0.0),
            "grupo_juncao": em_grupo.get(cod, ""),
        })
        (trocado if t == "trocado" else preenchido if t == "preenchido"
         else reformatado).append(linha)

    for lista in (trocado, preenchido, reformatado):
        lista.sort(key=lambda x: -x["capital"])
    n_reformatado = len(reformatado)
    reformatado = reformatado[:a.max_reformatados]

    capital_trocado = sum(x["capital"] for x in trocado)
    bloq = [r for r in plano if r["ACAO"] == "BLOQUEADO"]

    saida = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "fonte": {
            "juncao": "artefatos/plano_juncao.csv",
            "saneado": "artefatos/saneado_base.csv (NCM_ORIGINAL × NCM_PDM)",
            "capital": "dados/01_base_materiais.xlsx (ESTOQUE_ATUAL × PRECO_MEDIO_UNITARIO)",
        },
        "resumo": {
            "itens_na_base": len(san),
            "grupos": len(grupos),
            "codigos_no_plano": len(plano),
            "codigos_que_saem": len(bloq),
            "codigos_que_ficam": len(grupos),
            "capital_liberado": round(sum(g["capital_liberado"] for g in grupos), 2),
            "saem_com_saldo": sum(g["saem_com_saldo"] for g in grupos),
            "grupos_com_llm": sum(1 for g in grupos if g["depende_de_llm"]),
            "grupos_com_ncm_divergente": sum(1 for g in grupos if g["ncm_divergente"]),
            "grupos_com_unidade_divergente": sum(1 for g in grupos
                                                 if g["unidade_divergente"]),
            "grupos_por_tamanho": {str(k): sum(1 for g in grupos if g["n"] == k)
                                   for k in sorted({g["n"] for g in grupos})},
            "precisao_juncao": precisao_do_radar(),
            "ncm": {
                "trocado": len(trocado), "preenchido": len(preenchido),
                "reformatado": n_reformatado, "reformatado_publicado": len(reformatado),
                "sem_ncm": sem_ncm, "inalterado": inalterado,
                "capital_trocado": round(capital_trocado, 2),
                "trocado_em_grupo": sum(1 for x in trocado if x.get("grupo_juncao")),
            },
        },
        "grupos": grupos,
        "ncm_trocado": trocado + preenchido + reformatado,
    }

    arq = Path(a.saida)
    arq.write_text(json.dumps(saida, ensure_ascii=False) + "\n", encoding="utf-8")
    copia = RAIZ / "frontend/dados/juncao_ncm.json"
    copia.parent.mkdir(parents=True, exist_ok=True)
    copia.write_text(arq.read_text(encoding="utf-8"), encoding="utf-8")

    r = saida["resumo"]
    print(f"grupos de juncao: {r['grupos']} · {r['codigos_que_saem']} codigos a bloquear "
          f"({r['saem_com_saldo']} com saldo) · R$ {r['capital_liberado']:,.2f} liberados"
          .replace(",", "X").replace(".", ",").replace("X", "."))
    print(f"NCM: {r['ncm']['trocado']} trocados ({r['ncm']['trocado_em_grupo']} em grupo "
          f"de juncao), {r['ncm']['preenchido']} preenchidos, "
          f"{r['ncm']['reformatado']} reformatados "
          f"({r['ncm']['reformatado_publicado']} publicados), "
          f"{r['ncm']['sem_ncm']} continuam sem NCM")
    print(f"\n{arq}  ({arq.stat().st_size / 1e6:.1f} MB)")
    print(f"{copia}  (servido em /frontend/dados/juncao_ncm.json)")


if __name__ == "__main__":
    main()
