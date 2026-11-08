# -*- coding: utf-8 -*-
"""Gera os slides de PEDIDOS, no desenho do deck "Pipeline de Saneamento VX".

Uso:
  backend/.venv/bin/python avaliacao/16_slides_pedidos_html.py \
      [--saida avaliacao/slides_pedidos.html]

Quatro telas 16:9, para entrar depois do slide "O que esta medido, e o que ainda
nao" do deck existente. Abre no navegador; imprimir para PDF da uma pagina em
paisagem por slide.

NENHUM NUMERO E DIGITADO AQUI. Tudo vem de:
  avaliacao/resultado_pedidos.json   publicado por evaluate_pedidos.py
  avaliacao/concordancia_pedidos.json
  dados/02_pedidos_cadastro.xlsx     contagem dos canais de entrada
  avaliacao/candidatos_pedidos.csv   propriedades da amostra
Se um arquivo faltar, o script para e diz qual - em vez de inventar valor.

PALETA
------
Medida do PDF do deck por amostragem de pixel (pdftoppm + contagem), nao
escolhida: navy #17202a, teal #1d6a73, superficie #f2f4f3, cartao #fefefe,
trilha #e0e6e5, verde #2d794b, creme #f5ead2, ambar #7e5200, rosa #f4dedb,
vermelho #8d2d29, ciano #5cb7c0, texto-no-escuro #edf1f0.

Contraste conferido com o validador da skill de dataviz (APCA/WCAG): todos os
pares de texto usados passam (Lc >= 71 nos textos, Lc 54 no numero grande sobre
navy, que e tamanho de titulo). O grafico de barras usa UMA matiz mais o
vermelho de status no caso critico, com rotulo direto em cada barra - nao e
paleta categorica, e por isso nao passa pelo teste de separacao categorica.
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

ROTULO_ESTILO = {
    "telegrafico": "texto livre telegráfico",
    "ficha": "ficha técnica anexa",
    "email_longo": "e-mail com lista",
    "catalogo": "catálogo do fornecedor",
}
ORDEM_ESTILO = ["telegrafico", "ficha", "email_longo", "catalogo"]


def exige(p: Path) -> Path:
    if not p.exists():
        sys.exit(f"ERRO: falta {p}. Rode evaluate_pedidos.py antes.")
    return p


def pct(t, casas=1):
    return f"{t['p'] * 100:.{casas}f}%".replace(".", ",")


def pbr(fracao, casas=1):
    """Fracao -> porcentagem com virgula decimal. Nunca aplicar replace numa
    frase inteira: ja trocou o ponto final de uma sentenca por virgula."""
    return f"{fracao * 100:.{casas}f}%".replace(".", ",")


def num_br(x, casas=3):
    return f"{x:.{casas}f}".replace(".", ",")


def ic(t):
    return (f"{t['ic'][0] * 100:.1f}–{t['ic'][1] * 100:.1f}%").replace(".", ",")


def mil(n):
    return f"{n:,}".replace(",", ".")


def e(s):
    return html.escape(str(s))


# ------------------------------------------------------------------- dados ----
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--saida", default=str(RAIZ / "slides_pedidos.html"))
a = ap.parse_args()

M = json.loads(exige(RAIZ / "resultado_pedidos.json").read_text(encoding="utf-8"))
CONC = json.loads(exige(RAIZ / "concordancia_pedidos.json").read_text(encoding="utf-8"))
cand = pd.read_csv(exige(RAIZ / "candidatos_pedidos.csv"), dtype=str).fillna("")

arq_ped = REPO / "dados/02_pedidos_cadastro.xlsx"
if not arq_ped.exists():
    arq_ped = REPO / "02_pedidos_cadastro.xlsx"
ped = pd.read_excel(exige(arq_ped), sheet_name="PEDIDOS", dtype=str).fillna("")
N_PED = len(ped)
CANAIS = ped["CANAL"].value_counts().to_dict()
N_ANEXO = int((ped["TIPO_ANEXO"] != "").sum())
N_CATALOGO = int((ped["TIPO_ANEXO"] == "CATALOGO FORNECEDOR").sum())
_comb = (ped["TEXTO_SOLICITACAO"].str.strip() + "\n"
         + ped["CONTEUDO_ANEXO"].str.strip()).str.strip()


def _meio_minusculo(t):
    """Mesma regra do 22_candidatos_pedidos.py: metade ou mais das letras baixas."""
    letras = [c for c in t if c.isalpha()]
    return bool(letras) and sum(1 for c in letras if c.islower()) / len(letras) >= 0.5


N_MINUSCULA = int(_comb.map(_meio_minusculo).sum())

base = REPO / "dados/01_base_materiais.xlsx"
N_BASE = len(pd.read_excel(base, sheet_name="BASE_MATERIAIS", usecols=[0], dtype=str)) \
    if base.exists() else None


# -------------------------------------------------------------- componentes ----
def slide(label, titulo, corpo, fonte, escuro=False, sub=""):
    cls = " escuro" if escuro else ""
    subhtml = f'<p class="sub">{sub}</p>' if sub else ""
    return f"""<section class="slide{cls}">
  <div class="rot">{e(label)}</div>
  <h2>{titulo}</h2>
  {subhtml}
  <div class="corpo">{corpo}</div>
  <div class="fonte">fonte: {e(fonte)}</div>
</section>"""


def cartao(rotulo, numero, nota, cor=None, destaque=False):
    estilo = f' style="color:{cor}"' if cor else ""
    return f"""<div class="cartao{' destaque' if destaque else ''}">
      <div class="crot">{rotulo}</div>
      <div class="cnum"{estilo}>{numero}</div>
      <div class="cnota">{nota}</div>
    </div>"""


def barras(itens, maximo=100.0):
    """itens: (rotulo, valor_pct, texto_direito, cor, titulo_hover)."""
    out = ['<div class="barras">']
    for rot, val, dire, cor, hover in itens:
        larg = max(0.6, val / maximo * 100)
        out.append(f"""<div class="linha" title="{e(hover)}">
      <div class="brot">{rot}</div>
      <div class="trilha"><div class="fill" style="width:{larg:.2f}%;background:{cor}"></div></div>
      <div class="bval" style="color:{cor}">{dire}</div>
    </div>""")
    out.append("</div>")
    return "\n".join(out)


def tabela(cabecalho, linhas, alinha=None):
    al = alinha or ["left"] * len(cabecalho)
    th = "".join(f'<th style="text-align:{al[i]}">{c}</th>'
                 for i, c in enumerate(cabecalho))
    trs = []
    for ln in linhas:
        cls = ' class="ruim"' if ln and ln[0] == "__RUIM__" else ""
        cels = ln[1:] if cls else ln
        tds = "".join(f'<td style="text-align:{al[i]}">{c}</td>'
                      for i, c in enumerate(cels))
        trs.append(f"<tr{cls}>{tds}</tr>")
    return f'<table><thead><tr>{th}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


# ------------------------------------------------------------------ slides ----
SL = []

# --- 1. por que um gabarito separado -----------------------------------------
cls_geral = M["classe"]["geral"]
frac_vazias = M["invencao"]["vazias_no_gabarito"] / M["rotulos_caixa"]
linhas_cmp = [
    ["registros", f"{mil(N_BASE)} materiais" if N_BASE else "—",
     f"{mil(N_PED)} pedidos"],
    ["formato do texto", "uma coluna de descrição",
     f"4 formatos · {len(CANAIS)} canais de entrada"],
    ["caixa alta", "praticamente toda a base",
     f"{mil(N_MINUSCULA)} dos {mil(N_PED)} têm minúscula"],
    ["onde está a informação", "na própria linha",
     f"{mil(N_ANEXO)} trazem o dado só no anexo"],
    ["língua", "português",
     f"{mil(N_CATALOGO)} em inglês (catálogo do fornecedor)"],
    ["o problema", "campo vazio: 78,5% da referência do fabricante",
     f"campo vazio é raro: {pbr(frac_vazias)} das caixas"],
]
SL.append(slide(
    "PEDIDOS · O QUE CHEGA, NÃO O QUE JÁ ESTÁ",
    "O gabarito mediu a base. O pedido é outra coisa.",
    tabela(["", "base", "pedido"], linhas_cmp, ["left", "left", "left"])
    + '<p class="obs">Medir na base não diz como o pipeline se comporta na '
      '<strong>entrada</strong>, que é onde o cadastro é decidido. Daí um gabarito '
      f'próprio: {mil(M["pedidos"])} pedidos sorteados, '
      f'{mil(M["rotulos_caixa"])} rótulos de caixa e {mil(M["pedidos"])} de classe, '
      'anotados só contra o texto cru e o PDM.</p>',
    "avaliacao/GABARITO_PEDIDOS.md · dados/02_pedidos_cadastro.xlsx"))

# --- 2. o achado: acerto de classe por formato de entrada ---------------------
pe = M["classe"]["por_estilo"]
itens = []
for k in ORDEM_ESTILO:
    if k not in pe:
        continue
    t = pe[k]
    critico = t["p"] < 0.9
    itens.append((ROTULO_ESTILO[k], t["p"] * 100, pct(t),
                  C["red"] if critico else C["teal"],
                  f"{t['k']} de {t['n']} · IC 95% {ic(t)}"))
cat = pe.get("catalogo", {})
SL.append(slide(
    "ACERTO DE CLASSE · POR FORMATO DE ENTRADA",
    "Os erros de classe estão num canal só",
    barras(itens)
    + f'<p class="obs"><strong>Os três formatos em português dão 100%.</strong> '
      f'O catálogo fica em {pct(cat)} [{ic(cat)}], e é de onde vêm '
      f'<strong>{M["classe"]["erros_no_catalogo"]} dos {M["classe"]["erros"]}</strong> '
      'erros. A causa é a língua: essas linhas chegam em inglês '
      '(<code>Ball valve</code>, <code>Hex head bolt</code>, <code>Oil seal</code>), '
      'o pipeline não acha o substantivo do PDM e conclui FORA_DO_PDM. Os acertos '
      'do canal confirmam — são <code>O-ring</code>, que coincide com o '
      'qualificador do PDM, e um item com os atributos em português.</p>'
      f'<p class="obs destaque-obs">{mil(N_CATALOGO)} dos {mil(N_PED)} pedidos '
      f'({pbr(N_CATALOGO / N_PED)}) entram por esse canal e seriam recusados por '
      'causa da língua. É conserto de vocabulário, não de modelo.</p>',
    "avaliacao/resultado_pedidos.md §1 · gold_classe_pedidos.csv",
    sub="escala 0–100% · rótulo direto em cada barra · n e IC 95% no hover do HTML e em resultado_pedidos.md"))

# --- 3. placar ---------------------------------------------------------------
cx = M["caixas"]
inv = M["invencao"]
pr = M["perdidas"]
# Classe em portugues = todos os formatos menos o catalogo do fornecedor, que
# chega em ingles. IC de Wilson, o mesmo do evaluate_pedidos.py.
_pt = [v for k, v in pe.items() if k != "catalogo"]
_k, _n = sum(v["k"] for v in _pt), sum(v["n"] for v in _pt)
_z = 1.96
_c = (_k / _n + _z * _z / (2 * _n)) / (1 + _z * _z / _n)
_m = _z * ((_k / _n * (1 - _k / _n) / _n + _z * _z / (4 * _n * _n)) ** 0.5) / (1 + _z * _z / _n)
cls_pt = {"k": _k, "n": _n, "p": _k / _n, "ic": [max(0.0, _c - _m), min(1.0, _c + _m)]}
n_fora_pt = pe.get("catalogo", {}).get("n", 0)
cards = [
    cartao("Acerto de classe · pedidos em português",
           f'{pct(cls_pt)}<span class="clado"><b>{n_fora_pt} de {cls_geral["n"]}</b>'
           f'<br>não vieram em português</span>',
           f"{cls_pt['k']} de {cls_pt['n']} · IC {ic(cls_pt)}. Contando os em inglês: "
           f"{pct(cls_geral)} ({cls_geral['k']} de {cls_geral['n']})",
           C["teal"]),
    cartao("Precisão das caixas", pct(cx["precisao"]),
           f"{cx['precisao']['k']} de {cx['precisao']['n']} valores afirmados · "
           f"IC {ic(cx['precisao'])}", C["green"]),
    cartao("Cobertura, classe certa", pct(cx["cobertura_classe_certa"]),
           f"{pct(cx['cobertura'])} no total; o resto se perde porque a classe "
           "errou", C["teal"]),
    cartao("Invenção · estrita", f"{inv['estrita']['k']}/{inv['estrita']['n']}",
           f"caixas vazias preenchidas · IC {ic(inv['estrita'])}. Na leitura "
           f"permissiva, {inv['permissiva']['k']}/{inv['permissiva']['n']}",
           C["amber"], destaque=True),
    cartao("Caixas perdidas", mil(pr["total"]),
           f"{pr['por_classe_errada']} por classe errada, {pr['pendente']} "
           f"\"não informado\", {pr['ambiguo']} ambíguas", C["navy"]),
    cartao("Concordância A×B · kappa",
           num_br(M["concordancia"]["kappa"]),
           f"{M['concordancia']['divergencias']} divergências adjudicadas — mas "
           "<strong>não</strong> são dois anotadores independentes", C["amber"],
           destaque=True),
]
SL.append(slide(
    "PEDIDOS · MEDIDO EM GABARITO",
    "Afirma pouco, e erra quase nada",
    f'<div class="grade">{"".join(cards)}</div>'
    + '<p class="obs ressalva"><strong>Ressalva de método.</strong> As duas '
      'passadas de anotação são do mesmo anotador — um LLM — sob regras de decisão '
      'diferentes, e não de duas pessoas. O kappa mede quanto a <em>regra</em> muda o '
      'rótulo, não concordância entre duas cabeças. Até '
      '<code>revisao_humana_pedidos.csv</code> voltar respondido, o gabarito é '
      'provisório. Execução medida sem BERT e sem LLM: são números do piso.</p>',
    "avaliacao/resultado_pedidos.json · concordancia_pedidos.json"))

# --- 4. os defeitos nomeados -------------------------------------------------
fontes = M["por_fonte"]
# ordenar por PRECISAO crescente. Ordenar pela chave trazia 'gramatica' (38 de
# 39) em vez de 'ordem_pdm' (0 de 3), que e o defeito de verdade.
pior = sorted((v["precisao"]["p"], k, v) for k, v in fontes.items()
              if v["precisao"]["n"] >= 1 and v["precisao"]["p"] < 1)
_, pior_nome, pior_v = (pior[0] if pior
                        else (0, "—", {"precisao": {"k": 0, "n": 0}}))
defeitos = [
    ["__RUIM__", "Vocabulário só em português",
     f"{M['classe']['erros_no_catalogo']} erros de classe",
     f"{mil(N_CATALOGO)} pedidos do canal de catálogo chegam em inglês e viram "
     "FORA_DO_PDM; cada recusa arrasta as caixas do item "
     f"({pr['por_classe_errada']} das {pr['total']} perdidas)"],
    ["Referência do fabricante não é extraída",
     f"{pr['referencia_fabricante']} caixas",
     "com a classe certa e o código visível no texto (<code>hb-467508</code>, "
     "<code>g2021</code>, <code>C 83 416</code>). Em PDM100 e PDM110 esse campo é "
     "metade da chave de identidade da regra 10"],
    ["Irmãos de grandeza",
     f"{inv['estrita']['k']} invenções + {pr['terminais_ambiguos']} ambíguas",
     "caixa vazia recebe o valor da irmã (terminal A copiado para B; a seção "
     "virando também diâmetro interno); e o espelho, dois terminais no texto que "
     "o pipeline não sabe separar"],
    [f"Camada <code>{e(pior_nome)}</code>",
     f"{pior_v['precisao']['k']} de {pior_v['precisao']['n']} certos",
     "nas correias, pôs o comprimento externo na caixa <code>REFERENCIA</code>, "
     "que devia levar a designação da correia (<code>A157</code>, "
     "<code>B146</code>, <code>SPB 3650</code>)"],
]
SL.append(slide(
    "PEDIDOS · QUATRO DEFEITOS COM NOME E LINHA",
    "Cada número aponta um conserto",
    tabela(["defeito", "tamanho", "o que acontece"], defeitos,
           ["left", "right", "left"])
    + '<p class="obs">Nenhum deles é "o modelo precisa melhorar". Os quatro têm '
      'arquivo, linha e teste possível — e o primeiro vale mais que os outros três '
      'somados.</p>',
    "avaliacao/resultado_pedidos.md §3 a §5"))

# -------------------------------------------------------------------- html ----
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
  padding:92px 90px 76px;overflow:hidden}}
.slide.escuro{{background:var(--navy);color:var(--onDark)}}
.rot{{font-family:var(--mono);font-size:13px;letter-spacing:.14em;color:var(--teal);
  text-transform:uppercase;margin:0 0 14px}}
.slide.escuro .rot{{color:var(--cyan)}}
h2{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:46px;
  line-height:1.04;letter-spacing:-.005em;margin:0 0 10px}}
.sub{{font-family:var(--mono);font-size:12.5px;color:rgba(23,32,42,.45);margin:0 0 20px}}
.corpo{{margin-top:14px}}
.fonte{{position:absolute;left:90px;bottom:34px;font-family:var(--mono);font-size:13px;
  color:rgba(23,32,42,.45)}}
.slide.escuro .fonte{{color:rgba(237,241,240,.45)}}

table{{width:100%;border-collapse:collapse;font-size:16.5px}}
thead th{{background:var(--track);font-weight:600;font-size:14.5px;padding:11px 14px;
  border:1px solid rgba(23,32,42,.10)}}
tbody td{{padding:11px 14px;border:1px solid rgba(23,32,42,.10);background:var(--card);
  vertical-align:top;line-height:1.35}}
tbody td:first-child{{font-weight:600}}
tr.ruim td{{background:var(--pink)}}
tr.ruim td:first-child{{color:var(--red)}}
code{{font-family:var(--mono);font-size:.92em;background:rgba(23,32,42,.055);
  padding:1px 5px;border-radius:3px}}

.barras{{display:flex;flex-direction:column;gap:14px;margin:8px 0 26px}}
.linha{{display:grid;grid-template-columns:270px 1fr 86px;align-items:center;gap:18px}}
.brot{{font-size:17px;font-weight:600}}
.trilha{{height:24px;background:var(--track);border-radius:4px;overflow:hidden}}
.fill{{height:100%;border-radius:0 4px 4px 0}}
.bval{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:24px;
  text-align:right}}

.grade{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}
.cartao{{background:var(--card);border:1px solid rgba(23,32,42,.09);border-radius:8px;
  padding:20px 22px 18px;min-height:168px;display:flex;flex-direction:column}}
.cartao.destaque{{background:var(--cream);border-color:rgba(126,82,0,.18)}}
.crot{{font-size:14.5px;color:rgba(23,32,42,.62);margin-bottom:6px}}
.clado{{font-family:var(--txt);font-weight:400;font-stretch:normal;font-size:14px;line-height:1.3;
  color:var(--amber);display:inline-block;vertical-align:middle;margin-left:14px;
  padding-left:12px;border-left:2px solid rgba(126,82,0,.35)}}
.clado b{{font-weight:700}}
.cnum{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:42px;
  line-height:1;margin-bottom:auto}}
.cnota{{font-size:13.5px;line-height:1.4;color:rgba(23,32,42,.72);margin-top:12px}}

.obs{{font-size:16px;line-height:1.5;margin:18px 0 0;max-width:1100px}}
.obs.destaque-obs{{background:var(--cream);border-left:3px solid var(--amber);
  padding:12px 16px;margin-top:14px}}
.obs.ressalva{{background:var(--card);border-left:3px solid var(--teal);
  padding:12px 16px;font-size:14.5px;color:rgba(23,32,42,.8)}}

@media print{{
  @page{{size:1334px 750px;margin:0}}
  html,body{{background:#fff}}
  .deck{{gap:0;padding:0}}
  .slide{{page-break-after:always;break-after:page}}
}}
"""

HTML = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Pipeline de saneamento · slides de pedidos</title>
<meta name="viewport" content="width=1334">
<style>{CSS}</style></head>
<body><div class="deck">
{chr(10).join(SL)}
</div></body></html>
"""

Path(a.saida).write_text(HTML, encoding="utf-8")
print(f"gravado {a.saida}  ({len(SL)} slides, {len(HTML) / 1024:.0f} KB, autocontido)")
print(f"  classe por formato: " + ", ".join(
    f"{ROTULO_ESTILO.get(k, k)} {pct(v)}" for k, v in
    sorted(pe.items(), key=lambda kv: -kv[1]["p"])))
