# -*- coding: utf-8 -*-
"""Alimenta o Radar da interface com os dados que o projeto realmente tem.

Uso:
  uv run --no-project --with pandas --with openpyxl python scripts/20_radar.py \
      [--taxa-oportunidade 0.30] [--saida artefatos/radar.json]

A tela do Radar nasceu com numeros fixos no HTML e com selo de procedencia
(medido | estimado | premissa). Os selos estavam certos como convencao e errados
como fato: "Capital ja consolidado R$ 4,7 mi — medido" nao tinha medicao nenhuma
atras, porque nenhuma unificacao foi executada. Aqui cada numero sai de um
arquivo e carrega:

  valor     o numero
  fonte     medido    sai de um artefato do pipeline ou de um gabarito
            estimado  calculo sobre a base, com a premissa dita
            premissa  parametro ajustavel, nao medido
  detalhe   a frase que aparece embaixo
  origem    o arquivo de onde veio

Quando nao existe medicao, o campo vai com `fonte: "nao_medido"` e a tela diz
isso, em vez de mostrar um numero bonito.

Entradas: artefatos/plano_juncao.csv, saneado_base.csv, fila_intervencao.json,
avaliacao/gold_juncao.csv, resultado_caracteristicas.md, concordancia_*.json,
determinismo.txt, dados/01_base_materiais.xlsx.
"""
import argparse
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ART = RAIZ / "artefatos"
AVA = RAIZ / "avaliacao"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return p, max(0.0, centro - meia), min(1.0, centro + meia)


def num(v) -> str:
    return f"{v:,.0f}".replace(",", ".")


def milhoes(v: float) -> str:
    return f"R$ {v / 1e6:,.2f} mi".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(p: float, casas: int = 1) -> str:
    return f"{p * 100:.{casas}f}%".replace(".", ",")


def le_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def dado(valor, fonte, detalhe, origem, rotulo=None, tipo="dinheiro"):
    """tipo diz como a tela formata: 'dinheiro' em R$ mi, 'inteiro' com separador.

    Sem isso a interface adivinhava pela magnitude e 1.104 NCMs corrigidos
    apareciam como "R$ 0,00 mi".
    """
    return {"valor": valor, "fonte": fonte, "detalhe": detalhe, "origem": origem,
            "tipo": tipo, **({"rotulo": rotulo} if rotulo else {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taxa-oportunidade", type=float, default=0.30,
                    help="custo de capital ao ano, usado no custo de oportunidade")
    ap.add_argument("--saida", default=str(ART / "radar.json"))
    a = ap.parse_args()

    import pandas as pd            # tardio: so a leitura do .xlsx precisa

    # --- estoque total da base ---------------------------------------------
    base = pd.read_excel(RAIZ / "dados/01_base_materiais.xlsx",
                         sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
    estoque = 0.0
    for _, r in base.iterrows():
        try:
            estoque += float(r["ESTOQUE_ATUAL"] or 0) * float(r["PRECO_MEDIO_UNITARIO"] or 0)
        except ValueError:
            pass
    itens_base = len(base)

    # --- junção: o capital que da para consolidar ---------------------------
    plano = le_csv(ART / "plano_juncao.csv")
    bloq = [r for r in plano if r["ACAO"] == "BLOQUEADO"]
    manter = [r for r in plano if r["ACAO"] == "MANTER ATIVO"]

    # O capital redundante e o estoque dos codigos que SAEM (BLOQUEADO), e ele
    # vem da base: a coluna ESTOQUE_CONSOLIDADO do plano fica na linha que
    # PERMANECE (e o saldo que o codigo mantido passa a ter), nao na que sai.
    # Mesma definicao do avaliacao/30_valor_financeiro.py, para o Radar e o
    # relatorio financeiro nao darem numeros diferentes para a mesma coisa.
    capital_de = {}
    for _, r in base.iterrows():
        try:
            capital_de[str(r["CODIGO_MATERIAL"]).strip()] = (
                float(r["ESTOQUE_ATUAL"] or 0) * float(r["PRECO_MEDIO_UNITARIO"] or 0))
        except ValueError:
            capital_de[str(r["CODIGO_MATERIAL"]).strip()] = 0.0

    def val(r):
        return capital_de.get(str(r["CODIGO"]).strip(), 0.0)

    capital_bloq = sum(val(r) for r in bloq)
    dep_llm = sum(val(r) for r in bloq if r.get("DEPENDE_DE_LLM") not in ("", "0", "False"))

    # precisao da juncao medida no gabarito, para ajustar o capital
    jun = le_csv(AVA / "gold_juncao.csv")
    san = {r["CODIGO_MATERIAL"]: r for r in le_csv(ART / "saneado_base.csv")}
    pares = {r["par_id"]: r for r in le_csv(AVA / "pares_juncao_candidatos.csv")}
    vp = fp = 0
    for g in jun:
        p = pares.get(g["CODIGO_MATERIAL"])
        if not p or g["y_gold"] == "INDETERMINADO":
            continue
        k1 = (san.get(p["codigo_1"], {}).get("CHAVE_IDENTIDADE") or "").strip()
        k2 = (san.get(p["codigo_2"], {}).get("CHAVE_IDENTIDADE") or "").strip()
        if k1 and k1 == k2:
            vp += g["y_gold"] == "MESMO_ITEM"
            fp += g["y_gold"] == "ITENS_DIFERENTES"
    prec, lo, hi = wilson(vp, vp + fp)

    # --- estado da base -----------------------------------------------------
    linhas = list(san.values())
    n = len(linhas)
    saneado = sum(1 for r in linhas if r["ESTADO"] == "SANEADO")
    completo = sum(1 for r in linhas if r["COMPLETO"] in ("1", "1.0", "True"))
    com_chave = sum(1 for r in linhas if r["CHAVE_IDENTIDADE"])
    rev = sum(1 for r in linhas if r["ESTADO"] == "REVISAO_HUMANA")
    uni_corr = sum(1 for r in linhas if r["UNIDADE_PDM"] and r["UNIDADE_ORIGINAL"]
                   and r["UNIDADE_PDM"] != r["UNIDADE_ORIGINAL"])
    ncm_corr = sum(1 for r in linhas if r["NCM_PDM"] and r["NCM_ORIGINAL"]
                   and r["NCM_PDM"].replace(".", "") != r["NCM_ORIGINAL"].replace(".", ""))
    ncm_vazio = sum(1 for r in linhas if not r["NCM_ORIGINAL"])
    grupo_corr = sum(1 for r in linhas if r["GRUPO_CORRIGIDO"] not in ("", "0"))

    # --- fila de intervencao ------------------------------------------------
    fila = {}
    arq_fila = ART / "fila_intervencao.json"
    if arq_fila.exists():
        fila = json.loads(arq_fila.read_text(encoding="utf-8"))["resumo"]

    # --- qualidade medida pelo gabarito -------------------------------------
    md = (AVA / "resultado_caracteristicas.md").read_text(encoding="utf-8")
    m_res = re.search(r"^\|\s*geral\s*\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|"
                      r"([^|]+)\|([^|]+)\|", md, re.M)
    m_cls = re.search(r"Acerto de classe: \*\*(\d+)/(\d+)\*\*", md)
    m_rec = re.search(r"^\|\s*recall\s*\|([^|]+)\|", md, re.M)
    travas = {}
    if (AVA / "efeito_travas.json").exists():
        travas = json.loads((AVA / "efeito_travas.json").read_text(encoding="utf-8"))
    det = ""
    if (AVA / "determinismo.txt").exists():
        det = (AVA / "determinismo.txt").read_text(encoding="utf-8").strip()

    taxa = a.taxa_oportunidade
    radar = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        # Contagens estruturadas, nao so dentro da frase do `detalhe`: a casca da
        # interface (menu lateral, titulo da home) precisa do numero cru, e este
        # JSON ja e baixado na home para os KPI. Sem isto, o unico jeito seria
        # puxar o juncao_ncm.json de 4,5 MB para mostrar uma contagem.
        "base": {"itens": itens_base, "estoque": round(estoque, 2),
                 "estoque_texto": milhoes(estoque),
                 "grupos": len(manter), "codigos_que_saem": len(bloq)},
        "hero": {
            "consolidavel": dado(
                round(capital_bloq, 2), "medido",
                f"{pct(capital_bloq / estoque)} dos {milhoes(estoque)} em estoque · "
                f"{num(len(bloq))} códigos a bloquear em {num(len(manter))} grupos · "
                f"precisão da junção {pct(prec)} [{pct(lo, 0)}–{pct(hi, 0)}] no gabarito",
                "artefatos/plano_juncao.csv + avaliacao/gold_juncao.csv",
                "Capital consolidável"),
            "consolidado": dado(
                0.0, "medido",
                f"nenhuma unificação executada no ERP: o plano está pronto, com "
                f"{num(len(bloq))} códigos a bloquear e {num(len(manter))} a manter",
                "artefatos/plano_juncao.csv (nenhum log de unificação)",
                "Capital já consolidado"),
            "oportunidade": dado(
                round(capital_bloq * taxa, 2), "premissa",
                f"{milhoes(capital_bloq)} × {pct(taxa, 0)} a.a. — a taxa é parâmetro, "
                "não medição",
                f"premissa: custo de capital {pct(taxa, 0)} a.a.",
                "Custo de oportunidade do capital parado"),
            "fila": dado(
                fila.get("capital_na_fila", 0.0), "medido",
                f"{num(fila.get('itens_na_fila', 0))} itens esperando decisão humana · "
                f"{num((fila.get('campos_por_acao') or {}).get('um_clique', 0))} campos "
                "a um clique",
                "artefatos/fila_intervencao.json",
                "Capital na fila de intervenção"),
            "ncm": dado(
                ncm_corr, "medido",
                f"{num(ncm_vazio)} itens entraram sem NCM · {num(uni_corr)} unidades e "
                f"{num(grupo_corr)} grupos de mercadoria também corrigidos",
                "artefatos/saneado_base.csv (NCM_ORIGINAL × NCM_PDM)",
                "NCM corrigido contra a tabela vigente", tipo="inteiro"),
        },
        "saude": [
            {"rotulo": "descrição no padrão PDM", "valor": pct(saneado / n),
             "detalhe": f"{num(saneado)} de {num(n)}", "fonte": "medido"},
            {"rotulo": "cadastro completo", "valor": pct(completo / n),
             "detalhe": f"{num(completo)} sem atributo pendente", "fonte": "medido"},
            {"rotulo": "com chave de identidade", "valor": pct(com_chave / n),
             "detalhe": f"{num(n - com_chave)} fora da comparação de duplicidade",
             "fonte": "medido"},
            {"rotulo": "em revisão humana", "valor": num(rev),
             "detalhe": "conflito entre camadas", "fonte": "medido"},
            {"rotulo": "unidade corrigida", "valor": num(uni_corr),
             "detalhe": "metro onde era peça, peça onde era par", "fonte": "medido"},
            {"rotulo": "grupo de mercadoria corrigido", "valor": num(grupo_corr),
             "detalhe": "retentor cadastrado em tubos", "fonte": "medido"},
        ],
        "eficacia": [
            {"rotulo": "precisão das características", "valor": (m_res.group(3).strip()
                                                                 if m_res else "—"),
             "detalhe": f"{m_res.group(2).strip()} rótulos de gabarito" if m_res else "",
             "fonte": "medido", "origem": "avaliacao/gold_caracteristicas.csv"},
            {"rotulo": "cobertura", "valor": (m_res.group(4).strip() if m_res else "—"),
             "detalhe": "dos valores que o texto traz", "fonte": "medido",
             "origem": "avaliacao/resultado_caracteristicas.md"},
            {"rotulo": "taxa de invenção", "valor": (m_res.group(7).strip() if m_res else "—"),
             # o numero do .md e o dos artefatos ATUAIS, que ainda sao de antes
             # das travas: o pipeline nao foi reexecutado. O 7% e projecao por
             # replay da camada que mudou, e e assim que tem de aparecer.
             "detalhe": (f"cai para {travas['metricas_depois']['invencao']} com as travas do "
                         "dicionário aprendido — projeção por replay, o pipeline ainda não "
                         "foi reexecutado" if travas else ""),
             "fonte": "medido", "origem": "avaliacao/resultado_caracteristicas.md"},
            {"rotulo": "acerto de classe",
             "valor": (pct(int(m_cls.group(1)) / int(m_cls.group(2))) if m_cls else "—"),
             "detalhe": f"{m_cls.group(1)} de {m_cls.group(2)} itens" if m_cls else "",
             "fonte": "medido", "origem": "avaliacao/gold_classe.csv"},
            {"rotulo": "junção: precisão e recall",
             "valor": f"{pct(prec)} / {m_rec.group(1).split('[')[0].strip() if m_rec else '—'}",
             "detalhe": f"{vp} junções certas, {fp} errada(s) em {vp + fp} pares decidíveis",
             "fonte": "medido", "origem": "avaliacao/gold_juncao.csv"},
            {"rotulo": "determinismo", "valor": "idêntico" if det else "—",
             "detalhe": det[:120], "fonte": "medido",
             "origem": "scripts/17_testar_determinismo.sh"},
        ],
        "premissas": [
            {"rotulo": "custo de capital", "valor": pct(taxa, 0),
             "nota": "parâmetro do custo de oportunidade; ajuste com --taxa-oportunidade"},
            {"rotulo": "capital = saldo × preço médio", "valor": milhoes(estoque),
             "nota": "ESTOQUE_ATUAL × PRECO_MEDIO_UNITARIO do ERP, sem ajuste de obsolescência"},
            {"rotulo": "capital que depende de LLM", "valor": milhoes(dep_llm),
             "nota": f"{pct(dep_llm / capital_bloq) if capital_bloq else '—'} do consolidável "
                     "veio de cluster com decisão de LLM na chave"},
        ],
        "nao_medido": [
            {"rotulo": "compras evitadas pela busca",
             "motivo": "exige log de requisições com status de transferência, que esta base "
                       "não traz"},
            {"rotulo": "NF-e que deixaram de travar",
             "motivo": "exige o retorno da SEFAZ; o que existe é o NCM corrigido contra a "
                       "tabela vigente"},
            {"rotulo": "capital consolidado acumulado por mês",
             "motivo": "não há série histórica: esta é a primeira execução, o marco zero"},
        ],
    }
    Path(a.saida).write_text(json.dumps(radar, ensure_ascii=False, indent=1) + "\n",
                             encoding="utf-8")
    copia = RAIZ / "frontend/dados/radar.json"
    copia.parent.mkdir(parents=True, exist_ok=True)
    copia.write_text(Path(a.saida).read_text(encoding="utf-8"), encoding="utf-8")

    print(f"estoque na base: {milhoes(estoque)} em {num(itens_base)} itens")
    print(f"capital consolidavel: {milhoes(capital_bloq)} "
          f"({pct(capital_bloq / estoque)}) em {num(len(bloq))} codigos a bloquear")
    print(f"precisao da juncao no gabarito: {pct(prec)} [{pct(lo, 0)}-{pct(hi, 0)}] "
          f"({vp}/{vp + fp})")
    print(f"capital na fila de intervencao: {milhoes(fila.get('capital_na_fila', 0))}")
    print(f"nao medido: {len(radar['nao_medido'])} cartoes dizem isso na tela")
    print(f"\n{a.saida}\n{copia}  (servido em /frontend/dados/radar.json)")


if __name__ == "__main__":
    main()
