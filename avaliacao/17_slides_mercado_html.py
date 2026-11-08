# -*- coding: utf-8 -*-
"""Gera os slides de MERCADO E MODELO DE NEGOCIO, no desenho do deck
"Pipeline de Saneamento VX" (mesma paleta e componentes de 16_slides_pedidos_html.py).

Uso:
  backend/.venv/bin/python avaliacao/17_slides_mercado_html.py \
      [--saida avaliacao/slides_mercado.html]

Quatro telas 16:9, para entrar depois dos slides de pedidos.

TRES TIPOS DE NUMERO, NUNCA MISTURADOS SEM AVISO
------------------------------------------------
MEDIDO   calculado aqui a partir de artefatos/radar.json, artefatos/plano_juncao.csv
         e dados/01_base_materiais.xlsx. Se um arquivo faltar, o script para.
PREMISSA preco, numero de clientes, taxa. Ficam todas no dicionario PREMISSA abaixo,
         para serem contestadas e trocadas num lugar so.
EXTERNO  numero de fonte publica, com a URL no dicionario EXTERNO. Conferido em
         08/11/2026; os institutos de mercado divergem muito entre si (ver nota).
"""
import argparse
import html
import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent

C = {
    "navy": "#17202a", "teal": "#1d6a73", "surface": "#f2f4f3", "card": "#fefefe",
    "track": "#e0e6e5", "green": "#2d794b", "cream": "#f5ead2", "amber": "#7e5200",
    "pink": "#f4dedb", "red": "#8d2d29", "cyan": "#5cb7c0", "onDark": "#edf1f0",
}

# ------------------------------------------------------------- premissas ----
PREMISSA = {
    "preco_registro": 15.0,        # R$ por registro saneado (projeto unico)
    "assinatura_mes": 20_000.0,    # R$/mes do modo de cadastro, cliente com 6 plantas
    "comissao_rede": 0.05,         # fatia de cada transacao entre empresas (visao)
    "empresas_sam": 200,           # industriais multiplanta no Brasil no perfil
    "clientes_ano3": 10,           # SOM
    "parado_anos": 2,              # estoque sem movimento ha mais que isso = parado
}

# ---------------------------------------------------------- fontes externas ----
EXTERNO = {
    "mdm_global_usd_bi": 18.63,    # 2025, Fortune Business Insights
    "mdm_faixa": "US$ 5 a 23 bi conforme o instituto",
    "mdm_url": "fortunebusinessinsights.com/master-data-management-market-114277",
    "petrobras_mat_rs_bi": 8.393,  # materiais, suprimentos e outros, 31/12/2024
    "petrobras_url": "Petrobras, DF 4T24 (6-K, SEC), nota de estoques",
    "vale_cons_usd_mi": 988,       # consumable inventory, 31/12/2024
    "vale_url": "Vale, 20-F 2024, nota 13",
    "verusen_dup": "10 a 20%",     # do estoque, em operacoes multiplanta (dado de fornecedor)
    "verdantis_dup": "5 a 7%",     # das compras de MRO (pesquisa de fornecedor)
}


def exige(p: Path) -> Path:
    if not p.exists():
        sys.exit(f"ERRO: falta {p}.")
    return p


def e(s):
    return html.escape(str(s))


def brl(v, casas=2, sufixo=" mi", div=1e6):
    return "R$ " + f"{v / div:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".") + sufixo


def mil(n):
    return f"{int(round(n)):,}".replace(",", ".")


def pbr(f, casas=1):
    return f"{f * 100:.{casas}f}%".replace(".", ",")


# ------------------------------------------------------------------- dados ----
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--saida", default=str(RAIZ / "slides_mercado.html"))
a = ap.parse_args()

R = json.loads(exige(REPO / "artefatos/radar.json").read_text(encoding="utf-8"))
H = R["hero"]
ESTOQUE = R["base"]["estoque"]
N_ITENS = R["base"]["itens"]
CONSOLIDAVEL = H["consolidavel"]["valor"]
OPORTUNIDADE = H["oportunidade"]["valor"]
NCM = H["ncm"]["valor"]

arq_base = REPO / "dados/01_base_materiais.xlsx"
if not arq_base.exists():
    arq_base = REPO / "01_base_materiais.xlsx"
b = pd.read_excel(exige(arq_base), sheet_name="BASE_MATERIAIS")
b["CODIGO"] = b["CODIGO_MATERIAL"].astype(str)
b["ult"] = pd.to_datetime(b["DATA_ULTIMA_MOVIMENTACAO"])
REF = b["ult"].max()
anos_criacao = pd.to_datetime(b["DATA_CRIACAO"]).dt.year
CAD_ANO = anos_criacao[anos_criacao.between(2021, 2025)].value_counts().mean()

# Ponte entre plantas: mesmo item (mesma CHAVE no plano de juncao), parado numa
# planta e zerado-mas-movimentando noutra. Mesmo calculo da conversa de 08/11.
p = pd.read_csv(exige(REPO / "artefatos/plano_juncao.csv"), dtype={"CODIGO": str})
d = p.merge(b[["CODIGO", "CENTRO", "STATUS", "ESTOQUE_ATUAL", "PRECO_MEDIO_UNITARIO", "ult"]],
            on="CODIGO")
d["valor"] = d["ESTOQUE_ATUAL"] * d["PRECO_MEDIO_UNITARIO"]
d["dias"] = (REF - d["ult"]).dt.days
d = d[d.groupby("CHAVE")["CENTRO"].transform("nunique") >= 2]


def ponte(sem_cd):
    parado = (d["ESTOQUE_ATUAL"] > 0) & ((d["dias"] > 365 * PREMISSA["parado_anos"]) | d["ult"].isna())
    if sem_cd:
        parado &= ~d["CENTRO"].str.startswith("9000")
    demanda = (d["ESTOQUE_ATUAL"] == 0) & (d["dias"] <= 365) & (d["STATUS"] == "ATIVO")
    linhas = []
    for chave, x in d.groupby("CHAVE"):
        s, q = x[parado.loc[x.index]], x[demanda.loc[x.index]]
        if len(s) and len(q) and set(q["CENTRO"]) - set(s["CENTRO"]):
            linhas.append((chave, s["valor"].sum(), s["CENTRO"].iloc[0], q["CENTRO"].iloc[0]))
    return pd.DataFrame(linhas, columns=["chave", "valor", "sobra", "falta"]).sort_values(
        "valor", ascending=False)


P_TODOS, P_SEM_CD = ponte(False), ponte(True)
TOP = P_TODOS.iloc[0]
top_nome = " ".join(TOP["chave"].split("|")[1:3]).title()
top_pn = TOP["chave"].split("|")[3]

# ------------------------------------------------------------- derivados ----
SANEAMENTO = N_ITENS * PREMISSA["preco_registro"]
ASSIN_ANO = PREMISSA["assinatura_mes"] * 12
CUSTO_ANO1 = SANEAMENTO + ASSIN_ANO
RETORNO = OPORTUNIDADE / CUSTO_ANO1
PAYBACK_MESES = CUSTO_ANO1 / (OPORTUNIDADE / 12)
SAM_REC = PREMISSA["empresas_sam"] * ASSIN_ANO
SAM_PROJ = PREMISSA["empresas_sam"] * SANEAMENTO
SOM_ARR = PREMISSA["clientes_ano3"] * ASSIN_ANO
SOM_PROJ = PREMISSA["clientes_ano3"] * SANEAMENTO
PETRO_X = EXTERNO["petrobras_mat_rs_bi"] * 1e9 / ESTOQUE
RAZAO = CONSOLIDAVEL / ESTOQUE


# -------------------------------------------------------------- componentes ----
def slide(label, titulo, corpo, fonte):
    return f"""<section class="slide">
  <div class="rot">{e(label)}</div>
  <h2>{titulo}</h2>
  <div class="corpo">{corpo}</div>
  <div class="fonte">fonte: {e(fonte)}</div>
</section>"""


def cartao(rotulo, numero, nota, cor=None, tipo="", destaque=False):
    estilo = f' style="color:{cor}"' if cor else ""
    selo = f'<span class="selo {tipo}">{tipo}</span>' if tipo else ""
    return f"""<div class="cartao{' destaque' if destaque else ''}">
      <div class="crot">{rotulo}{selo}</div>
      <div class="cnum"{estilo}>{numero}</div>
      <div class="cnota">{nota}</div>
    </div>"""


def tabela(cabecalho, linhas, larguras=None):
    cols = "".join(f'<col style="width:{w}">' for w in larguras) if larguras else ""
    th = "".join(f"<th>{c}</th>" for c in cabecalho)
    trs = []
    for ln in linhas:
        cls = ""
        if ln[0] in ("__VISAO__", "__NOS__"):
            cls = ' class="visao"' if ln[0] == "__VISAO__" else ' class="nos"'
            ln = ln[1:]
        trs.append(f"<tr{cls}>" + "".join(f"<td>{c}</td>" for c in ln) + "</tr>")
    return f"<table><colgroup>{cols}</colgroup><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"


SL = []

# 1 ------------------------------------------------------------ valor ----
SL.append(slide(
    "MODELO DE NEGÓCIO · O QUE O CLIENTE GANHA",
    f"O cliente recupera {RETORNO:.0f}× o que paga no primeiro ano",
    f"""<div class="grade">
  {cartao("Capital consolidável", brl(CONSOLIDAVEL), f"{pbr(RAZAO)} dos {brl(ESTOQUE)} em estoque, preso em códigos redundantes.", C['teal'], "medido")}
  {cartao("Custo de oportunidade", brl(OPORTUNIDADE) + "<small>/ano</small>", "o que esse capital custa parado, a 30% a.a. (parâmetro do radar).", C['teal'], "premissa")}
  {cartao("Ponte entre plantas", f"{brl(P_SEM_CD.valor.sum(), 1, '')}–{brl(P_TODOS.valor.sum(), 1, ' mi')[3:]}",
          f"{len(P_TODOS)} itens parados há +{PREMISSA['parado_anos']} anos numa planta e zerados noutra que os movimenta. "
          f"Maior caso: {e(top_nome)} {e(top_pn)}, {brl(TOP.valor, 2, ' mil', 1e3)} no CD com a mina zerada.", C['green'], "medido")}
  {cartao("Preço no ano 1", brl(CUSTO_ANO1, 0, " mil", 1e3),
          f"saneamento ({mil(N_ITENS)} registros × R$ {PREMISSA['preco_registro']:.0f}) + assinatura de R$ {PREMISSA['assinatura_mes'] / 1e3:.0f} mil/mês.", None, "premissa")}
  {cartao("Retorno no ano 1", f"{RETORNO:.0f}×", f"custo de oportunidade ÷ preço: o preço se paga em {PAYBACK_MESES:.1f} mês de capital liberado.".replace(f"{PAYBACK_MESES:.1f}", f"{PAYBACK_MESES:.1f}".replace(".", ",")), C['amber'], "", True)}
  {cartao("NCM corrigido", mil(NCM), "contra a tabela vigente: risco fiscal que sai da base sem projeto separado.", C['teal'], "medido")}
</div>
<p class="obs ressalva"><b>Ressalva.</b> A Serra Azul é fictícia: todo número medido vale nesta base. O que se leva a outro cliente é o método,
e a razão de {pbr(RAZAO)} do estoque, que dimensiona o ganho de cada empresa com o estoque dela.</p>""",
    "artefatos/radar.json · plano_juncao.csv × 01_base_materiais.xlsx · premissas em 17_slides_mercado_html.py"))

# 2 ----------------------------------------------------------- modelo ----
SL.append(slide(
    "MODELO DE NEGÓCIO · TRÊS RECEITAS",
    "O saneamento abre a porta; o cadastro sustenta o contrato",
    tabela(
        ["camada", "natureza", "como cobra", "na Serra Azul"],
        [
            ["Saneamento", "projeto, uma vez: limpa a base de 22 anos",
             f"por registro saneado (R$ {PREMISSA['preco_registro']:.0f})", brl(SANEAMENTO, 0, " mil", 1e3) + " uma vez"],
            ["Modo de cadastro", f"operação contínua: {mil(CAD_ANO)} cadastros novos por ano, constante há 5 anos; inclui a ponte entre plantas",
             "assinatura mensal", brl(ASSIN_ANO, 0, " mil", 1e3) + " por ano"],
            ["__VISAO__", "Rede entre empresas · visão",
             "a sobra de um cliente vira oferta para outro; a chave de identidade é o que torna os estoques comparáveis",
             f"comissão de {PREMISSA['comissao_rede'] * 100:.0f}% por transação", "depende de vários clientes na mesma rede"],
        ],
        ["20%", "42%", "20%", "18%"])
    + f"""<p class="obs">Sem o controle de entrada, a base volta a sujar a {mil(CAD_ANO)} itens por ano e o ganho do saneamento se perde. O saneamento vende,
o cadastro mantém o cliente, e cada cliente novo deixa a rede mais valiosa para os outros.</p>
<p class="obs destaque-obs"><b>Margem.</b> A IA quase não pesa no custo: os 12.909 fabricantes preenchidos por LLM custaram <b>US$ 20,45</b>,
e as regras de custo zero resolvem o resto antes de chamar o modelo.</p>""",
    "docs/03-analise-mercado.md §5 e §9 · README.md · premissas em 17_slides_mercado_html.py"))

# 3 ---------------------------------------------------------- mercado ----
SL.append(slide(
    "TAMANHO DE MERCADO · TAM, SAM E SOM",
    f"Só a Petrobras tem {PETRO_X:.0f} Serras Azuis em materiais",
    f"""<div class="funil">
  <div class="nivel n1"><div class="ntag">TAM</div><div class="nval">US$ {str(round(EXTERNO['mdm_global_usd_bi'], 1)).replace(".", ",")} bi<small>/ano</small></div>
    <div class="ntxt"><b>Mercado global de gestão de dados mestres (MDM), 2025.</b> É a categoria onde o produto compete. Os institutos divergem: {EXTERNO['mdm_faixa']}.<span class="selo externo">externo</span></div></div>
  <div class="nivel n2"><div class="ntag">SAM</div><div class="nval">{brl(SAM_REC, 0)}<small>/ano</small></div>
    <div class="ntxt"><b>{PREMISSA['empresas_sam']} industriais multiplanta no Brasil</b> (mineração, energia, óleo e gás, siderurgia, celulose) × assinatura,
      mais {brl(SAM_PROJ, 0)} em projetos de saneamento. Piso: o preço é o de um cliente do porte da Serra Azul.<span class="selo premissa">premissa</span></div></div>
  <div class="nivel n3"><div class="ntag">SOM</div><div class="nval">{brl(SOM_ARR, 1)}<small>/ano</small></div>
    <div class="ntxt"><b>{PREMISSA['clientes_ano3']} clientes no ano 3</b>, em receita recorrente, mais {brl(SOM_PROJ, 1)} em projetos de saneamento acumulados.<span class="selo premissa">premissa</span></div></div>
</div>
<div class="grade g2">
  {cartao("Petrobras · materiais e suprimentos", f"R$ {EXTERNO['petrobras_mat_rs_bi']:.2f} bi".replace(".", ","), f"31/12/2024. A Serra Azul tem {brl(ESTOQUE)}.", C['teal'], "externo")}
  {cartao("Vale · estoque de consumo", f"US$ {EXTERNO['vale_cons_usd_mi']} mi", "31/12/2024. Petróleo e mineração: dois setores do perfil, cada um com bilhões em materiais de manutenção.", C['teal'], "externo")}
  {cartao("Duplicidade · outros medidores", EXTERNO['verusen_dup'], f"do estoque em operações multiplanta (Verusen) e {EXTERNO['verdantis_dup']} das compras de MRO (Verdantis). Aqui: {pbr(RAZAO)}.", C['amber'], "externo", True)}
</div>""",
    f"{EXTERNO['mdm_url']} · {EXTERNO['petrobras_url']} · {EXTERNO['vale_url']} · verusen.com · verdantis.com"))

# 4 ------------------------------------------------------- concorrencia ----
SL.append(slide(
    "CONCORRÊNCIA · POR QUE AGORA",
    "O mercado já paga por isso. Ninguém lê o texto em português",
    tabela(
        ["alternativa", "o que faz", "o que falta"],
        [
            ["SAP MDG e módulos de ERP", "fluxo de aprovação do cadastro", "garante que o campo foi preenchido, não que está certo; não lê texto livre"],
            ["Informatica, Stibo e plataformas de MDM", "governam, versionam e casam registros", "o casamento é por similaridade de texto, que acha 0 dos 2 grupos de duplicidade plantados no gabarito"],
            ["Especialistas em MRO (Verdantis, Verusen, SPARETECH)", "limpeza e enriquecimento de peças com IA", "foco em inglês e catálogo global; não trazem NCM nem o PDM do cliente. Mostram que existe quem pague: a SPARETECH captou Série A com a Insight Partners"],
            ["Consultoria e BPO de cadastro", "equipe limpa a base em projeto", "resolve o passivo e vai embora; a base volta a sujar"],
            ["__NOS__", "vxwinners", "lê texto industrial abreviado em português, contra o PDM", "duplicidade por igualdade de chave, auditável; NCM; equivalência não é duplicidade; pendência em vez de palpite"],
        ],
        ["27%", "28%", "45%"])
    + """<p class="obs"><b>Por que agora.</b> Ler <code>FILTRO P551808 DONALDSON</code> e separar part number de fabricante era trabalho de especialista.
Com modelos de linguagem restritos à lista do PDM, custa centavos e dá para medir em gabarito. A reforma tributária (CBS/IBS) aumenta o custo de NCM errado.</p>""",
    "docs/03-analise-mercado.md §4, §7 e §8 · insightpartners.com (Série A da SPARETECH)"))

# ---------------------------------------------------------------- CSS ----
CSS = f"""
:root {{
  --navy:{C['navy']}; --teal:{C['teal']}; --surface:{C['surface']}; --card:{C['card']};
  --track:{C['track']}; --green:{C['green']}; --cream:{C['cream']}; --amber:{C['amber']};
  --pink:{C['pink']}; --red:{C['red']}; --cyan:{C['cyan']}; --onDark:{C['onDark']};
  --tit: "Archivo Narrow","Oswald","Roboto Condensed","Ubuntu Sans",
         "Liberation Sans Narrow","Nimbus Sans Narrow",system-ui,sans-serif;
  --txt: system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
  --mono: ui-monospace,"JetBrains Mono","SF Mono","DejaVu Sans Mono",Menlo,monospace;
}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:#8a9098;font-family:var(--txt);color:var(--navy)}}
.deck{{display:flex;flex-direction:column;align-items:center;gap:22px;padding:22px}}
.slide{{position:relative;width:1334px;height:750px;flex:0 0 auto;background:var(--surface);
  padding:80px 90px 70px;overflow:hidden}}
.rot{{font-family:var(--mono);font-size:13px;letter-spacing:.14em;color:var(--teal);
  text-transform:uppercase;margin:0 0 14px}}
h2{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:46px;
  line-height:1.04;letter-spacing:-.005em;margin:0 0 10px}}
.corpo{{margin-top:14px}}
.fonte{{position:absolute;left:90px;bottom:30px;right:90px;font-family:var(--mono);font-size:12px;
  color:rgba(23,32,42,.45)}}
table{{width:100%;border-collapse:collapse;font-size:17.5px;table-layout:fixed}}
thead th{{background:var(--track);font-weight:600;font-size:14px;padding:10px 14px;text-align:left;
  border:1px solid rgba(23,32,42,.10)}}
tbody td{{padding:13px 15px;border:1px solid rgba(23,32,42,.10);background:var(--card);
  vertical-align:top;line-height:1.35}}
tbody td:first-child{{font-weight:600}}
tr.visao td{{background:var(--cream);color:rgba(23,32,42,.85)}}
tr.visao td:first-child{{color:var(--amber)}}
tr.nos td{{background:#dcebe9}}
tr.nos td:first-child{{color:var(--teal)}}
code{{font-family:var(--mono);font-size:.92em;background:rgba(23,32,42,.055);padding:1px 5px;border-radius:3px}}
.grade{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.grade.g2{{margin-top:22px}}
.cartao{{background:var(--card);border:1px solid rgba(23,32,42,.09);border-radius:8px;
  padding:16px 20px 14px;min-height:150px;display:flex;flex-direction:column}}
.g2 .cartao{{min-height:150px}}
.cartao.destaque{{background:var(--cream);border-color:rgba(126,82,0,.18)}}
.crot{{font-size:14px;color:rgba(23,32,42,.62);margin-bottom:6px;display:flex;justify-content:space-between;gap:8px}}
.cnum{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:40px;line-height:1;margin-bottom:auto}}
.cnum small,.nval small{{font-size:.5em;font-weight:600;margin-left:3px}}
.cnota{{font-size:13px;line-height:1.38;color:rgba(23,32,42,.72);margin-top:10px}}
.selo{{font-family:var(--mono);font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;
  padding:2px 6px;border-radius:3px;height:fit-content;white-space:nowrap;margin-left:8px}}
.selo.medido{{background:#dcebe9;color:var(--teal)}}
.selo.premissa{{background:var(--cream);color:var(--amber)}}
.selo.externo{{background:var(--track);color:rgba(23,32,42,.7)}}
.obs{{font-size:17px;line-height:1.5;margin:16px 0 0;max-width:1150px}}
.obs.destaque-obs{{background:var(--cream);border-left:3px solid var(--amber);padding:11px 16px;margin-top:12px}}
.obs.ressalva{{background:var(--card);border-left:3px solid var(--teal);padding:11px 16px;font-size:14px;color:rgba(23,32,42,.8)}}
.funil{{display:flex;flex-direction:column;gap:8px}}
.nivel{{display:grid;grid-template-columns:70px 230px 1fr;align-items:center;gap:18px;
  background:var(--card);border:1px solid rgba(23,32,42,.09);border-radius:8px;padding:16px 18px}}
.nivel.n2{{margin-left:50px}} .nivel.n3{{margin-left:100px}}
.n1{{border-left:6px solid var(--track)}} .n2{{border-left:6px solid var(--cyan)}} .n3{{border-left:6px solid var(--teal)}}
.ntag{{font-family:var(--mono);font-size:15px;font-weight:700;letter-spacing:.1em;color:var(--teal)}}
.nval{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:36px;line-height:1}}
.ntxt{{font-size:14.5px;line-height:1.4;color:rgba(23,32,42,.78)}}
.ntxt .selo{{margin-left:8px}}
@media print{{
  @page{{size:1334px 750px;margin:0}}
  html,body{{background:#fff}}
  .deck{{gap:0;padding:0}}
  .slide{{page-break-after:always;break-after:page}}
}}
"""

HTML = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Pipeline de saneamento · mercado e modelo</title>
<meta name="viewport" content="width=1334">
<style>{CSS}</style></head>
<body><div class="deck">
{chr(10).join(SL)}
</div></body></html>
"""

Path(a.saida).write_text(HTML, encoding="utf-8")
print(f"gravado {a.saida}  ({len(SL)} slides)")
print(f"  retorno ano 1 {RETORNO:.1f}x · payback {PAYBACK_MESES:.2f} mes · ponte {brl(P_SEM_CD.valor.sum())}–{brl(P_TODOS.valor.sum())}")
print(f"  SAM {brl(SAM_REC)}/ano + {brl(SAM_PROJ)} projetos · SOM {brl(SOM_ARR)}/ano · Petrobras = {PETRO_X:.1f}x Serra Azul")
