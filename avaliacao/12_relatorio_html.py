# -*- coding: utf-8 -*-
"""Monta um HTML autocontido com o gabarito, o resultado da avaliacao e o codigo
que reproduz tudo.

Uso:
  uv run --no-project --with pandas --with openpyxl python avaliacao/12_relatorio_html.py \
      [--saida avaliacao/relatorio_caracteristicas.html]

Entradas (todas em avaliacao/):
  GABARITO_CARACTERISTICAS.md      metodo, estratos, kappa, limitacoes
  resultado_caracteristicas.md     saida de evaluate_caracteristicas.py
  concordancia_caracteristicas.json
  gold_caracteristicas.csv, gold_classe.csv, gold_juncao.csv
  10_candidatos_caracteristicas.py, 11_adjudicar_caracteristicas.py,
  evaluate_caracteristicas.py, 12_relatorio_html.py   (embutidos no HTML)

Os numeros dos cartoes do topo sao LIDOS do resultado_caracteristicas.md e do
concordancia_caracteristicas.json - nada e digitado a mao aqui. Se o formato
mudar, o script falha em vez de inventar numero.

Sem dependencia externa: so biblioteca padrao, e o HTML nao carrega nada da rede.
"""
import argparse
import csv
import html
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

FONTES = ["10_candidatos_caracteristicas.py", "11_adjudicar_caracteristicas.py",
          "evaluate_caracteristicas.py", "12_relatorio_html.py"]

COMANDOS = """# 0) o .venv do projeto nao tem pandas; tudo roda via uv
cd /home/igor-alves/clas/hack/vxwinners

# 1) selecao reproduzivel dos 240 itens e dos 150 pares (semente 20251107)
#    so e preciso rodar de novo se a base mudar: regerar muda a amostra
uv run --no-project --with pandas --with openpyxl python \\
    avaliacao/10_candidatos_caracteristicas.py

# 2) anotacao: duas passadas independentes (ordem_A e ordem_B do candidatos .csv)
#    produzem avaliacao/anotacoes_carac_A.jsonl e anotacoes_carac_B.jsonl
#    uma linha por rotulo:
#    {"CODIGO_MATERIAL","id_pdm","campo","y_gold","status","evidencia","justificativa"}
#    campo = _CLASSE (item), _JUNCAO (par) ou o nome do atributo do PDM

# 3) adjudicacao: acordo, kappa, gold, planilha de revisao humana
#    aborta se alguma divergencia nao tiver decisao escrita em ADJUDICACOES
uv run --no-project --with pandas --with openpyxl python \\
    avaliacao/11_adjudicar_caracteristicas.py

# 4) avaliacao do pipeline sobre os artefatos atuais
uv run --no-project --with pandas --with openpyxl python \\
    avaliacao/evaluate_caracteristicas.py \\
    --saida avaliacao/resultado_caracteristicas.md

# 5) este relatorio
uv run --no-project --with pandas --with openpyxl python \\
    avaliacao/12_relatorio_html.py \\
    --saida avaliacao/relatorio_caracteristicas.html

# opcional) quando a planilha conferida voltar, salve como
#   avaliacao/revisao_humana_caracteristicas_respondida.csv
# com concordo_discordo=DISCORDO + valor_certo/status_certo nas linhas corrigidas
# e rode o passo 3 outra vez: o gold e regerado com origem_decisao=revisao_humana
"""


# ------------------------------------------------- markdown (subconjunto) -----
def slug(texto, prefixo):
    t = "".join(c for c in unicodedata.normalize("NFKD", texto)
                if not unicodedata.combining(c)).lower()
    return prefixo + "-" + re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def inline(txt):
    t = html.escape(txt)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    return t


def md_para_html(md, prefixo):
    """Converte titulos, paragrafos, listas, tabelas e blocos de codigo.

    Os titulos descem um nivel (# -> h2) para caber sob o <h1> da pagina.
    Devolve (html, [(nivel, id, texto)]) para o sumario.
    """
    linhas = md.splitlines()
    out, toc = [], []
    i, n = 0, len(linhas)
    while i < n:
        linha = linhas[i]

        if linha.startswith("```"):                              # codigo cercado
            i += 1
            buf = []
            while i < n and not linhas[i].startswith("```"):
                buf.append(html.escape(linhas[i]))
                i += 1
            i += 1
            out.append("<pre class=\"bloco\"><code>" + "\n".join(buf) + "</code></pre>")
            continue

        m = re.match(r"^(#{1,4})\s+(.*)$", linha)                # titulo
        if m:
            nivel = min(len(m.group(1)) + 1, 5)
            texto = m.group(2).strip()
            ident = slug(texto, prefixo)
            toc.append((nivel, ident, texto))
            out.append(f"<h{nivel} id=\"{ident}\">{inline(texto)}</h{nivel}>")
            i += 1
            continue

        if linha.startswith("|"):                                # tabela
            bloco = []
            while i < n and linhas[i].startswith("|"):
                bloco.append(linhas[i])
                i += 1
            celulas = [[c.strip() for c in l.strip().strip("|").split("|")]
                       for l in bloco]
            cab = celulas[0]
            corpo = celulas[2:] if len(celulas) > 1 and set(
                "".join(celulas[1]).replace("|", "")) <= set("-: ") else celulas[1:]
            t = ["<div class=\"rolagem\"><table>", "<thead><tr>"]
            t += [f"<th>{inline(c)}</th>" for c in cab]
            t.append("</tr></thead><tbody>")
            for linha_t in corpo:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in linha_t)
                         + "</tr>")
            t.append("</tbody></table></div>")
            out.append("".join(t))
            continue

        if re.match(r"^- ", linha):                              # lista
            itens = []
            while i < n and (re.match(r"^- ", linhas[i])
                             or (itens and linhas[i].startswith("  ")
                                 and linhas[i].strip())):
                if re.match(r"^- ", linhas[i]):
                    itens.append([linhas[i][2:].rstrip()])
                else:
                    itens[-1].append(linhas[i].strip())
                i += 1
            out.append("<ul>" + "".join(
                "<li>" + "<br>".join(inline(p.rstrip()) for p in it) + "</li>"
                for it in itens) + "</ul>")
            continue

        if re.match(r"^\d+\.\s", linha):                         # lista numerada
            itens = []
            while i < n and (re.match(r"^\d+\.\s", linhas[i])
                             or (itens and linhas[i].startswith("   ")
                                 and linhas[i].strip())):
                if re.match(r"^\d+\.\s", linhas[i]):
                    itens.append([re.sub(r"^\d+\.\s+", "", linhas[i]).rstrip()])
                else:
                    itens[-1].append(linhas[i].strip())
                i += 1
            out.append("<ol>" + "".join(
                "<li>" + " ".join(inline(p.rstrip()) for p in it) + "</li>"
                for it in itens) + "</ol>")
            continue

        if not linha.strip():                                    # linha vazia
            i += 1
            continue

        par = []                                                 # paragrafo
        while i < n and linhas[i].strip() and not linhas[i].startswith(
                ("|", "#", "- ", "```")) and not re.match(r"^\d+\.\s", linhas[i]):
            par.append(linhas[i])
            i += 1
        texto = ""
        for p in par:
            texto += inline(p.strip()) + ("<br>" if p.endswith("  ") else " ")
        out.append("<p>" + texto.strip() + "</p>")

    return "\n".join(out), toc


# -------------------------------------------------------------- numeros -------
def exige(padrao, texto, oque, flags=re.M):
    m = re.search(padrao, texto, flags)
    if not m:
        sys.exit(f"nao encontrei {oque} em resultado_caracteristicas.md - "
                 "o formato mudou; ajuste 12_relatorio_html.py")
    return m


def pt(txt):
    """97.5% -> 97,5% (a pagina e em pt-BR; o .md sai com ponto decimal)."""
    return re.sub(r"(\d)\.(\d)", r"\1,\2", txt)


def cartoes(md_res, conc):
    g = exige(r"^\|\s*geral\s*\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|"
              r"([^|]+)\|([^|]+)\|", md_res, "a linha de resumo")
    itens, rotulos, precisao, cobertura, erros, absteve, invencao = (
        x.strip() for x in g.groups())
    c = exige(r"Acerto de classe: \*\*(\d+)/(\d+)\*\*\s*\(([^)]*)\)", md_res,
              "o acerto de classe")
    p = exige(r"^\|\s*precisão\s*\|([^|]+)\|", md_res, "a precisao da juncao")
    r = exige(r"^\|\s*recall\s*\|([^|]+)\|", md_res, "o recall da juncao")
    kap = conc["global"]["kappa"]
    return {
        "hero": {"valor": pt(precisao.split("[")[0].strip()),
                 "ic": "IC 95% " + ("[" + pt(precisao.split("[")[1])
                                    if "[" in precisao else "—"),
                 "rotulos": rotulos, "itens": itens, "erros": erros},
        "tiles": [
            ("Cobertura", pt(cobertura),
             f"{absteve} rótulos DEFINIDO deixados vazios", "neutro"),
            ("Taxa de invenção", invencao.split("(")[-1].rstrip(")") or invencao,
             f"preencheu {invencao.split('/')[0]} dos "
             f"{invencao.split('/')[1].split()[0]} rótulos AUSENTE/INDEFINÍVEL",
             "serious"),
            ("Acerto de classe", pt(f"{int(c.group(1)) / int(c.group(2)):.1%}"),
             pt(f"{c.group(1)}/{c.group(2)} itens · {c.group(3)}"), "neutro"),
            ("Precisão da junção", pt(p.group(1).split("[")[0].strip()),
             pt(f"precisão {p.group(1).strip()} · recall {r.group(1).strip()}"),
             "neutro"),
            ("Kappa de Cohen A×B", pt(f"{kap:.3f}"),
             f"{conc['global']['n']} rótulos · "
             f"{conc['divergencias_adjudicadas']} divergências adjudicadas",
             "warning"),
        ],
    }


# ----------------------------------------------------------------- pagina -----
CSS = """
:root{color-scheme:light;
 --surface:#fcfcfb; --surface-2:#f4f3f0; --borda:#e2e0da;
 --ink:#0b0b0b; --ink-2:#52514e; --ink-3:#6f6e69;
 --accent:#2a78d6; --good:#0ca30c; --warning:#fab219; --serious:#ec835a;
 --critical:#d03b3b; --codigo:#f7f6f3;}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){
 color-scheme:dark;
 --surface:#1a1a19; --surface-2:#232322; --borda:#383835;
 --ink:#f0efec; --ink-2:#c3c2b7; --ink-3:#a3a29a;
 --accent:#3987e5; --codigo:#141413;}}
:root[data-theme=dark]{color-scheme:dark;
 --surface:#1a1a19; --surface-2:#232322; --borda:#383835;
 --ink:#f0efec; --ink-2:#c3c2b7; --ink-3:#a3a29a;
 --accent:#3987e5; --codigo:#141413;}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);
 font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.pagina{max-width:1180px;margin:0 auto;padding:0 24px 96px;
 display:grid;grid-template-columns:minmax(0,1fr);gap:0}
@media(min-width:1060px){.pagina{grid-template-columns:228px minmax(0,1fr);
 column-gap:48px;align-items:start}
 .topo,.cartoes,.aviso{grid-column:1/-1}
 nav.sumario{position:sticky;top:24px;max-height:calc(100vh - 48px);overflow:auto}}
.topo{padding:48px 0 24px;border-bottom:1px solid var(--borda);margin-bottom:32px}
h1{font-size:30px;line-height:1.25;margin:0 0 8px;letter-spacing:-.01em}
.subtitulo{color:var(--ink-2);margin:0;max-width:72ch;font-size:17px}
.meta{color:var(--ink-3);font-size:13px;margin-top:16px}
.meta code{font-size:12px}
.barra{display:flex;gap:8px;align-items:center;margin-top:20px;flex-wrap:wrap}
button{font:inherit;font-size:13px;color:var(--ink-2);background:var(--surface-2);
 border:1px solid var(--borda);border-radius:7px;padding:5px 11px;cursor:pointer}
button:hover{color:var(--ink);border-color:var(--ink-3)}
.cartoes{display:flex;flex-direction:column;gap:16px;margin:0 0 32px}
.tiles{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(182px,1fr))}
.hero,.tile{background:var(--surface-2);border:1px solid var(--borda);
 border-radius:12px;padding:18px 20px}
.hero{display:flex;flex-direction:column;gap:2px}
.rotulo{font-size:12px;letter-spacing:.04em;text-transform:uppercase;
 color:var(--ink-3);margin:0 0 6px}
.valor{font-size:52px;font-weight:600;line-height:1;margin:0;letter-spacing:-.02em}
.tile .valor{font-size:30px}
.nota{color:var(--ink-2);font-size:13px;margin:8px 0 0}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;
 color:var(--ink-2);margin-top:10px}
.ponto{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.ponto.serious{background:var(--serious)} .ponto.warning{background:var(--warning)}
.ponto.good{background:var(--good)} .ponto.neutro{background:var(--accent)}
.aviso{border:1px solid var(--borda);border-left:3px solid var(--warning);
 background:var(--surface-2);border-radius:8px;padding:16px 20px;margin:0 0 36px}
.aviso p{margin:0;color:var(--ink-2);font-size:14.5px}
.aviso strong{color:var(--ink)}
nav.sumario{font-size:13.5px;padding-top:4px}
nav.sumario p{font-size:12px;letter-spacing:.04em;text-transform:uppercase;
 color:var(--ink-3);margin:0 0 8px}
nav.sumario a{display:block;color:var(--ink-2);text-decoration:none;padding:3px 0}
nav.sumario a:hover{color:var(--accent)}
nav.sumario a.n3{padding-left:12px;color:var(--ink-3);font-size:12.5px}
main{min-width:0}
h2{font-size:23px;margin:48px 0 12px;letter-spacing:-.01em;
 padding-top:16px;border-top:1px solid var(--borda)}
h3{font-size:17.5px;margin:32px 0 10px}
h4{font-size:15px;margin:24px 0 8px;color:var(--ink-2)}
p,li{color:var(--ink-2)} li{margin:4px 0}
strong{color:var(--ink);font-weight:600}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-size:.88em;background:var(--codigo);border:1px solid var(--borda);
 border-radius:4px;padding:1px 4px}
.rolagem{overflow-x:auto;margin:16px 0;border:1px solid var(--borda);
 border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px;
 font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--borda);
 white-space:nowrap}
th{background:var(--surface-2);color:var(--ink);font-weight:600;font-size:12.5px;
 position:sticky;top:0}
tbody tr:last-child td{border-bottom:0}
td code{white-space:nowrap}
pre.bloco{background:var(--codigo);border:1px solid var(--borda);border-radius:10px;
 padding:16px 18px;overflow-x:auto;font-size:13px;line-height:1.55;margin:16px 0}
pre.bloco code{background:none;border:0;padding:0;font-size:13px}
details.fonte{border:1px solid var(--borda);border-radius:10px;margin:12px 0;
 background:var(--surface-2)}
details.fonte>summary{cursor:pointer;padding:12px 16px;font-size:14px;
 color:var(--ink);font-weight:600;display:flex;gap:10px;align-items:baseline}
details.fonte>summary span{color:var(--ink-3);font-weight:400;font-size:12.5px}
details.fonte[open]>summary{border-bottom:1px solid var(--borda)}
details.fonte pre.bloco{margin:0;border:0;border-radius:0 0 10px 10px;
 max-height:620px}
.copiar{float:right;margin:-2px 0 0}
footer{margin-top:64px;padding-top:24px;border-top:1px solid var(--borda);
 color:var(--ink-3);font-size:13px}
@media print{nav.sumario,.barra{display:none}details.fonte{break-inside:avoid}
 details.fonte[open] pre.bloco{max-height:none}}
"""

JS = """
const alvo=document.documentElement;
const salvo=localStorage.getItem('tema');
if(salvo){alvo.dataset.theme=salvo;}
document.getElementById('tema').addEventListener('click',()=>{
  const escuro=getComputedStyle(document.body).backgroundColor==='rgb(26, 26, 25)';
  const novo=escuro?'light':'dark';
  alvo.dataset.theme=novo;localStorage.setItem('tema',novo);
});
document.querySelectorAll('[data-copiar]').forEach(b=>{
  b.addEventListener('click',async()=>{
    const pre=document.getElementById(b.dataset.copiar);
    try{await navigator.clipboard.writeText(pre.innerText);
        const t=b.textContent;b.textContent='copiado';
        setTimeout(()=>b.textContent=t,1400);}
    catch(e){const r=document.createRange();r.selectNodeContents(pre);
        const s=getSelection();s.removeAllRanges();s.addRange(r);}
  });
});
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(RAIZ / "relatorio_caracteristicas.html"))
    args = ap.parse_args()

    md_gab = (RAIZ / "GABARITO_CARACTERISTICAS.md").read_text(encoding="utf-8")
    md_res = (RAIZ / "resultado_caracteristicas.md").read_text(encoding="utf-8")
    conc = json.loads((RAIZ / "concordancia_caracteristicas.json").read_text("utf-8"))

    # o h1 de cada .md vira titulo de secao da pagina
    md_gab = re.sub(r"^# .*\n", "", md_gab, count=1)
    md_res = re.sub(r"^# .*\n", "", md_res, count=1)
    html_gab, toc_gab = md_para_html(md_gab, "gab")
    html_res, toc_res = md_para_html(md_res, "res")

    k = cartoes(md_res, conc)
    tamanhos = {nome: len((RAIZ / nome).read_text(encoding="utf-8").splitlines())
                for nome in FONTES}
    n_revisao = sum(1 for _ in csv.reader(
        (RAIZ / "revisao_humana_caracteristicas.csv").open(encoding="utf-8"))) - 1
    n_gold = {nome: sum(1 for _ in csv.reader(
        (RAIZ / nome).open(encoding="utf-8"))) - 1
        for nome in ("gold_caracteristicas.csv", "gold_classe.csv", "gold_juncao.csv")}

    # --- sumario ---
    sec = [("sec-gabarito", "Gabarito: método e limitações", toc_gab),
           ("sec-resultado", "Resultado da avaliação", toc_res),
           ("sec-reproduzir", "Reproduzir",
            [(3, "rep-comandos", "Os cinco passos"),
             (3, "rep-fontes", "Os quatro scripts, por inteiro")])]
    nav = ["<nav class=\"sumario\"><p>Nesta página</p>",
           "<a href=\"#topo\">Resumo</a>"]
    for ident, titulo, toc in sec:
        nav.append(f"<a href=\"#{ident}\"><strong>{html.escape(titulo)}</strong></a>")
        for nivel, i2, texto in toc:
            if nivel == 3:
                nav.append(f"<a class=\"n3\" href=\"#{i2}\">{html.escape(texto)}</a>")
    nav.append("</nav>")

    # --- cartoes ---
    cards = [f"""<div class="hero"><p class="rotulo">Precisão das características</p>
<p class="valor">{html.escape(k['hero']['valor'])}</p>
<p class="nota">{html.escape(k['hero']['ic'])} · {html.escape(k['hero']['rotulos'])}
 rótulos em {html.escape(k['hero']['itens'])} itens ·
 {html.escape(k['hero']['erros'])} erros de valor</p>
<span class="chip"><span class="ponto neutro"></span>acertos / (acertos + erros),
 só onde o gold diz DEFINIDO</span></div>"""]
    for rotulo, valor, nota, cor in k["tiles"]:
        cards.append(f"""<div class="tile"><p class="rotulo">{html.escape(rotulo)}</p>
<p class="valor">{html.escape(valor)}</p>
<p class="nota">{html.escape(nota)}</p>
<span class="chip"><span class="ponto {cor}"></span>{
 'atenção' if cor in ('serious', 'warning') else 'medido contra o gold'}</span></div>""")

    # --- codigo embutido ---
    blocos = [f"""<h3 id="rep-comandos">Os cinco passos</h3>
<p>Copie e rode na raiz do repositório. O <code>.venv</code> do projeto não tem
pandas, por isso tudo passa por <code>uv</code>.</p>
<pre class="bloco" id="cmd"><button class="copiar" data-copiar="cmd">copiar</button>
<code>{html.escape(COMANDOS)}</code></pre>
<h3 id="rep-fontes">Os quatro scripts, por inteiro</h3>
<p>Cada bloco abre com o arquivo completo, como está em <code>avaliacao/</code>.
Juntos, mais os dois <code>.xlsx</code> de <code>dados/</code> e as duas anotações
<code>.jsonl</code>, reproduzem todos os números desta página.</p>"""]
    for nome in FONTES:
        fonte = (RAIZ / nome).read_text(encoding="utf-8")
        ident = "src-" + re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-")
        papel = {
            "10_candidatos_caracteristicas.py": "seleção dos 240 itens e dos 150 pares",
            "11_adjudicar_caracteristicas.py": "adjudicação A×B, kappa e gold",
            "evaluate_caracteristicas.py": "avaliação do pipeline e geração do .md",
            "12_relatorio_html.py": "este relatório",
        }[nome]
        blocos.append(f"""<details class="fonte"><summary>{html.escape(nome)}
 <span>{papel} · {tamanhos[nome]} linhas</span></summary>
<pre class="bloco" id="{ident}"><button class="copiar" data-copiar="{ident}">copiar</button>
<code>{html.escape(fonte)}</code></pre></details>""")

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    pagina = f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conjunto-ouro de características, classe e junção — Serra Azul</title>
<style>{CSS}</style></head><body>
<div class="pagina">
<header class="topo" id="topo">
<h1>Conjunto-ouro das características técnicas, da classe e da junção</h1>
<p class="subtitulo">A régua independente do pipeline de saneamento de cadastro:
como foi construída, o que ela diz sobre a execução atual e o código que
reproduz os dois.</p>
<p class="meta">{n_gold['gold_caracteristicas.csv']} rótulos de atributo ·
{n_gold['gold_classe.csv']} rótulos de classe ·
{n_gold['gold_juncao.csv']} pares · gerado em {agora} ·
repositório <code>/home/igor-alves/clas/hack/vxwinners</code></p>
<div class="barra"><button id="tema">claro / escuro</button></div>
</header>

<div class="cartoes">{cards[0]}<div class="tiles">{''.join(cards[1:])}</div></div>

<div class="aviso"><p><strong>Leia junto com os números:</strong> as duas
anotações independentes (A e B) saíram do mesmo modelo, em passadas separadas,
com ordens diferentes e sem reabrir a saída da outra — não são anotadores
independentes de verdade. O kappa de {pt(f"{conc['global']['kappa']:.3f}")} mede
consistência interna, não confiabilidade entre humanos. A planilha
<code>revisao_humana_caracteristicas.csv</code> ({n_revisao} linhas) faz parte do
entregável por isso, e a amostra é estratificada para concentrar armadilhas:
as taxas acima são o desempenho nos casos difíceis, não uma estimativa da base
inteira.</p></div>

{''.join(nav)}

<main>
<h2 id="sec-gabarito">Gabarito: método e limitações</h2>
{html_gab}

<h2 id="sec-resultado">Resultado da avaliação</h2>
{html_res}

<h2 id="sec-reproduzir">Reproduzir</h2>
{''.join(blocos)}

<footer>Gerado por <code>avaliacao/12_relatorio_html.py</code> a partir de
<code>GABARITO_CARACTERISTICAS.md</code>,
<code>resultado_caracteristicas.md</code> e
<code>concordancia_caracteristicas.json</code>. Os números dos cartões são lidos
desses arquivos; nenhum valor é digitado no gerador.</footer>
</main>
</div>
<script>{JS}</script>
</body></html>
"""
    Path(args.saida).write_text(pagina, encoding="utf-8")
    print(f"{args.saida} gravado ({len(pagina) / 1024:.0f} KB, "
          f"{sum(tamanhos.values())} linhas de codigo embutidas)")


if __name__ == "__main__":
    main()
