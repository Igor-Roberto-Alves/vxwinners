"""Grava o vídeo de apresentação v2 navegando de verdade na interface nova.

Adaptado de gravar_demo.py para a plataforma.html da interface2, seguindo o
arco do pitch oficial ("Pipeline de Saneamento VX - pitch.pdf"):

  1. cartão de capa (P1) + página Início
  2. cartão "Mesmas caixas, mesmo item" (P2: 90,8% classe · 97,5% atributos
     · 98,5% junção) — a tela de visão do pipeline não existe na interface,
     então a cena usa cartão de título no estilo Figma, como previsto
  3. Radar com os dados reais de artefatos/radar.json (R$ 30,24 mi
     consolidável · R$ 10,84 mi na fila · 3.482 itens · 1.478 a um clique);
     os cinco cartões do topo do mockup são reescritos com o JSON real
  4. Busca ao vivo: digita a descrição e o POST /sugerir responde na tela
  5. Cadastro: pedido real (SC-202600002, retentor FREUDENBERG), sugestões
     com confiança e checagem de duplicata consultando a base real
  6. Clusters: chave igual = código redundante (P9/P10), unificação
  7. cartão de fecho (R$ 30,24 mi consolidáveis · benchmark auditado)

Requisitos: site em http://127.0.0.1:8080 (http.server na raiz do repo) e o
motor de sugestão em http://127.0.0.1:8700 (servico/). Nada na busca, no
cadastro e nos números do Radar é fixo: vem da API e de artefatos/radar.json.

Uso:
    python3 apresentacao/gravar_demo_v2.py [pasta_saida]

Sai um .webm (screencast do Playwright, 1280x800) na pasta de saída; a
conversão para MP4 (H.264, yuv420p) é feita depois com o ffmpeg do
imageio-ffmpeg. Em WSL sem as libs do Chromium, exporte antes:
    LD_LIBRARY_PATH=/tmp/demo_mvp/libs/usr/lib/x86_64-linux-gnu
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
RAIZ = Path(__file__).resolve().parent          # apresentacao/
CARTOES = RAIZ / "cartoes_v2"
SAIDA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_mvp_v2/video"
W, H = 1280, 800

# ---------------------------------------------------------------- cartões
# Estilo Figma do kit apresentacao/estilo_figma/ (o mesmo de slides_pitch):
# degradê #000 -> #200d42 -> #371770 -> #4f21a1 -> #a46edb, grade pontilhada,
# headline clara gigante com gradiente no texto, horizonte-planeta no rodapé.
CSS_CARTAO = """
@font-face{font-family:"Archivo";src:url("../slides_pitch/fontes/archivo-400.woff2") format("woff2");font-weight:400;font-display:block}
@font-face{font-family:"Archivo";src:url("../slides_pitch/fontes/archivo-500.woff2") format("woff2");font-weight:500;font-display:block}
@font-face{font-family:"Archivo";src:url("../slides_pitch/fontes/archivo-600.woff2") format("woff2");font-weight:600;font-display:block}
@font-face{font-family:"Archivo";src:url("../slides_pitch/fontes/archivo-700.woff2") format("woff2");font-weight:700;font-display:block}
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000;font-family:"Archivo","Inter",system-ui,sans-serif;overflow:hidden}
.slide{position:relative;width:1280px;height:800px;overflow:hidden;
  background:linear-gradient(180deg,#000 0%,#200d42 36%,#371770 53%,#4f21a1 69%,#a46edb 87%)}
.slide::before{content:"";position:absolute;inset:0;
  background-image:url("../estilo_figma/grid_pontilhada.svg");
  background-size:693px 1539px;background-repeat:repeat;background-position:31px 19px;
  opacity:.5;z-index:0;pointer-events:none}
.linha-esquerda{position:absolute;left:69px;top:0;width:4px;height:100%;
  background-image:url("../estilo_figma/linha_esquerda.png");background-size:100% 100%;z-index:1;pointer-events:none}
.linha-no{position:absolute;left:69px;top:var(--no-top,-78px);width:76px;height:423px;z-index:2;pointer-events:none}
.horizonte{position:absolute;bottom:0;left:0;width:100%;height:auto;z-index:2;pointer-events:none}
.conteudo{position:absolute;inset:0;padding:64px 80px 48px 147px;z-index:3;
  display:flex;flex-direction:column;justify-content:center}
.etiqueta{font-size:15px;font-weight:500;letter-spacing:.22em;text-transform:uppercase;
  color:#b9a8e0;margin-bottom:16px}
.titulo{font-weight:700;font-size:88px;line-height:1.1;letter-spacing:-.025em;max-width:1000px;
  background:linear-gradient(171deg,#fff 0%,rgba(255,255,255,.37) 99%);
  -webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent}
.titulo.menor{font-size:72px}
.subtitulo{font-weight:400;font-size:26px;line-height:1.35;margin-top:18px;max-width:900px;
  background:linear-gradient(171deg,rgba(255,255,255,.98) 0%,rgba(255,255,255,.55) 99%);
  -webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent}
.assinatura{margin-top:26px;font-size:18px;font-weight:500;letter-spacing:.08em;
  text-transform:uppercase;color:#b9a8e0}
.medidores{margin-top:40px;display:grid;grid-template-columns:repeat(3,1fr);gap:18px;max-width:980px}
.medidor{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.14);
  border-radius:14px;padding:22px 22px}
.medidor .campo{font-size:14px;font-weight:500;letter-spacing:.14em;text-transform:uppercase;color:#b9a8e0}
.medidor .valor{margin-top:10px;font-size:54px;font-weight:700;letter-spacing:-.02em;color:#fff;line-height:1}
.medidor .nota{margin-top:8px;font-size:15px;color:#cfc3e8}
.pilula{display:inline-flex;align-self:flex-start;margin-top:30px;padding:12px 22px;border-radius:12px;
  background:rgba(16,6,36,.55);border:1px solid rgba(255,255,255,.14);
  font-size:20px;font-weight:500;color:#e3d9f6;backdrop-filter:blur(4px)}
"""

CARTAO_TPL = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>{titulo}</title>
<style>{css}</style></head>
<body><div class="slide" style="--no-top:{no_top}px">
  <div class="linha-esquerda"></div>
  <img class="linha-no" src="../estilo_figma/linha_vertical_no.svg" alt="">
  <div class="conteudo">{conteudo}</div>
  <img class="horizonte" src="../estilo_figma/horizonte_planeta.png" alt="">
</div></body></html>
"""

CARTOES_HTML = {
    # cena 1a — capa, espelha a P1 do pitch
    "cartao_capa.html": {
        "titulo": "Pipeline de saneamento",
        "no_top": -40,
        "conteudo": """
    <div class="etiqueta">Hackathon VX · Desafio 01 · Cadastro e saneamento</div>
    <div class="titulo">Pipeline de saneamento</div>
    <div class="subtitulo">Como 23.554 materiais em texto livre viram grades de caixas
      comparáveis — e por que duas grades iguais provam um código redundante.</div>
    <div class="assinatura">vxwinners · novembro de 2026</div>""",
    },
    # cena 2 — P2 do pitch (a interface não tem tela de visão do pipeline)
    "cartao_caixas.html": {
        "titulo": "Mesmas caixas, mesmo item",
        "no_top": -78,
        "conteudo": """
    <div class="etiqueta">Visão geral · o método</div>
    <div class="titulo menor">Mesmas caixas, mesmo item</div>
    <div class="subtitulo">A classe define as caixas; regras e BERT as preenchem; tudo
      passa pela lista do PDM; o LLM entra só nas caixas em dúvida.</div>
    <div class="medidores">
      <div class="medidor"><div class="campo">Classe</div><div class="valor">90,8%</div>
        <div class="nota">acerto de classe</div></div>
      <div class="medidor"><div class="campo">Caixas</div><div class="valor">97,5%</div>
        <div class="nota">precisão dos atributos</div></div>
      <div class="medidor"><div class="campo">Junção</div><div class="valor">98,5%</div>
        <div class="nota">precisão da junção</div></div>
    </div>""",
    },
    # cena 7 — fecho
    "cartao_fecho.html": {
        "titulo": "vxwinners",
        "no_top": -40,
        "conteudo": """
    <div class="etiqueta">Hackathon VX · Desafio 01</div>
    <div class="titulo">vxwinners</div>
    <div class="subtitulo">Pipeline de saneamento</div>
    <div class="pilula">R$ 30,24 mi consolidáveis&nbsp;&nbsp;·&nbsp;&nbsp;benchmark auditado</div>""",
    },
}


def gera_cartoes():
    CARTOES.mkdir(exist_ok=True)
    for nome, c in CARTOES_HTML.items():
        html = CARTAO_TPL.format(css=CSS_CARTAO, **c)
        (CARTOES / nome).write_text(html, encoding="utf-8")
    print("cartões gerados em", CARTOES)


# ---------------------------------------------------- cursor visível (v1)
INIT = """
(() => {
  if (location.href === 'about:blank') document.documentElement.style.background = '#000';
  const instala = () => {
    const st = document.createElement('style');
    st.textContent = '#__cursor{position:fixed;left:0;top:0;width:19px;height:19px;border-radius:50%;' +
      'background:rgba(13,138,95,.25);border:2px solid rgba(13,138,95,.9);z-index:2147483647;' +
      'pointer-events:none;transform:translate(-50%,-50%);opacity:0;' +
      'transition:width .1s,height .1s,opacity .2s}';
    document.head.appendChild(st);
    const d = document.createElement('div');
    d.id = '__cursor';
    document.body.appendChild(d);
    addEventListener('mousemove', e => { d.style.opacity = 1;
      d.style.left = e.clientX + 'px'; d.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', () => { d.style.width = '27px'; d.style.height = '27px'; }, true);
    addEventListener('mouseup', () => { d.style.width = '19px'; d.style.height = '19px'; }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', instala);
  else instala();
})();
"""

# ------------------------------------------- dados reais em cima do mockup
# A interface nova traz números ilustrativos nos cartões do Radar e do Início.
# Antes de filmar, os cinco cartões do topo do Radar e os dois KPIs do Início
# são reescritos com artefatos/radar.json (os números medidos do pipeline,
# os mesmos do pitch). O aviso "valores simulados" passa a declarar a origem.
INJETA_REAIS = """
async () => {
  const d = await (await fetch('/artefatos/radar.json')).json();
  const mi = v => 'R$ ' + (v / 1e6).toLocaleString('pt-BR',
      {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' mi';
  const dinheiro = v => v ? mi(v) : 'R$ 0,00';
  const tag = f => `<span class="src-tag src-${f === 'medido' ? 'med' : f === 'estimado' ? 'est' : 'pre'}">${f}</span>`;
  const h = d.hero;

  const cards = document.querySelectorAll('#page-radar .card.hero');
  const poe = (card, rotulo, fonte, valorHtml, det) => {
    if (!card) return;
    card.querySelector('.l').innerHTML = rotulo + ' ' + tag(fonte);
    card.querySelector('.v').innerHTML = valorHtml;
    card.querySelector('.v').style.color = '';
    card.querySelector('.s').innerHTML = det;
    card.setAttribute('data-tt', rotulo + '|origem: ' + 'artefatos/radar.json');
  };
  poe(cards[0], h.consolidavel.rotulo, h.consolidavel.fonte, dinheiro(h.consolidavel.valor),
      h.consolidavel.detalhe.split(' · precisão')[0]);
  poe(cards[1], h.fila.rotulo, h.fila.fonte, dinheiro(h.fila.valor), h.fila.detalhe);
  poe(cards[2], 'Custo de oportunidade do capital', h.oportunidade.fonte,
      dinheiro(h.oportunidade.valor) + '<span style="font-size:13px;color:var(--text-3)">/ano</span>',
      h.oportunidade.detalhe);
  poe(cards[3], h.consolidado.rotulo, h.consolidado.fonte, dinheiro(h.consolidado.valor),
      h.consolidado.detalhe.split(':')[0]);
  poe(cards[4], h.ncm.rotulo, h.ncm.fonte, h.ncm.valor.toLocaleString('pt-BR'), h.ncm.detalhe);

  const aviso = document.querySelector('#page-radar .callout.warn div');
  if (aviso) aviso.textContent = 'Os cinco números do topo vêm de artefatos/radar.json, ' +
      'medidos pelo pipeline na base do desafio (R$ 200,87 mi em estoque). ' +
      'Tendência, saúde e matriz abaixo são ilustrativos do produto.';

  const k = document.querySelectorAll('#page-inicio .ax-kpi');
  if (k[0]) { k[0].querySelector('strong').textContent = mi(h.consolidavel.valor);
    k[0].querySelector('span').innerHTML = 'capital consolidável <i style="font-style:normal;opacity:.7">(medido)</i> · 1.991 grupos'; }
  if (k[1]) { k[1].querySelector('strong').textContent = mi(h.fila.valor);
    k[1].querySelector('span').textContent = 'na fila de intervenção · 3.482 itens'; }
}
"""

BUSCA_TXT = "filtro oleo fleetguard lf9009 caminhao fora de estrada"

t0 = time.time()


def marca(nome):
    print(f"[{time.time()-t0:6.1f}s] {nome}", flush=True)


def main():
    gera_cartoes()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            record_video_dir=SAIDA,
            record_video_size={"width": W, "height": H},
        )
        ctx.add_init_script(INIT)
        pg = ctx.new_page()

        def pausa(s):
            pg.wait_for_timeout(int(s * 1000))

        def mouse_para(sel, steps=22):
            box = pg.locator(sel).first.bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            pg.mouse.move(x, y, steps=steps)
            return x, y

        def clica(sel):
            mouse_para(sel)
            pausa(0.25)
            pg.locator(sel).first.click()

        def rola_ate(sel, block="center"):
            pg.locator(sel).first.evaluate(
                f"e => e.scrollIntoView({{behavior:'smooth', block:'{block}'}})")
            pausa(1.1)

        def cartao(nome, segundos, varre=None):
            pg.goto(f"{BASE}/apresentacao/cartoes_v2/{nome}")
            pg.evaluate("() => document.fonts.ready")
            pausa(0.4)
            if varre:                       # passeio lento do cursor
                for (x, y, s) in varre:
                    pg.mouse.move(x, y, steps=36)
                    pausa(s)
            pausa(segundos)

        def abre_plataforma():
            pg.goto(f"{BASE}/plataforma.html")
            pg.wait_for_selector("#page-inicio.active", timeout=15000)
            pg.evaluate(INJETA_REAIS)       # números reais de artefatos/radar.json

        # ---------------------------------------- cena 1 · capa + início
        marca("cena 1a: cartao capa")
        cartao("cartao_capa.html", 3.4)

        marca("cena 1b: inicio")
        abre_plataforma()
        pausa(0.6)
        pg.mouse.move(430, 300, steps=20)   # hero: "um cadastro que se mantém limpo"
        pausa(1.6)
        mouse_para("#page-inicio .ax-result .ax-kpi >> nth=0")   # R$ 30,24 mi (real)
        pausa(2.2)

        # ------------------------------- cena 2 · mesmas caixas, mesmo item
        marca("cena 2: cartao caixas (P2)")
        cartao("cartao_caixas.html", 2.6, varre=[(355, 585, 2.4), (640, 585, 2.4), (925, 585, 2.4)])

        # ---------------------------------------- cena 3 · radar (dados reais)
        marca("cena 3: radar")
        abre_plataforma()
        pausa(0.4)
        clica(".side-item[data-nav='radar']")
        pg.wait_for_selector("#page-radar.active .card.hero", timeout=10000)
        assert "30,24" in pg.locator("#page-radar .card.hero .v").first.inner_text()
        pg.mouse.move(640, 500, steps=14)   # ponto neutro, números à vista
        pausa(4.2)
        mouse_para("#page-radar .card.hero >> nth=1", steps=18)  # fila: R$ 10,84 mi
        pausa(2.6)
        pg.mouse.move(640, 520, steps=10)
        rola_ate("#page-radar .tbl.mtx", block="center")         # matriz de autonomia
        pausa(2.4)
        rola_ate("#evid", block="start")                         # evidências de eficácia
        pausa(2.6)

        # ---------------------------------------- cena 4 · busca ao vivo
        marca("cena 4: busca ao vivo")
        clica(".side-item[data-nav='busca']")
        pg.wait_for_selector("#page-busca.active #q", timeout=10000)
        pausa(0.8)
        clica("#q")
        pg.keyboard.press("ControlOrMeta+a")
        pausa(0.3)
        pg.keyboard.type(BUSCA_TXT, delay=46)                    # digitação humanizada
        pausa(0.5)
        clica("#btn-buscar")                                     # POST /sugerir real
        pg.wait_for_function(
            "document.getElementById('interp-note').textContent.includes('resposta em')",
            timeout=20000)
        marca("cena 4: resposta da API na tela")
        pausa(0.8)
        mouse_para("#interp-chips", steps=18)                    # grupo, NCM, fabricante, ref
        pausa(2.6)
        rola_ate("#cands .cand >> nth=0")
        mouse_para("#cands .cand >> nth=0", steps=14)
        pausa(1.6)
        clica("#cands .cand >> nth=0")                           # seleciona o melhor candidato
        pausa(0.8)
        mouse_para("#picked-code", steps=16)                     # decisão: validar existente
        pausa(1.6)
        rola_ate("#busca-callout", block="center")               # "encontrados na base real"
        pausa(2.2)

        # ---------------------------------------- cena 5 · cadastro guiado
        marca("cena 5: cadastro")
        clica(".side-item[data-nav='cadastro']")
        pg.wait_for_selector("#page-cadastro.active #attr-form select", timeout=10000)
        pausa(0.6)
        mouse_para("#page-cadastro .pdm-preview", steps=18)      # pedido real SC-202600002
        pausa(2.4)
        mouse_para("#page-cadastro .badge.b-info", steps=14)     # "IA preencheu 5 campos"
        pausa(1.6)
        sel_material = "#attr-form select[data-i='4']"
        rola_ate(sel_material)
        mouse_para(sel_material, steps=14)
        pausa(0.5)
        pg.locator(sel_material).select_option("NBR")            # resolve a pendência
        pausa(0.8)
        mouse_para("#desc-long", steps=16)                       # descrição no padrão PDM
        pausa(1.8)
        pg.wait_for_function(
            "document.getElementById('sim-sub').textContent.includes('consulta real')",
            timeout=20000)
        marca("cena 5: duplicidade consultada na base real")
        mouse_para("#checks", steps=14)                          # validação: pronto
        pausa(1.6)
        rola_ate("#similar", block="center")                     # alerta de duplicata
        mouse_para("#similar tr >> nth=1", steps=14)
        pausa(2.2)
        mouse_para("#sim-sub", steps=12)                         # "consulta real à base · N ms"
        pausa(1.8)

        # ---------------------------------------- cena 6 · clusters / junção
        marca("cena 6: clusters")
        clica(".side-item[data-nav='clusters']")
        pg.wait_for_selector("#page-clusters.active #cl-table tr", timeout=10000)
        pausa(1.0)
        clica("#cl-table tbody tr >> nth=0")        # dente caçamba · 4 códigos, chave igual
        pausa(0.6)
        rola_ate("#cl-why", block="center")         # "fabricante + part number iguais"
        pausa(1.8)
        rola_ate("#cl-cmp", block="center")         # grades lado a lado
        pausa(1.8)
        rola_ate("#cl-detail button.btn.primary", block="center")
        clica("#cl-detail button.btn.primary")      # Unificar no código escolhido
        pausa(2.2)                                  # toast + próximo cluster

        # ---------------------------------------- cena 7 · fecho
        marca("cena 7: cartao fecho")
        cartao("cartao_fecho.html", 6.4)

        marca("fim das cenas")
        video = pg.video
        ctx.close()
        caminho = video.path()
        browser.close()
        print("webm:", caminho)


if __name__ == "__main__":
    main()
