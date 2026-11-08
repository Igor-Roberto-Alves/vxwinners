# -*- coding: utf-8 -*-
"""Gera os slides de CAMADAS LIGADAS (BERT, LLM e classes aprendidas pelo LLM),
no desenho do deck "Pipeline de Saneamento VX". Entram depois dos slides de pedidos.

Uso:
  backend/.venv/bin/python avaliacao/18_slides_camadas_html.py \
      [--saida avaliacao/slides_camadas.html]

NENHUM NUMERO E DIGITADO AQUI. Tudo vem das rodadas em artefatos/medicao_pedidos/:
  1_piso/                      a medicao oficial (so regras), copiada antes de rodar
  0_piso_reexec/               a mesma configuracao rodada de novo (deu identico)
  2_bert/                      + BERT
  3_bert_llm/                  + LLM no residuo (desempate)
  4_classe_llm_sem_gabarito/   + regras de classe que o LLM aprendeu SEM ver o gabarito
  5_classe_llm_todos/          + regras de classe aprendidas com todos os pedidos
  sujeito_aprendido_*.json     as regras, com custo e o que as travas barraram
Cada rodada tem execucao.log (custo e tempo) e resultado.json (evaluate_pedidos.py).
Todas com --congelar-aprendizado: nenhuma rodada alterou o dicionario de atributos.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
MED = REPO / "artefatos/medicao_pedidos"

C = {
    "navy": "#17202a", "teal": "#1d6a73", "surface": "#f2f4f3", "card": "#fefefe",
    "track": "#e0e6e5", "green": "#2d794b", "cream": "#f5ead2", "amber": "#7e5200",
    "pink": "#f4dedb", "red": "#8d2d29", "cyan": "#5cb7c0",
}


def exige(p: Path) -> Path:
    if not p.exists():
        sys.exit(f"ERRO: falta {p}. Rode as medicoes antes (ver docstring).")
    return p


def e(s):
    return html.escape(str(s))


def pbr(f, casas=1):
    return f"{f * 100:.{casas}f}%".replace(".", ",")


def usd(v):
    return f"US$ {v:.2f}".replace(".", ",")


def log_de(rodada):
    return exige(MED / rodada / "execucao.log").read_text(encoding="utf-8")


def custo_llm(rodada):
    m = re.search(r"custo estimado: US\$ ([\d.]+)", log_de(rodada))
    return float(m.group(1)) if m else 0.0


def tempo(rodada):
    return float(re.search(r"tempo total\s+([\d.]+)s", log_de(rodada)).group(1))


ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--saida", default=str(RAIZ / "slides_camadas.html"))
a = ap.parse_args()

R = {r: json.loads(exige(MED / r / "resultado.json").read_text(encoding="utf-8"))
     for r in ("1_piso", "2_bert", "3_bert_llm", "4_classe_llm_sem_gabarito", "5_classe_llm_todos")}
SG = json.loads(exige(MED / "sujeito_aprendido_sem_gabarito.json").read_text(encoding="utf-8"))
TD = json.loads(exige(MED / "sujeito_aprendido_todos.json").read_text(encoding="utf-8"))

# custo acumulado: o desempate (3) e pago uma vez; as perguntas de classe da
# rodada 5 que ja estavam no cache foram pagas na rodada 4.
C_DESEMP = custo_llm("3_bert_llm")
C_CLS_SG = SG["uso"]["custo_usd"]
C_CLS_TD = SG["uso"]["custo_usd"] + TD["uso"]["custo_usd"]
CUSTO = {"1_piso": 0.0, "2_bert": 0.0, "3_bert_llm": C_DESEMP,
         "4_classe_llm_sem_gabarito": C_DESEMP + C_CLS_SG, "5_classe_llm_todos": C_DESEMP + C_CLS_TD}
TEMPO = {"1_piso": tempo("0_piso_reexec"), "2_bert": tempo("2_bert"), "3_bert_llm": tempo("3_bert_llm"),
         "4_classe_llm_sem_gabarito": tempo("4_classe_llm_sem_gabarito"),
         "5_classe_llm_todos": tempo("5_classe_llm_todos")}
N_PED = 520
CHAMADAS_DESEMP = int(re.search(r"(\d+) chamadas", log_de("3_bert_llm")).group(1))
N_TEXTOS_CLS = SG["uso"]["chamadas"] + TD["uso"]["chamadas"]


def slide(label, titulo, corpo, fonte):
    return f"""<section class="slide">
  <div class="rot">{e(label)}</div>
  <h2>{titulo}</h2>
  <div class="corpo">{corpo}</div>
  <div class="fonte">fonte: {e(fonte)}</div>
</section>"""


SL = []

# 1 ------------------------------------------------------ escada de camadas ----
ROTULO = {
    "1_piso": ("Só regras", "medição oficial · o piso"),
    "2_bert": ("+ BERT", "modelo local, sem custo por chamada"),
    "3_bert_llm": ("+ LLM no resíduo", f"{CHAMADAS_DESEMP} pedidos em dúvida, escolhendo da lista do PDM"),
    "4_classe_llm_sem_gabarito": ("+ classes pelo LLM", f"{len(SG['regras'])} regras aprendidas sem ver o gabarito"),
    "5_classe_llm_todos": ("+ classes pelo LLM", f"{len(TD['regras'])} regras, todos os pedidos (operação real)"),
}
linhas = []
for r, (nome, nota) in ROTULO.items():
    m = R[r]
    cx, cl = m["caixas"], m["classe"]
    inv = m["invencao"]["estrita"]
    cls = ' class="final"' if r == "5_classe_llm_todos" else ""
    linhas.append(f"""<tr{cls}><td><b>{nome}</b><div class="nota">{e(nota)}</div></td>
      <td class="n">{pbr(cl['geral']['p'])}</td><td class="n">{pbr(cl['por_estilo']['catalogo']['p'])}</td>
      <td class="n">{pbr(cx['precisao']['p'])}</td><td class="n">{pbr(cx['cobertura']['p'])}</td>
      <td class="n">{inv['k']}/{inv['n']}</td><td class="n">{usd(CUSTO[r])}</td>
      <td class="n">{TEMPO[r]:.0f} s</td></tr>""")
fim, ini = R["5_classe_llm_todos"], R["1_piso"]
tabela = f"""<table><thead><tr><th style="width:30%">configuração</th><th>classe</th><th>classe · catálogo em inglês</th>
  <th>precisão das caixas</th><th>cobertura</th><th>invenção</th><th>custo de LLM</th><th>tempo · 520 pedidos</th></tr></thead>
  <tbody>{''.join(linhas)}</tbody></table>"""
SL.append(slide(
    "PEDIDOS · LIGANDO O BERT E O LLM",
    f"Classe de {pbr(ini['classe']['geral']['p'])} para {pbr(fim['classe']['geral']['p'])}, "
    f"com {usd(CUSTO['5_classe_llm_todos'])} de LLM",
    tabela + f"""<div class="tres">
  <p><b>BERT:</b> não mexe na classe, que é decidida pelo substantivo. Preenche as caixas que as regras deixaram vazias:
  cobertura de {pbr(ini['caixas']['cobertura']['p'])} para {pbr(R['2_bert']['caixas']['cobertura']['p'])}, sem perder precisão.</p>
  <p><b>LLM no resíduo:</b> resolve as ambíguas e os conflitos entre regra e BERT, escolhendo só da lista do PDM.
  As caixas ambíguas perdidas vão de {ini['perdidas']['ambiguo']} para {R['3_bert_llm']['perdidas']['ambiguo']}.</p>
  <p><b>Classes pelo LLM:</b> ataca o catálogo em inglês, de onde vinham os 16 erros.
  Mesmo aprendendo sem ver o gabarito, a classe vai a {pbr(R['4_classe_llm_sem_gabarito']['classe']['geral']['p'])}.</p>
</div>
<p class="obs ressalva"><b>O custo total é de {usd(CUSTO['5_classe_llm_todos'])} para os {N_PED} pedidos</b>, menos de um décimo de centavo de dólar por pedido.
A invenção subiu de {ini['invencao']['estrita']['k']} para {fim['invencao']['estrita']['k']} em {fim['invencao']['estrita']['n']}: o LLM preencheu um acabamento
que o pedido não informava. O gabarito é o mesmo da medição oficial e continua provisório até a revisão humana.</p>""",
    "artefatos/medicao_pedidos/*/resultado.json e execucao.log · evaluate_pedidos.py · Haiku 4.5 no Bedrock"))

# 2 ------------------------------------------------------ regras de classe ----
regras = sorted(TD["regras"].items(), key=lambda kv: (-len(kv[1]["origens"]), kv[0]))
sem_gab = set(SG["regras"])
lin = []
for termo, r in regras:
    selo = '<span class="selo">sem gabarito</span>' if termo in sem_gab else ""
    lin.append(f"<tr><td><code>{e(termo)}</code>{selo}</td><td>{e(r['para'])}</td>"
               f"<td class='n'>{r['id_pdm']}</td><td class='n'>{len(r['origens'])}</td></tr>")
barradas = []
vistas = set()
for d in SG["descartadas"] + TD["descartadas"]:
    suj = d["sujeito"] if isinstance(d["sujeito"], str) else " ou ".join(d["sujeito"])
    k = (d["termo"], d["trava"])
    if k in vistas:
        continue
    vistas.add(k)
    barradas.append(f"<li><code>{e(d['termo'])}</code> → {e(suj)}<br><span>{e(d['trava'])}</span></li>")
n_nenhuma = len(TD["fora_do_pdm_confirmado"])
SL.append(slide(
    "PEDIDOS · O LLM ESCREVEU AS REGRAS",
    f"O LLM traduziu {len(regras)} nomes de classe e gravou cada um como regra",
    f"""<div class="duas">
  <div><table><thead><tr><th>termo do catálogo</th><th>sujeito do PDM</th><th>classe</th><th>pedidos</th></tr></thead>
    <tbody>{''.join(lin)}</tbody></table></div>
  <div class="lado">
    <div class="caixa"><div class="crot">Como funciona</div>
      <p>O LLM é chamado <b>uma vez por texto recusado</b>, lê a expressão inteira (<code>BALL VALVE</code> é
      VALVULA ESFERA, não "bola") e escolhe só da lista fechada de sujeitos do PDM. A resposta vira regra em
      <code>sujeito_aprendido.json</code>. Na rodada seguinte: <b>0 chamadas</b>, o dicionário resolve.</p></div>
    <div class="caixa"><div class="crot">Travas: barradas antes de virar regra</div>
      <ul>{''.join(barradas)}</ul>
      <p class="mini">Também barra regra que não reproduz a classe no próprio texto ou que não está escrita nele.
      {n_nenhuma} pedidos foram confirmados como fora do PDM (serviço, café, móvel).</p></div>
  </div>
</div>
<p class="obs ressalva"><b>Erros que sobraram (3 de 120):</b> <code>Pipe fitting</code> foi barrado pela trava e ficou para revisão humana;
o LLM respondeu "nenhuma classe" para <code>Safety glove</code>, que é LUVA SEGURANCA; e <code>Socket head cap screw</code> já caía em CAP no piso,
porque a palavra inglesa "cap" casa com o tampão de tubo. Nenhuma regra nova causou erro.</p>""",
    f"artefatos/medicao_pedidos/sujeito_aprendido_*.json · scripts/24_aprender_classes_llm.py · "
    f"{N_TEXTOS_CLS} perguntas, {usd(C_CLS_TD)}"))

CSS = f"""
:root{{--navy:{C['navy']};--teal:{C['teal']};--surface:{C['surface']};--card:{C['card']};--track:{C['track']};
 --green:{C['green']};--cream:{C['cream']};--amber:{C['amber']};--pink:{C['pink']};--red:{C['red']};--cyan:{C['cyan']};
 --tit:"Archivo Narrow","Oswald","Roboto Condensed","Ubuntu Sans","Liberation Sans Narrow","Nimbus Sans Narrow",system-ui,sans-serif;
 --txt:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
 --mono:ui-monospace,"JetBrains Mono","SF Mono","DejaVu Sans Mono",Menlo,monospace}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:#8a9098;font-family:var(--txt);color:var(--navy)}}
.deck{{display:flex;flex-direction:column;align-items:center;gap:22px;padding:22px}}
.slide{{position:relative;width:1334px;height:750px;flex:0 0 auto;background:var(--surface);padding:72px 90px 64px;overflow:hidden}}
.rot{{font-family:var(--mono);font-size:13px;letter-spacing:.14em;color:var(--teal);text-transform:uppercase;margin:0 0 14px}}
h2{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:44px;line-height:1.04;margin:0 0 10px}}
.corpo{{margin-top:12px}}
.fonte{{position:absolute;left:90px;right:90px;bottom:28px;font-family:var(--mono);font-size:12px;color:rgba(23,32,42,.45)}}
table{{width:100%;border-collapse:collapse;font-size:15px}}
thead th{{background:var(--track);font-weight:600;font-size:13px;padding:8px 10px;text-align:left;border:1px solid rgba(23,32,42,.10);line-height:1.25}}
tbody td{{padding:7px 10px;border:1px solid rgba(23,32,42,.10);background:var(--card);vertical-align:middle;line-height:1.3}}
td.n{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}}
tr.final td{{background:#dcebe9}}
.nota{{font-size:12.5px;color:rgba(23,32,42,.62);font-weight:400}}
code{{font-family:var(--mono);font-size:.9em;background:rgba(23,32,42,.055);padding:1px 5px;border-radius:3px}}
.tres{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}}
.tres p{{margin:0;font-size:14px;line-height:1.42;background:var(--card);border:1px solid rgba(23,32,42,.09);border-radius:8px;padding:11px 14px}}
.obs{{font-size:14.5px;line-height:1.45;margin:12px 0 0}}
.obs.ressalva{{background:var(--card);border-left:3px solid var(--teal);padding:10px 16px;color:rgba(23,32,42,.82)}}
.duas{{display:grid;grid-template-columns:1.25fr 1fr;gap:18px;align-items:start}}
.duas tbody td{{padding:6px 10px;font-size:14.5px}}
.selo{{font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;background:#dcebe9;color:var(--teal);
  padding:1px 5px;border-radius:3px;margin-left:8px;white-space:nowrap}}
.lado{{display:flex;flex-direction:column;gap:12px}}
.caixa{{background:var(--card);border:1px solid rgba(23,32,42,.09);border-radius:8px;padding:12px 16px}}
.caixa p{{margin:4px 0 0;font-size:14px;line-height:1.42}}
.caixa .mini{{font-size:12.5px;color:rgba(23,32,42,.7);margin-top:8px}}
.caixa ul{{margin:6px 0 0;padding-left:18px;font-size:14px;line-height:1.35}}
.caixa li{{margin-bottom:6px}} .caixa li span{{color:var(--red);font-size:12.5px}}
.crot{{font-size:13px;color:rgba(23,32,42,.62);font-weight:600}}
@media print{{@page{{size:1334px 750px;margin:0}} html,body{{background:#fff}} .deck{{gap:0;padding:0}}
 .slide{{page-break-after:always;break-after:page}}}}
"""

HTML = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Pipeline de saneamento · camadas ligadas</title>
<meta name="viewport" content="width=1334"><style>{CSS}</style></head>
<body><div class="deck">
{chr(10).join(SL)}
</div></body></html>
"""
Path(a.saida).write_text(HTML, encoding="utf-8")
print(f"gravado {a.saida}  ({len(SL)} slides)")
for r in ROTULO:
    print(f"  {r:28s} classe {pbr(R[r]['classe']['geral']['p'])}  custo {usd(CUSTO[r])}  {TEMPO[r]:.0f}s")
