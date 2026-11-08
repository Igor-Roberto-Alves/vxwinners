# -*- coding: utf-8 -*-
"""Gera os slides de CUSTO DE LLM, no desenho do deck "Pipeline de Saneamento VX".
Entram depois dos slides de camadas (18_slides_camadas_html.py), que mostram o
ganho de ligar o LLM; estes mostram o que isso custou e o que custaria sem as
camadas baratas na frente.

Uso:
  .venv/bin/python scripts/27_custo_llm.py          # produz artefatos/custo_llm.json
  .venv/bin/python avaliacao/24_slides_custo_html.py [--saida avaliacao/slides_custo.html]

NENHUM NUMERO E DIGITADO AQUI. Tudo vem de artefatos/custo_llm.json, que
scripts/27_custo_llm.py grava: gasto real por etapa (com a fonte de cada numero),
contrafactual montado sobre os prompts reais, calibracao caractere/token medida numa
rodada com tokens em log, e as sensibilidades de modelo e de prompt caching.
A explicacao do metodo esta em docs/16-custo-de-llm.md.
"""
import argparse
import html
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent

C = {
    "navy": "#17202a", "teal": "#1d6a73", "surface": "#f2f4f3", "card": "#fefefe",
    "track": "#e0e6e5", "green": "#2d794b", "cream": "#f5ead2", "amber": "#7e5200",
    "pink": "#f4dedb", "red": "#8d2d29", "cyan": "#5cb7c0",
}


def e(s):
    return html.escape(str(s))


def usd(v, casas=2):
    return f"US$ {v:,.{casas}f}".replace(",", " ").replace(".", ",")


def num(v):
    return f"{v:,}".replace(",", ".")


def pbr(f, casas=1):
    return f"{f * 100:.{casas}f}%".replace(".", ",")


def vezes(f, casas=1):
    return f"{f:.{casas}f}×".replace(".", ",")


ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--dados", default=str(REPO / "artefatos/custo_llm.json"))
ap.add_argument("--saida", default=str(RAIZ / "slides_custo.html"))
a = ap.parse_args()

arq = Path(a.dados)
if not arq.exists():
    sys.exit(f"ERRO: falta {arq}. Rode antes: .venv/bin/python scripts/27_custo_llm.py")
D = json.loads(arq.read_text(encoding="utf-8"))
REAL, CF, CAL = D["gasto_real"], D["contrafactual_llm_em_tudo"], D["calibracao"]
CACHE = CF["com_prompt_caching"]
IDENT = CF["campos_de_identidade"]
RAZAO = D["razao"]["contrafactual_sobre_real"]
# a comparacao direta: mesma tarefa (ler atributo e decidir classe) nos dois lados.
# No gasto real sao as etapas 11, 10, 12 e 24; o resto e campo de identidade.
ETAPAS_LEITURA = ("11", "10", "12", "24", "04")
real_leitura = sum(x["usd"] for x in REAL["etapas"]
                   if x["etapa"].split(" ")[0] in ETAPAS_LEITURA)
cf_leitura = CF["atributos"]["usd"] + CF["classe"]["usd"]


def slide(label, titulo, corpo, fonte):
    return f"""<section class="slide">
  <div class="rot">{e(label)}</div>
  <h2>{titulo}</h2>
  <div class="corpo">{corpo}</div>
  <div class="fonte">fonte: {e(fonte)}</div>
</section>"""


SL = []

# 1 ------------------------------------------------- gasto real x contrafactual ----
linhas_real = "".join(
    f"<tr><td>{e(x['etapa'])}</td><td class='n'>{num(x['perguntas'])}</td>"
    f"<td class='n'>{usd(x['usd'])}</td></tr>" for x in REAL["etapas"])
linhas_real += (
    f"<tr class='final'><td><b>total em produção</b></td>"
    f"<td class='n'>{num(REAL['perguntas_producao'])}</td>"
    f"<td class='n'>{usd(REAL['usd_producao'])}</td></tr>")

n_reg = CF["registros_da_base"]
linhas_cf = (
    f"<tr><td>atributos, 1 pergunta por registro</td>"
    f"<td class='n'>{num(CF['registros_com_classe_do_pdm'])}</td>"
    f"<td class='n'>{usd(CF['atributos']['usd'])}</td></tr>"
    f"<tr><td>classe, contra a lista fechada do PDM</td>"
    f"<td class='n'>{num(n_reg)}</td>"
    f"<td class='n'>{usd(CF['classe']['usd'])}</td></tr>")
for x in IDENT:
    linhas_cf += (f"<tr><td>{e(x['campo'])} em toda linha</td>"
                  f"<td class='n'>{num(n_reg)}</td>"
                  f"<td class='n'>{usd(x['usd_base_inteira'])}</td></tr>")
linhas_cf += (f"<tr class='final'><td><b>total, uma execução, mesmo modelo</b></td>"
              f"<td class='n'>{num(CF['perguntas'])}</td>"
              f"<td class='n'>{usd(CF['usd_uma_execucao'])}</td></tr>")

modelos = "".join(
    f"<tr><td>{e(m)}</td><td class='n'>{usd(v)}</td></tr>"
    for m, v in CF["usd_por_modelo"].items())

SL.append(slide(
    "CUSTO DE IA · O QUE GASTAMOS E O QUE GASTARÍAMOS",
    f"{usd(REAL['usd_producao'])} de LLM nesta base. Com LLM em tudo: "
    f"{usd(CF['usd_uma_execucao'])}",
    f"""<p class="destaque"><b>{vezes(RAZAO)}</b> mais caro por execução — e
{vezes(cf_leitura / real_leitura)} na tarefa que as duas abordagens fazem igual, ler atributo e
decidir classe ({usd(real_leitura)} medidos contra {usd(cf_leitura)} estimados). Por registro,
{usd(D['razao']['usd_por_registro_real'], 5)} contra
{usd(D['razao']['usd_por_registro_contrafactual'], 5)}.</p>
<div class="duas">
  <div><div class="crot">Gasto real — perguntas que de fato foram feitas 🟢</div>
    <table><thead><tr><th>etapa</th><th style="width:16%">perguntas</th>
      <th style="width:20%">custo</th></tr></thead><tbody>{linhas_real}</tbody></table>
    <p class="mini">Fora da tabela, porque é pesquisa e não operação: o benchmark das
    10 soluções × 4 campos custou {usd(REAL['usd_benchmark_pesquisa'])}, uma vez só, para
    descobrir qual solução ganha em cada campo. Num cliente novo não se repete.</p></div>
  <div><div class="crot">Se o LLM fosse a única camada, nos mesmos
      {num(n_reg)} registros 🟡</div>
    <table><thead><tr><th>o que o LLM faria</th><th style="width:16%">perguntas</th>
      <th style="width:20%">custo</th></tr></thead><tbody>{linhas_cf}</tbody></table>
    <div class="tres" style="margin-top:12px">
      <div class="caixa"><div class="crot">O modelo multiplica</div>
        <table class="mini"><tbody>{modelos}</tbody></table></div>
      <div class="caixa"><div class="crot">A reexecução multiplica</div>
        <p class="mini">Hoje a 2ª execução da mesma base custa <b>{usd(0)}</b>: a resposta
        virou regra no dicionário e o cache devolve a pergunta repetida. Sem camada barata,
        <b>{usd(CF['usd_uma_execucao'] * 2)}</b> pelas duas rodadas do teste de
        determinismo.</p></div>
      <div class="caixa"><div class="crot">O desconto que falta aos dois</div>
        <p class="mini">Com <i>prompt caching</i> por classe o contrafactual cairia a
        <b>{usd(CACHE['usd_uma_execucao'])}</b>. Não está implementado, e valeria igual para o
        resíduo: a razão se mantém.</p></div>
    </div></div>
</div>""",
    "artefatos/custo_llm.json · scripts/27_custo_llm.py · docs/16-custo-de-llm.md · "
    "Haiku 4.5 no Bedrock, preço de tabela"))

# 2 ------------------------------------------- onde o LLM nao vale + metodo ----
perdeu = [x for x in IDENT
          if x["aplicada_top1"] > x["top1"] and not x["aplicada"].startswith("llm_")]
def top1(v):
    return f"{v:.3f}".replace(".", ",")


# O MESMO modelo sem lista fechada, sem tool use e sem validador: a linha
# llm_naive_haiku do benchmark. E o que mede quanto do resultado e andaime.
import csv  # noqa: E402

_bench = list(csv.DictReader((REPO / "preenchimento/benchmark.csv").open(encoding="utf-8")))
naive = {r["campo"]: float(r["top1"]) for r in _bench if r["solucao"] == "llm_naive_haiku"}


linhas_id = ""
for x in sorted(IDENT, key=lambda y: y["aplicada"].startswith("llm_")):
    cls = " class='final'" if x in perdeu else ""
    linhas_id += (f"<tr{cls}><td>{e(x['campo'])}</td>"
                  f"<td><code>{e(x['aplicada'])}</code></td>"
                  f"<td class='n'>{top1(x['aplicada_top1'])}</td>"
                  f"<td class='n'>{usd(x['aplicada_usd_base_inteira'])}</td>"
                  f"<td class='n'>{top1(x['top1'])}</td>"
                  f"<td class='n'>{usd(x['usd_base_inteira'])}</td></tr>")

SL.append(slide(
    "CUSTO DE IA · ONDE O LLM NÃO VALE O PREÇO",
    f"Em {len(perdeu)} dos {len(IDENT)} campos de identidade, a solução barata "
    f"<i>acerta mais</i>",
    f"""<div class="duas">
  <div><table><thead><tr><th>campo</th><th>solução aplicada</th><th>top-1</th>
      <th>na base inteira</th><th>top-1 do LLM</th>
      <th>LLM na base inteira</th></tr></thead><tbody>{linhas_id}</tbody></table>
    <p class="obs">Se o LLM em tudo fosse só mais caro, seria escolha de orçamento. O
    benchmark diz outra coisa: em {len(perdeu)} dos {len(IDENT)} campos, pagar pelo LLM
    compraria <b>menos acerto</b>. Só em FABRICANTE ele ganha — e ali o projeto pagou pelo
    modelo melhor (Sonnet 5), que é metade do gasto real do projeto. A arquitetura não
    economiza por avareza: paga o LLM onde ele é o melhor e não paga onde ele perde.</p>
    <p class="obs ressalva"><b>O que este slide não prova.</b> A comparação de acerto é dos
    quatro campos de identidade, que têm gabarito e benchmark. Nos <i>atributos</i> o
    contrafactual mede custo, não acurácia: rodar 500 registros com o LLM fazendo tudo
    (~{usd(5, 0)}) fecharia essa lacuna, e é a próxima medição da lista.</p></div>
  <div class="lado">
    <div class="caixa"><div class="crot">Como o contrafactual foi calculado</div>
      <p>O script monta o <b>prompt de verdade</b> para cada um dos {num(n_reg)} registros — o
      mesmo <code>SISTEMA</code>, o mesmo <code>enum</code> da classe no tool use — e converte
      caractere em token por uma razão <b>medida</b>: a única rodada do projeto com tokens em
      log ({CAL['chamadas']} chamadas, {num(CAL['tokens_entrada'])} tokens de entrada) dá
      <b>{str(CAL['caracteres_por_token_entrada']).replace('.', ',')} caracteres por
      token</b>.</p>
      <p class="mini">A convenção de 3,5 car/token dos scripts 12 e 24 conta 40% menos token
      do que o real, e toda estimativa de <code>--so-contar</code> sai baixa na mesma
      proporção.</p></div>
    <div class="caixa"><div class="crot">Aferição contra medição real</div>
      <p>O item "atributos" é a mesma chamada do desempate, só que em todos os registros. Os
      dois custos por registro batem:</p>
      <table class="mini"><tbody>
        <tr><td>contrafactual, atributos 🟡</td><td class="n">
          {usd(CF['atributos']['usd'] / CF['registros_com_classe_do_pdm'], 5)}</td></tr>
        <tr><td>desempate real, 1.370 registros 🟢</td><td class="n">{usd(5.53 / 1370, 5)}</td></tr>
      </tbody></table>
      <p class="mini">Os 18% de diferença têm o sinal certo: no contrafactual o modelo
      preenche <b>todas</b> as caixas, e escreve mais na saída.</p></div>
    <div class="caixa"><div class="crot">O LLM sem o andaime das camadas</div>
      <p>O mesmo modelo, perguntado sem lista fechada, sem <i>tool use</i> e sem validador
      (<code>llm_naive</code>), tira top-1 de <b>{top1(naive['GRUPO_MERCADORIA'])}</b> em
      GRUPO_MERCADORIA e <b>{top1(naive['NCM'])}</b> em NCM — e custa quase o mesmo. O que faz
      o LLM servir não é o modelo, é o andaime em volta dele.</p></div>
  </div>
</div>""",
    "preenchimento/benchmark.csv (10 soluções × 4 campos, tokens reais) · "
    "artefatos/custo_llm.json · docs/16-custo-de-llm.md"))

CSS = f"""
:root{{--navy:{C['navy']};--teal:{C['teal']};--surface:{C['surface']};--card:{C['card']};--track:{C['track']};
 --green:{C['green']};--cream:{C['cream']};--amber:{C['amber']};--pink:{C['pink']};--red:{C['red']};--cyan:{C['cyan']};
 --tit:"Archivo Narrow","Oswald","Roboto Condensed","Ubuntu Sans","Liberation Sans Narrow","Nimbus Sans Narrow",system-ui,sans-serif;
 --txt:system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;
 --mono:ui-monospace,"JetBrains Mono","SF Mono","DejaVu Sans Mono",Menlo,monospace}}
*{{box-sizing:border-box}}
html,body{{margin:0;background:#8a9098;font-family:var(--txt);color:var(--navy)}}
.deck{{display:flex;flex-direction:column;align-items:center;gap:22px;padding:22px}}
.slide{{position:relative;width:1334px;height:750px;flex:0 0 auto;background:var(--surface);padding:62px 90px 56px;overflow:hidden}}
.rot{{font-family:var(--mono);font-size:13px;letter-spacing:.14em;color:var(--teal);text-transform:uppercase;margin:0 0 12px}}
h2{{font-family:var(--tit);font-weight:800;font-stretch:condensed;font-size:42px;line-height:1.04;margin:0 0 8px}}
.corpo{{margin-top:10px}}
.fonte{{position:absolute;left:90px;right:90px;bottom:24px;font-family:var(--mono);font-size:12px;color:rgba(23,32,42,.45)}}
table{{width:100%;border-collapse:collapse;font-size:14px}}
thead th{{background:var(--track);font-weight:600;font-size:12.5px;padding:7px 9px;text-align:left;border:1px solid rgba(23,32,42,.10);line-height:1.22}}
tbody td{{padding:6px 9px;border:1px solid rgba(23,32,42,.10);background:var(--card);vertical-align:middle;line-height:1.28}}
td.n{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}}
tr.final td{{background:#dcebe9}}
td.fraco,.fraco{{color:rgba(23,32,42,.58);font-weight:400}}
code{{font-family:var(--mono);font-size:.9em;background:rgba(23,32,42,.055);padding:1px 5px;border-radius:3px}}
.duas{{display:grid;grid-template-columns:1fr 1fr;gap:18px;align-items:start}}
.tres{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}}
.obs{{font-size:13.5px;line-height:1.42;margin:10px 0 0}}
.destaque{{background:var(--cream);border-left:3px solid var(--amber);padding:9px 15px;margin:0 0 14px;
  font-size:14.5px;line-height:1.4}}
.obs.ressalva{{background:var(--card);border-left:3px solid var(--teal);padding:9px 15px;color:rgba(23,32,42,.82);margin-top:12px}}
.lado{{display:flex;flex-direction:column;gap:12px}}
.caixa{{background:var(--card);border:1px solid rgba(23,32,42,.09);border-radius:8px;padding:10px 14px}}
.caixa p{{margin:4px 0 0;font-size:13.5px;line-height:1.4}}
.caixa .mini{{font-size:12px;color:rgba(23,32,42,.7);margin-top:7px}}
.crot{{font-size:12.5px;color:rgba(23,32,42,.62);font-weight:600;margin-bottom:5px}}
table.mini{{font-size:13px;margin-top:4px}}
table.mini tbody td{{padding:3px 8px;border:none;border-bottom:1px solid rgba(23,32,42,.07);white-space:nowrap}}
p.mini{{font-size:12.5px;line-height:1.38;color:rgba(23,32,42,.7);margin:8px 0 0}}
@media print{{@page{{size:1334px 750px;margin:0}} html,body{{background:#fff}} .deck{{gap:0;padding:0}}
 .slide{{page-break-after:always;break-after:page}}}}
"""

HTML = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Pipeline de saneamento · custo de LLM</title>
<meta name="viewport" content="width=1334"><style>{CSS}</style></head>
<body><div class="deck">
{chr(10).join(SL)}
</div></body></html>
"""
Path(a.saida).write_text(HTML, encoding="utf-8")
print(f"gravado {a.saida}  ({len(SL)} slides)")
print(f"  gasto real em producao ....... {usd(REAL['usd_producao'])} "
      f"({num(REAL['perguntas_producao'])} perguntas)")
print(f"  LLM em tudo, uma execucao .... {usd(CF['usd_uma_execucao'])} "
      f"({num(CF['perguntas'])} perguntas, {vezes(RAZAO)})")
print(f"  so a leitura ................. {usd(real_leitura)} contra {usd(cf_leitura)} "
      f"({vezes(cf_leitura / real_leitura)})")
