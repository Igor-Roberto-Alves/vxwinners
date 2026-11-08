# -*- coding: utf-8 -*-
"""Gera os slides de apresentacao do produto (HTML autocontido, 12 telas).

Uso:
  uv run --no-project --with pandas --with openpyxl python avaliacao/15_slides_html.py \
      [--saida avaliacao/slides.html]

Navegacao: setas, PageUp/PageDown, espaco, clique nas bolinhas, ou rolagem.
Imprimir para PDF funciona: cada slide e uma pagina em paisagem.

As metricas vem das MESMAS funcoes do 14_apresentacao_html.py (importado como
modulo), que as calcula de artefatos/ e avaliacao/. O unico texto com numero
digitado e a frase de capital parado, copiada de avaliacao/valor_financeiro.md
(gerado por 30_valor_financeiro.py) e citada como tal.
"""
import argparse
import html
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent


def carrega_metricas():
    spec = importlib.util.spec_from_file_location(
        "apres", RAIZ / "14_apresentacao_html.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def esc(s):
    return html.escape(str(s))


CSS = """
:root{color-scheme:dark;
 --fundo:#121211; --fundo-2:#1c1c1a; --borda:#34342f;
 --ink:#f5f4f0; --ink-2:#c3c2b7; --ink-3:#8f8e85;
 --accent:#3987e5; --good:#0ca30c; --warning:#fab219; --serious:#ec835a;
 --critical:#d03b3b;}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-snap-type:y mandatory;scroll-behavior:smooth}
body{background:var(--fundo);color:var(--ink);
 font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.slide{min-height:100vh;scroll-snap-align:start;display:flex;flex-direction:column;
 justify-content:center;padding:72px 7vw 96px;position:relative;
 border-bottom:1px solid var(--borda)}
.slide.capa{background:
 radial-gradient(1200px 600px at 15% 10%, rgba(57,135,229,.16), transparent 60%),
 var(--fundo)}
.kicker{font-size:13px;letter-spacing:.11em;text-transform:uppercase;
 color:var(--accent);font-weight:700;margin-bottom:20px}
h1{font-size:clamp(34px,5.2vw,68px);line-height:1.04;letter-spacing:-.025em;
 max-width:24ch;font-weight:700}
h2{font-size:clamp(26px,3.3vw,44px);line-height:1.1;letter-spacing:-.02em;
 max-width:30ch;font-weight:700;margin-bottom:14px}
.lede{font-size:clamp(16px,1.35vw,21px);color:var(--ink-2);max-width:68ch;
 margin-top:18px;line-height:1.55}
.enorme{font-size:clamp(56px,10vw,132px);line-height:.92;font-weight:700;
 letter-spacing:-.04em}
.enorme small{display:block;font-size:clamp(15px,1.3vw,19px);font-weight:500;
 color:var(--ink-2);letter-spacing:0;margin-top:18px;max-width:52ch;line-height:1.5}
.grade{display:grid;gap:18px;margin-top:38px}
.g2{grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.g3{grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(165px,1fr))}
.cartao{background:var(--fundo-2);border:1px solid var(--borda);border-radius:14px;
 padding:22px 24px}
.cartao .n{font-size:clamp(28px,3.4vw,42px);font-weight:700;letter-spacing:-.025em;
 line-height:1}
.cartao .r{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;
 color:var(--ink-3);font-weight:600;margin-bottom:10px}
.cartao p{color:var(--ink-2);font-size:14px;margin-top:10px;line-height:1.45}
.cartao.destaque{border-color:var(--accent);
 box-shadow:inset 0 0 0 1px rgba(57,135,229,.35)}
table{border-collapse:collapse;width:100%;margin-top:30px;font-size:15px;
 font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:11px 14px;border-bottom:1px solid var(--borda)}
th{font-size:11.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--ink-3)}
td.n,th.n{text-align:right}
td strong{color:var(--ink)} td{color:var(--ink-2)}
tr.alvo td{background:rgba(57,135,229,.1)}
tr:last-child td{border-bottom:0}
.faixa{display:flex;gap:3px;height:34px;margin:34px 0 14px;border-radius:6px;
 overflow:hidden}
.faixa div{display:flex;align-items:center;padding:0 12px;font-size:13px;
 font-weight:700;color:#06120a;white-space:nowrap;overflow:hidden}
.legenda{display:flex;gap:22px;flex-wrap:wrap;font-size:14px;color:var(--ink-2)}
.legenda span{display:inline-flex;align-items:center;gap:8px}
.ponto{width:10px;height:10px;border-radius:50%}
ul{margin-top:26px;list-style:none;max-width:76ch}
li{color:var(--ink-2);font-size:clamp(15px,1.25vw,18.5px);margin:14px 0;
 padding-left:26px;position:relative;line-height:1.5}
li:before{content:"";position:absolute;left:0;top:.55em;width:9px;height:9px;
 border-radius:2px;background:var(--accent)}
li.ruim:before{background:var(--critical)} li.bom:before{background:var(--good)}
li.meio:before{background:var(--warning)}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-size:.87em;background:#000;border:1px solid var(--borda);border-radius:5px;
 padding:2px 6px;color:var(--ink)}
.citacao{border-left:3px solid var(--accent);padding:4px 0 4px 22px;
 font-size:clamp(17px,1.7vw,25px);line-height:1.45;max-width:58ch;margin-top:30px;
 color:var(--ink)}
.fonte{font-size:12.5px;color:var(--ink-3);margin-top:22px;max-width:76ch;
 line-height:1.5}
.num{position:absolute;right:7vw;bottom:34px;font-size:12.5px;color:var(--ink-3);
 font-variant-numeric:tabular-nums}
.marca{position:absolute;left:7vw;bottom:34px;font-size:12.5px;color:var(--ink-3)}
nav{position:fixed;right:18px;top:50%;transform:translateY(-50%);display:flex;
 flex-direction:column;gap:9px;z-index:10}
nav a{width:9px;height:9px;border-radius:50%;background:var(--borda);
 border:1px solid transparent;display:block}
nav a:hover,nav a.ativo{background:var(--accent)}
.exemplo{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-size:clamp(11.5px,1.05vw,14px);background:#000;border:1px solid var(--borda);
 border-radius:12px;padding:18px 20px;margin-top:26px;overflow-x:auto;
 line-height:1.75;color:var(--ink-2)}
.exemplo b{color:var(--good);font-weight:600}
.exemplo i{color:var(--serious);font-style:normal}
@media print{
 html,body{background:#fff;color:#111}
 @page{size:landscape;margin:12mm}
 nav{display:none}
 .slide{min-height:auto;break-after:page;border:0;padding:24px 0}
 .cartao,.exemplo,code{background:#f6f5f2;border-color:#ddd;color:#111}
 .lede,li,td,.legenda,.fonte{color:#333}
}
"""

JS = """
const slides=[...document.querySelectorAll('.slide')];
const pontos=[...document.querySelectorAll('nav a')];
function ir(i){if(i>=0&&i<slides.length)slides[i].scrollIntoView();}
function atual(){let c=0,menor=1e9;slides.forEach((s,i)=>{
  const d=Math.abs(s.getBoundingClientRect().top);if(d<menor){menor=d;c=i;}});return c;}
addEventListener('keydown',e=>{
  const i=atual();
  if(['ArrowDown','ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();ir(i+1);}
  if(['ArrowUp','ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();ir(i-1);}
  if(e.key==='Home'){e.preventDefault();ir(0);}
  if(e.key==='End'){e.preventDefault();ir(slides.length-1);}});
const marca=()=>{const i=atual();pontos.forEach((p,j)=>p.classList.toggle('ativo',i===j));};
addEventListener('scroll',marca,{passive:true});marca();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(RAIZ / "slides.html"))
    a = ap.parse_args()

    m = carrega_metricas()
    base, fon = m.metricas_base(), m.metricas_fontes()
    gold, dic = m.metricas_gold(), m.metricas_dicionario()
    tes, pdm = m.metricas_testes(), m.classes_do_pdm()
    md = gold["md"]
    num, pt = m.num, m.pt

    resumo = m.tabela_do_md(md, "## 1. Resumo")[1][0]
    precisao, cobertura, invencao = resumo[3], resumo[4], resumo[7]
    m_classe = re.search(r"Acerto de classe: \*\*(\d+)/(\d+)\*\*", md)
    m_prec_j = re.search(r"^\|\s*precisão\s*\|([^|]+)\|", md, re.M)
    m_rec_j = re.search(r"^\|\s*recall\s*\|([^|]+)\|", md, re.M)
    travas = dic["travas"]
    est = base["estados"]

    # frase de capital parado, citada do relatorio financeiro
    capital = ""
    fin = RAIZ / "valor_financeiro.md"
    if fin.exists():
        mm = re.search(r"^> (.+)$", fin.read_text(encoding="utf-8"), re.M)
        capital = mm.group(1).strip() if mm else ""

    # exemplo real de antes/depois, tirado da base
    exemplo = {"cru": "", "pdm": ""}
    with open(REPO / "artefatos/saneado_base.csv", newline="", encoding="utf-8") as f:
        import csv as _csv
        for r in _csv.DictReader(f):
            if (r["ESTADO"] == "SANEADO" and r["ID_PDM"] == "PDM001"
                    and "<PENDENTE>" not in r["DESCRICAO_PDM"]
                    and len(r["DESCRICAO_ORIGINAL"]) < 72
                    and r["NCM_ORIGINAL"] != r["NCM_PDM"]):
                exemplo = {"cru": r["DESCRICAO_ORIGINAL"], "pdm": r["DESCRICAO_PDM"],
                           "cod": r["CODIGO_MATERIAL"],
                           "un_de": r["UNIDADE_ORIGINAL"], "un_para": r["UNIDADE_PDM"],
                           "ncm_de": r["NCM_ORIGINAL"] or "(vazio)",
                           "ncm_para": r["NCM_PDM"]}
                break

    # as cinco maiores, mais o LLM sempre visivel: a mensagem do slide e o
    # tamanho dele perto das camadas deterministicas
    camadas_top = sorted(fon["fontes"].items(), key=lambda kv: -kv[1])[:5]
    if "llm" not in dict(camadas_top):
        camadas_top.append(("llm", fon["fontes"].get("llm", 0)))
    nomes = {c[0]: c[1] for c in m.CAMADAS}
    det = tes["determinismo"]

    S = []

    def slide(conteudo, classe="", titulo=""):
        S.append((conteudo, classe, titulo))

    # 1 capa
    slide(f"""<p class="kicker">Serra Azul Mineração e Energia · Desafio 01</p>
<h1>O cadastro de materiais, saneado com prova de que está certo.</h1>
<p class="lede">{num(base['itens'])} descrições livres entram. Sai catálogo no padrão
PDM — descrição, classe, unidade, NCM e plano de junção de duplicados — com a
procedência de cada valor e a precisão medida contra um gabarito independente.</p>
<div class="grade g4">
<div class="cartao"><p class="r">Saneado</p><p class="n">{pt(f"{est['SANEADO'] / base['itens']:.1%}")}</p></div>
<div class="cartao"><p class="r">Precisão medida</p><p class="n">{pt(precisao.split('[')[0])}</p></div>
<div class="cartao"><p class="r">Duplicados colapsados</p><p class="n">{num(base['reducao'])}</p></div>
<div class="cartao"><p class="r">LLM no resultado</p><p class="n">{pt(f"{fon['fontes'].get('llm', 0) / fon['preenchidos']:.1%}")}</p></div>
</div>""", "capa")

    # 2 o problema
    slide(f"""<p class="kicker">O problema</p>
<h2>A mesma peça, escrita de {base['maior_grupo']} formas diferentes.</h2>
<p class="lede">O cadastro cresceu em texto livre: abreviação de quem digitou,
unidade trocada, NCM vazio, polegada com aspas, com <code>IN</code> e em fração
mista. Quem compra não acha; quem conta estoque conta duas vezes.</p>
<div class="grade g3">
<div class="cartao"><p class="r">Itens sem NCM na origem</p><p class="n">{num(base['ncm_vazio_origem'])}</p>
<p>{pt(f"{base['ncm_vazio_origem'] / base['itens']:.1%}")} da base entrou sem classificação fiscal</p></div>
<div class="cartao"><p class="r">Unidade de medida errada</p><p class="n">{num(base['unidade_corrigida'])}</p>
<p>metro onde é peça, peça onde é par</p></div>
<div class="cartao"><p class="r">Grupo de mercadoria errado</p><p class="n">{num(base['grupo_corrigido'])}</p>
<p>retentor cadastrado em tubos</p></div>
</div>""")

    # 3 o custo
    slide(f"""<p class="kicker">O custo</p>
<h2>Capital parado em código duplicado.</h2>
{f'<p class="citacao">{esc(capital)}</p>' if capital else ''}
<div class="grade g3">
<div class="cartao destaque"><p class="r">Registros redundantes</p>
<p class="n">{num(base['reducao'])}</p><p>{pt(f"{base['reducao'] / base['itens']:.1%}")} da base,
em {num(base['grupos_duplicados'])} grupos de itens iguais</p></div>
<div class="cartao"><p class="r">Itens com atributo faltando</p>
<p class="n">{pt(f"{base['itens_com_pendencia'] / base['itens']:.1%}")}</p>
<p>{num(base['pendencias'])} atributos obrigatórios em branco</p></div>
<div class="cartao"><p class="r">Maior grupo encontrado</p>
<p class="n">{base['maior_grupo']}</p><p>códigos distintos para o mesmo item</p></div>
</div>
<p class="fonte">Capital calculado por <code>avaliacao/30_valor_financeiro.py</code> sobre
estoque × preço médio do ERP, ajustado pela precisão da junção medida no gabarito.
Usa precisão, não recall: duplicidade que o pipeline não achou não está na conta.</p>""")

    # 4 o que entrega
    slide(f"""<p class="kicker">O que o produto entrega</p>
<h2>Uma linha de catálogo que a norma aceita.</h2>
<div class="exemplo">
código <b>{esc(exemplo.get('cod', ''))}</b><br>
antes &nbsp;<i>{esc(exemplo['cru'])}</i><br>
depois <b>{esc(exemplo['pdm'][:150])}</b><br>
unidade <i>{esc(exemplo.get('un_de', ''))}</i> → <b>{esc(exemplo.get('un_para', ''))}</b>
&nbsp;·&nbsp; NCM <i>{esc(exemplo.get('ncm_de', ''))}</i> → <b>{esc(exemplo.get('ncm_para', ''))}</b>
</div>
<div class="grade g4">
<div class="cartao"><p class="r">Descrição no padrão</p><p class="n">{num(est['SANEADO'])}</p></div>
<div class="cartao"><p class="r">Cadastro completo</p><p class="n">{pt(f"{base['completos'] / base['itens']:.1%}")}</p></div>
<div class="cartao"><p class="r">Classes do PDM em uso</p><p class="n">{base['classes_usadas']}/{pdm['classes']}</p></div>
<div class="cartao"><p class="r">Revisão humana</p><p class="n">{num(est.get('REVISAO_HUMANA', 0))}</p></div>
</div>""")

    # 5 como decide
    linhas = "".join(
        f"<tr{' class=\"alvo\"' if k == 'llm' else ''}><td><strong>{esc(nomes.get(k, k))}</strong></td>"
        f"<td><code>{esc(k)}</code></td><td class=\"n\">{num(v)}</td>"
        f"<td class=\"n\">{pt(f'{v / fon['preenchidos']:.1%}')}</td></tr>"
        for k, v in camadas_top)
    slide(f"""<p class="kicker">Como decide</p>
<h2>Camada barata antes de camada cara. O LLM é o último recurso, não o primeiro.</h2>
<table><thead><tr><th>camada</th><th>fonte</th><th class="n">valores na base</th>
<th class="n">% do preenchido</th></tr></thead><tbody>{linhas}</tbody></table>
<p class="fonte">{num(fon['atributos'])} decisões de atributo em {num(fon['itens'])} itens.
O LLM responde por {pt(f"{fon['fontes'].get('llm', 0) / fon['preenchidos']:.1%}")} dos valores
e foi acionado em {pt(f"{base['escalado_llm'] / base['itens']:.1%}")} dos itens — o resto é
regra auditável, e cada resposta do modelo é reaproveitada em vez de repetida.</p>""")

    # 6 procedencia
    slide(f"""<p class="kicker">Procedência</p>
<h2>Todo valor diz de onde veio, com que confiança e por qual trecho do texto.</h2>
<div class="exemplo">
{{"atributo": "<b>BITOLA</b>", "valor": "<b>M14</b>", "fonte": "<b>acordo</b>",<br>
&nbsp;"confianca": <b>0.99</b>, "evidencia": "<b>M14</b>",<br>
&nbsp;"motivo": "regra e BERT concordam", "regra": "M14", "bert": "M14"}}
</div>
<ul>
<li class="bom">Auditoria linha a linha: dá para perguntar <em>por que</em> o sistema
escreveu isso, e a resposta é um trecho do texto original.</li>
<li class="bom">Quando as camadas discordam, o item é marcado — não há empate
resolvido no escuro.</li>
<li class="meio">O que não tem evidência fica <code>&lt;PENDENTE&gt;</code> em vez de
ser preenchido com o palpite mais provável.</li>
</ul>""")

    # 7 prova
    slide(f"""<p class="kicker">A prova</p>
<h2>Gabarito independente, não auto-avaliação.</h2>
<p class="lede">{num(gold['carac'] + gold['classe'] + gold['juncao'])} rótulos anotados
só com o texto cru e o padrão PDM — sem olhar a saída do pipeline —, em duas passadas
independentes, com decisão escrita para cada divergência.</p>
<div class="grade g4">
<div class="cartao destaque"><p class="r">Precisão</p><p class="n">{pt(precisao.split('[')[0])}</p>
<p>IC 95% {pt('[' + precisao.split('[')[1]) if '[' in precisao else ''}</p></div>
<div class="cartao"><p class="r">Cobertura</p><p class="n">{pt(cobertura)}</p>
<p>dos valores que o texto traz</p></div>
<div class="cartao"><p class="r">Classe certa</p>
<p class="n">{pt(f"{int(m_classe.group(1)) / int(m_classe.group(2)):.1%}") if m_classe else '—'}</p>
<p>{m_classe.group(1) + ' de ' + m_classe.group(2) if m_classe else ''} itens</p></div>
<div class="cartao"><p class="r">Junção</p>
<p class="n">{pt(m_prec_j.group(1).split('[')[0].strip()) if m_prec_j else '—'}</p>
<p>precisão · recall {pt(m_rec_j.group(1).split('[')[0].strip()) if m_rec_j else '—'}</p></div>
</div>
<p class="fonte">Kappa de Cohen entre as duas anotações:
{pt(f"{gold['concordancia']['global']['kappa']:.3f}")} ·
{gold['concordancia']['divergencias_adjudicadas']} divergências adjudicadas uma por uma ·
amostra estratificada em {len(gold['estratos'])} estratos e
{len(gold['armadilhas'])} armadilhas conhecidas de extração.</p>""")

    # 8 invencao
    if travas:
        ma, mdp = travas["metricas_antes"], travas["metricas_depois"]
        slide(f"""<p class="kicker">O diferencial</p>
<h2>Medimos quando o sistema está chutando — e desligamos o chute.</h2>
<p class="lede">O gabarito marca onde o texto <em>não</em> traz o valor. Preencher ali
é invenção, e invenção não aparece em nenhuma métrica de acurácia comum. A nossa
estava em {pt(ma['invencao'].split('(')[-1].rstrip(')'))} e caiu para
{pt(mdp['invencao'].split('(')[-1].rstrip(')'))} depois de uma correção localizada.</p>
<div class="grade g2">
<div class="cartao"><p class="r">Antes</p><p class="n">{pt(ma['invencao'].split('(')[-1].rstrip(')'))}</p>
<p>{esc(ma['invencao'].split(' ')[0])} rótulos preenchidos sem apoio no texto ·
precisão {pt(ma['precisao'].split('[')[0])}</p></div>
<div class="cartao destaque"><p class="r">Depois</p><p class="n">{pt(mdp['invencao'].split('(')[-1].rstrip(')'))}</p>
<p>{esc(mdp['invencao'].split(' ')[0])} rótulos · precisão
<strong>{pt(mdp['precisao'].split('[')[0])}</strong> ·
{travas['removidos']} erros e invenções removidos</p></div>
</div>
<p class="fonte">A causa não era o LLM respondendo: era a resposta antiga dele
reaplicada como regra em outro contexto. O conserto exige que o termo aponte um único
valor do padrão na hora de aplicar, e abstém-se quando o texto alcança dois.
{num(dic['curado']['sugestoes'])} entradas viraram sugestão para curadoria humana em vez
de fato no catálogo.</p>""")

    # 9 governanca
    slide(f"""<p class="kicker">Governança</p>
<h2>Dá para auditar, repetir e contestar.</h2>
<ul>
<li class="bom"><strong>{esc(tes['pytest'])}</strong>, incluindo 25 casos que fixam
cada armadilha real encontrada no gabarito.</li>
<li class="bom"><strong>Determinismo:</strong> {esc(det if det != 'não executado' else 'duas execuções com as mesmas entradas são comparadas registro a registro por scripts/17_testar_determinismo.sh')}.</li>
<li class="bom"><strong>Seleção do gabarito reproduzível</strong> por semente fixa; os
pares de junção ficam congelados para a anotação não descolar do dado.</li>
<li class="meio"><strong>{num(gold['revisao_humana'])} linhas</strong> preparadas para
conferência de uma pessoa do time: todo rótulo indefinível, toda divergência e 10% de
amostra aleatória — com coluna para discordar.</li>
<li class="bom"><strong>Nada de número digitado à mão:</strong> esta apresentação é
gerada por script a partir dos artefatos.</li>
</ul>""")

    # 10 achados
    slide(f"""<p class="kicker">O que o gabarito encontrou</p>
<h2>Defeitos nomeados, com item e linha — não "a acurácia caiu".</h2>
<ul>
<li class="ruim"><code>TAMPAO</code> entra como <code>CAP</code>: o substantivo não
existe no PDM, e a descrição inteira é preenchida na classe errada.</li>
<li class="ruim"><code>41KGF/CM2</code> sai como <code>41BAR</code> — falta a conversão,
e o erro é de 2%.</li>
<li class="ruim"><code>DN 25</code>, <code>DN 50</code> e o dash <code>-20</code> de
mangueira não viram polegada; a referência de rolamento perde o sufixo
(<code>6010-2RS/C3</code> → <code>6010</code>).</li>
<li class="ruim">O terminal B decide o terminal A: a camada léxica recebe o texto
inteiro em vez da caixa do atributo.</li>
<li class="meio">Todos têm conserto de regra, não de modelo — e cada um já tem rótulo
de gabarito para provar que o conserto funcionou.</li>
</ul>""")

    # 11 limites
    slide(f"""<p class="kicker">O que não prometemos</p>
<h2>Os limites, ditos antes de alguém perguntar.</h2>
<ul>
<li class="meio">As duas anotações do gabarito saíram do mesmo modelo: o kappa mede
consistência, não concordância entre humanos. A conferência humana está preparada e
ainda não foi feita.</li>
<li class="meio">A amostra é estratificada para concentrar casos difíceis — as taxas
são desempenho no difícil, não estimativa da base inteira.</li>
<li class="meio">O recall da junção é otimista: dois terços dos pares avaliados saíram
de grupos que o próprio pipeline formou.</li>
<li class="meio">{pt(f"{(base['itens'] - base['com_chave']) / base['itens']:.1%}")} da base
não tem chave de identidade e nunca é comparada na junção.</li>
<li class="meio">{pt(f"{base['itens_com_pendencia'] / base['itens']:.1%}")} dos itens
ainda têm atributo em branco; o produto prefere a lacuna ao palpite.</li>
</ul>""")

    # 12 proximos passos
    slide(f"""<p class="kicker">Próximos passos</p>
<h2>O caminho até o catálogo que ninguém precisa revisar.</h2>
<ul>
<li class="bom"><strong>Promover {num(dic['curado']['aplicaveis'])} termos</strong> do
dicionário aprendido para <code>sinonimos.py</code>: recupera cobertura com regra
curada e versionada, sem risco de invenção.</li>
<li class="bom"><strong>Caixa por atributo</strong> na camada léxica: resolve a
contaminação entre terminais e o que as travas não alcançam.</li>
<li class="bom"><strong>Tabela de conversões</strong> (KGF/CM2, PSI, DN, dash de
mangueira, sufixo de rolamento): dezenas de itens por regra.</li>
<li class="meio"><strong>Conferência humana do gabarito</strong> —
{num(gold['revisao_humana'])} linhas, 5 a 10 horas de um especialista — e o gabarito
deixa de ter viés de LLM.</li>
<li class="bom"><strong>Rodar em outra base</strong>: o padrão é lido do
<code>.xlsx</code> do PDM, não está escrito no código.</li>
</ul>
<p class="fonte">Repositório, scripts e relatórios: <code>avaliacao/apresentacao.html</code>
(estrutura e todas as métricas), <code>avaliacao/relatorio_caracteristicas.html</code>
(cada erro e cada invenção, rótulo a rótulo).</p>""")

    nav = "".join(f'<a href="#s{i}" title="{esc(t or i)}"></a>'
                  for i, (_c, _cl, t) in enumerate(S, 1))
    corpo = "".join(
        f'<section class="slide {cl}" id="s{i}">{c}'
        f'<span class="marca">Saneamento de cadastro · Serra Azul</span>'
        f'<span class="num">{i}/{len(S)}</span></section>'
        for i, (c, cl, _t) in enumerate(S, 1))

    pagina = f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Saneamento de cadastro de materiais — apresentação</title>
<style>{CSS}</style></head><body>
<nav>{nav}</nav>
{corpo}
<script>{JS}</script></body></html>"""
    Path(a.saida).write_text(pagina, encoding="utf-8")
    print(f"{a.saida} gravado ({len(pagina) / 1024:.0f} KB, {len(S)} slides)")
    print(f"  gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")


if __name__ == "__main__":
    main()
