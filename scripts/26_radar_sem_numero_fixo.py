# -*- coding: utf-8 -*-
"""Tira do desenho novo os numeros de Radar escritos a mao.

Uso:
  backend/.venv/bin/python scripts/26_radar_sem_numero_fixo.py \
      [apresentacao/interface2.html plataforma.html] [--conferir]

O PROBLEMA
----------
O commit 90fe961 ("Radar ligado aos dados") tirou da tela tres numeros que nao
tinham medicao atras: "Capital ja consolidado R$ 4,7 mi - medido" sem nenhuma
unificacao executada no ERP, uma serie de seis meses inventada no grafico
([0.3, 0.9, 1.7, 2.6, 3.6, 4.7]) e tres sparklines de saude igualmente
inventadas ([21, 27, 36, 44, 51, 58] e companhia).

O merge da interface2 (cb7fcbb) trouxe os tres de volta, porque o desenho novo
e um fork anterior aquele commit. O 25_religar_frontend.py transplanta a
MARCACAO do Radar (o div #rad-hero, que o frontend/radar.js preenche), mas as
tres funcoes vivem no <script> inline do desenho novo e continuariam pintando
dado inventado por cima do dado real.

Este script conserta as tres funcoes e os dois KPI da home, na fonte, para o
conserto sobreviver a cada regeneracao do plataforma.html.

Idempotente: rodar duas vezes nao muda nada. --conferir so relata.
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]

TREND = '''function trendChart(){
  // Sem serie historica: esta e a primeira execucao do pipeline sobre a base, o
  // marco zero. O mockup desenhava seis meses inventados ([0.3..4.7]).
  const alvo=document.getElementById('trend');
  if(!alvo) return;
  if(!window.RADAR){ alvo.innerHTML=''; return; }
  const h=RADAR.hero.consolidavel;
  alvo.innerHTML=`<div style="padding:18px 4px;line-height:1.7">
    <div class="mono" style="font-size:26px">${fmtMi(h.valor/1e6)}</div>
    <div class="faint" style="font-size:12.5px;margin-top:6px">${h.detalhe}</div>
    <div class="faint" style="font-size:11.5px;margin-top:10px;font-style:italic">
      Sem série por mês: esta é a primeira execução sobre a base — o marco zero.
      A próxima execução passa a comparar com esta.</div></div>`;
}
'''

HEALTH = '''function healthTiles(){
  // Medido na saida do pipeline (artefatos/saneado_base.csv), em vez da serie
  // de seis meses do mockup, que nao existe em lugar nenhum.
  const alvo=document.getElementById('health');
  if(!alvo||!window.RADAR) return;
  alvo.style.gridTemplateColumns='repeat(3,1fr)';
  alvo.innerHTML=RADAR.saude.map(t=>`<div class="spark-tile" data-tt="${t.rotulo}|${t.detalhe}">
    <div class="faint" style="font-size:12px;min-height:34px">${t.rotulo}</div>
    <div class="mono" style="font-size:20px;margin-top:4px">${t.valor}</div>
    <div class="faint" style="font-size:11px;margin-top:4px">${t.detalhe}</div></div>`).join('');
}
'''

CALC = '''function radarCalc(){
  const r=+document.getElementById('r-opp').value, pr=+document.getElementById('r-prem').value;
  document.getElementById('r-opp-l').textContent=r+'% a.a.';document.getElementById('r-prem-l').textContent=pr+'%';
  // O capital vem de artefatos/radar.json (plano de juncao x base), nao de
  // constante no HTML. Os cartoes que dependiam de premissa sem medicao sairam,
  // por isso def() nao assume que o no existe.
  const mi=window.RADAR ? RADAR.hero.consolidavel.valor/1e6 : 0;
  const def=(id,v)=>{const n=document.getElementById(id); if(n) n.textContent=v;};
  def('opp-rate', r+'%');
  def('opp-v', fmtMi(mi*r/100));
  def('opp-pot', fmtMi(mi*r/100));
  def('buy-prem', pr+'%');
}
'''

KPI_VELHO = (
    '        <div class="ax-kpi"><strong>R$ 4,7 mi</strong><span>capital já consolidado '
    '<i style="font-style:normal;opacity:.7">(medido)</i></span></div>\n'
    '        <div class="ax-kpi"><strong>R$ 18,4 mi</strong><span>consolidável em 1.412 '
    'clusters abertos</span></div>'
)

KPI_NOVO = '''        <!-- Preenchidos por frontend/radar.js a partir de artefatos/radar.json.
             Nao escrever numero aqui: era isto que punha "R$ 4,7 mi · capital
             ja consolidado (medido)" na home sem nenhuma unificacao executada. -->
        <div class="ax-kpi"><strong id="home-consolidavel">—</strong><span id="home-consolidavel-d">capital consolidável</span></div>
        <div class="ax-kpi"><strong id="home-consolidado">—</strong><span id="home-consolidado-d">capital já consolidado no ERP</span></div>'''

FUNCOES = {"trendChart": TREND, "healthTiles": HEALTH, "radarCalc": CALC}

# A contagem de grupos de duplicidade aparecia como 1.412 em dois lugares da
# casca: o menu lateral e o titulo da home. O valor real e 1.991, e as duas
# fontes concordam nele (radar.json base.grupos e juncao_ncm.json
# resumo.grupos). O 25_religar_frontend.py troca o do menu por '—', por isso
# as duas formas sao aceitas aqui.
#
# Quem preenche e o frontend/radar.js, que ja baixa o radar.json (4,8 KB) na
# home para os KPI: puxar o juncao_ncm.json de 4,5 MB so para mostrar uma
# contagem sairia caro.
CONTAGENS = [
    # (variantes a procurar, substituto, rotulo)
    (['>Clusters (saneamento)<span class="count">1.412</span>',
      '>Clusters (saneamento)<span class="count">—</span>'],
     '>Clusters (saneamento)<span class="count" id="n-clusters">—</span>',
     "contagem do menu lateral"),
    (['<h2>1.412 clusters esperam revisão</h2>',
      '<h2>— clusters esperam revisão</h2>'],
     '<h2><span id="n-clusters-home">—</span> clusters esperam revisão</h2>',
     "titulo da home"),
    (['<span class="sub">1.412 clusters abertos · amostra</span>'],
     '<span class="sub"><span id="n-clusters-fila">—</span> clusters abertos · amostra</span>',
     "subtitulo da fila de revisao"),
]


def conserta(texto: str) -> tuple[str, list[str]]:
    feito = []
    for nome, novo in FUNCOES.items():
        if novo in texto:
            continue
        m = re.search(r"^function " + nome + r"\(\)\{.*?^\}\n", texto, re.S | re.M)
        if not m:
            feito.append(f"{nome}: NAO ACHEI")
            continue
        texto = texto[: m.start()] + novo + texto[m.end():]
        feito.append(f"{nome}: {m.end() - m.start()} -> {len(novo)} bytes")
    if KPI_NOVO not in texto:
        if KPI_VELHO in texto:
            texto = texto.replace(KPI_VELHO, KPI_NOVO)
            feito.append("KPI da home: ligados ao radar.json")
        else:
            feito.append("KPI da home: NAO ACHEI o bloco original")

    for variantes, novo, rotulo in CONTAGENS:
        if novo in texto:
            continue
        achou = next((v for v in variantes if v in texto), None)
        if achou is None:
            # nao e erro: cada arquivo tem um subconjunto destes pontos
            continue
        texto = texto.replace(achou, novo)
        feito.append(f"{rotulo}: ligada ao radar.json")
    return texto, feito


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    conferir = "--conferir" in sys.argv
    alvos = args or ["apresentacao/interface2.html", "plataforma.html"]
    ruim = 0
    for rel in alvos:
        p = RAIZ / rel
        if not p.exists():
            print(f"{rel}: nao existe")
            ruim = 1
            continue
        antes = p.read_text(encoding="utf-8")
        depois, feito = conserta(antes)
        if any("NAO ACHEI" in f for f in feito):
            ruim = 1
        if not feito:
            print(f"{rel}: ja estava conservado")
            continue
        print(f"{rel}:")
        for f in feito:
            print(f"  {f}")
        if conferir:
            print("  (--conferir: nao gravei)")
        elif depois != antes:
            p.write_text(depois, encoding="utf-8")
            print("  gravado")
    return ruim


if __name__ == "__main__":
    sys.exit(main())
