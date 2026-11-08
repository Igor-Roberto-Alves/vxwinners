"""Grava demo-mvp.mp4 navegando de verdade na plataforma servida por ./rodar.sh.

Sete cenas com tempos fixos (capítulos clicáveis do deck), sem cartões de
título — abre direto na página Início e tudo o que aparece vem da API, dos
artefatos do pipeline e do banco de desenvolvimento:

  0:00  Início carregada, parada
  0:04  Início: capital consolidável (R$ 30,24 mi) — pintado por frontend/radar.js
  0:22  Radar: cartões do topo com procedência (medido / premissa)
  0:40  Buscar material (painel): "filtro oleo fleetguard lf9009" → classe,
        NCM/fabricante/part number com confiança, itens parecidos, usar o código
  1:01  Pedidos de cadastro: SC-202600002 (retentor FREUDENBERG), leitura por
        IA (bedrock), última pendência (MATERIAL), descrição PDM, duplicidade
  1:20  Códigos juntados: grupo aberto, fica (verde) × saem (riscados),
        campo a campo, saldo somado
  1:38  NCM trocado: contadores e NCM antigo riscado → novo

Requisito: plataforma no ar (PORTA=8100 ./rodar.sh) e pedido SC-202600002 em
estado NOVO. Sai um .webm; a conversão para MP4 é feita fora daqui (ffmpeg).

Uso:  LD_LIBRARY_PATH=/tmp/demo_mvp/libs/usr/lib/x86_64-linux-gnu \
          python3 apresentacao/gravar_demo_mvp.py [pasta_saida]
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8100"
SAIDA = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_mvp_v3/video")
W, H = 1280, 800
FIM = 110.0                       # 1:50

# Cursor visível em todos os frames (página e iframe do painel). Cada frame
# desenha o próprio cursor no mousemove; ao entrar num iframe o frame de cima
# esconde o dele (mouseout com relatedTarget IFRAME), e ao sair o iframe
# esconde o seu (relatedTarget null) — sem pontos fantasmas duplicados.
INIT = """
(() => {
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
    addEventListener('mouseout', e => {
      if (!e.relatedTarget || e.relatedTarget.tagName === 'IFRAME') d.style.opacity = 0;
    }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', instala);
  else instala();
})();
"""

t_rec0 = None     # começo aproximado da gravação (página criada)
t0 = None         # zero do vídeo final (Início pronto); corte de cabeça = t0 - t_rec0
capitulos = []    # (nome, segundo real no vídeo final)


def main():
    global t_rec0, t0
    SAIDA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": W, "height": H},
            device_scale_factor=1,
            record_video_dir=str(SAIDA),
            record_video_size={"width": W, "height": H},
        )
        ctx.add_init_script(INIT)
        pg = ctx.new_page()
        t_rec0 = time.time()

        def T():
            return time.time() - t0

        def marca(nome):
            print(f"[{T():6.1f}s] {nome}", flush=True)

        def pausa(s):
            pg.wait_for_timeout(int(s * 1000))

        def ate(alvo):
            falta = alvo - T()
            if falta > 0:
                pg.wait_for_timeout(int(falta * 1000))
            else:
                print(f"    (cena anterior passou {-falta:.1f}s do alvo {alvo:.0f}s)", flush=True)

        def capitulo(nome):
            capitulos.append((nome, round(T(), 1)))
            marca("CAPITULO " + nome)

        def mouse_para(loc, steps=24, dy=0):
            box = loc.bounding_box()
            x = box["x"] + box["width"] / 2
            y = box["y"] + box["height"] / 2 + dy
            pg.mouse.move(x, y, steps=steps)

        def clica(loc, steps=24):
            mouse_para(loc, steps=steps)
            pausa(0.3)
            loc.click()

        def rola_ate(loc, block="center"):
            loc.evaluate(f"e => e.scrollIntoView({{behavior:'smooth', block:'{block}'}})")
            pausa(1.1)

        # ---------------------------------------------- abertura: Início pronto
        pg.goto(f"{BASE}/", wait_until="domcontentloaded")
        pg.wait_for_selector("#page-inicio.active", timeout=20000)
        pg.wait_for_function(
            "document.getElementById('home-consolidavel').textContent.includes('30,24')",
            timeout=20000)
        pg.wait_for_function(
            "document.getElementById('n-pedidos').textContent.trim() !== '—'", timeout=20000)
        painel = pg.frame_locator("#painel")
        fobj = next(f for f in pg.frames if "/painel" in f.url)
        fobj.wait_for_selector("#q", state="attached", timeout=20000)
        pg.evaluate("() => document.fonts.ready")
        pausa(0.5)
        t0 = time.time()

        # ------------------------------------------------ 0:00–0:04 · parada
        capitulo("inicio parado")
        ate(4.0)

        # ------------------------------------------------ 0:04–0:22 · Início
        capitulo("inicio: consolidavel")
        mouse_para(pg.locator("#page-inicio .ax-hero h1"), steps=34)
        pausa(1.6)
        mouse_para(pg.locator("#home-consolidavel"), steps=26)      # R$ 30,24 mi
        pausa(2.6)
        mouse_para(pg.locator("#home-consolidavel-d"), steps=12)
        pausa(1.8)
        mouse_para(pg.locator("#home-consolidado"), steps=14)       # R$ 0,00 — honesto
        pausa(1.8)
        botao_radar = pg.locator("#page-inicio .ax-result .ax-btn-primary")
        mouse_para(botao_radar, steps=18)
        ate(21.4)
        botao_radar.click()                                          # "Abrir o Radar"

        # ------------------------------------------------ 0:22–0:40 · Radar
        pg.wait_for_selector("#page-radar.active", timeout=10000)
        capitulo("radar: procedencia")
        heros = pg.locator("#rad-hero .card.hero")
        assert "30,24" in heros.nth(0).inner_text()
        assert "10,84" in heros.nth(3).inner_text()
        mouse_para(heros.nth(0), steps=22)          # consolidável · medido
        pausa(2.6)
        mouse_para(heros.nth(3), steps=20)          # fila R$ 10,84 mi · medido
        pausa(2.8)
        mouse_para(heros.nth(2), steps=18)          # custo de oportunidade · premissa
        pausa(2.6)
        mouse_para(heros.nth(4), steps=16)          # NCM corrigido · medido
        pausa(2.4)
        mouse_para(pg.locator("#page-radar .page-head p"), steps=16)  # legenda da procedência
        pausa(2.0)
        busca_nav = pg.locator(".side-item[data-nav='busca']")
        mouse_para(busca_nav, steps=20)
        ate(39.6)
        busca_nav.click()

        # ------------------------------------------- 0:40–1:01 · Buscar material
        painel.locator("#q").wait_for(timeout=10000)
        capitulo("busca ao vivo")
        clica(painel.locator("#q"), steps=18)
        pg.keyboard.type("filtro oleo fleetguard lf9009", delay=52)
        painel.locator("#resultado-nomes .item").first.wait_for(timeout=10000)
        pausa(1.4)                                   # classes sugeridas (grupo FIL01)
        clica(painel.locator("#resultado-nomes .item").first, steps=12)
        painel.locator("#texto-extra").wait_for(timeout=10000)
        pausa(0.7)
        clica(painel.locator("#texto-extra"), steps=16)
        pg.keyboard.type("fleetguard lf9009", delay=42)
        pg.keyboard.press("Enter")                   # preenche FABRICANTE
        fobj.wait_for_function(
            "() => [...document.querySelectorAll('input,select')].some(i => (i.value||'').includes('FLEETGUARD'))",
            timeout=10000)
        pausa(0.7)
        ref = painel.locator("input[data-atr='REFERENCIA FABRICANTE']")
        clica(ref, steps=14)
        pg.keyboard.type("LF9009", delay=55)
        pg.keyboard.press("Tab")                     # grava e dispara a duplicidade
        painel.locator("button.chip", has_text="LF9009").first.wait_for(timeout=10000)
        painel.locator("#lateral .cand").first.wait_for(timeout=10000)
        marca("sugestoes do modelo na tela")
        sug = painel.locator("button.chip", has_text="LF9009").first
        sug.evaluate("e => e.scrollIntoView({behavior:'smooth', block:'center'})")
        pausa(0.9)
        mouse_para(painel.locator("button.chip").first, steps=16)   # NCM · conf
        pausa(1.6)
        mouse_para(sug, steps=10)                                   # LF9009 · 85%
        pausa(1.6)
        cand = painel.locator("#lateral .cand").first
        mouse_para(cand, steps=18)                                  # item parecido real
        pausa(1.8)
        usar = cand.get_by_role("button", name="Usar este código")
        clica(usar, steps=10)
        painel.get_by_text("Encerrado: usar o código").first.wait_for(timeout=10000)
        marca("melhor candidato selecionado")
        mouse_para(painel.get_by_text("Encerrado: usar o código").first, steps=14)
        pedidos_nav = pg.locator(".side-item[data-nav='pedidos']")
        ate(60.6)
        pedidos_nav.click()

        # -------------------------------------- 1:01–1:20 · Pedidos de cadastro
        painel.locator("#lista-pedidos .item").first.wait_for(timeout=10000)
        capitulo("pedido SC-202600002")
        clica(painel.locator("#busca-pedido"), steps=16)
        pg.keyboard.type("SC-202600002", delay=40)
        alvo = painel.locator("#lista-pedidos .item", has_text="SC-202600002").first
        alvo.wait_for(timeout=10000)
        pausa(0.8)                                   # pedido com a pill "anexo"
        clica(alvo, steps=12)
        painel.get_by_text("Pedido SC-202600002").wait_for(timeout=10000)
        pausa(1.3)                                   # ficha técnica + campos por regra
        ler = painel.get_by_role("button", name="Ler com IA")
        clica(ler, steps=14)
        fobj.wait_for_function(
            "() => [...document.querySelectorAll('input,select')].some(i => (i.value||'').includes('FREUDENBERG'))",
            timeout=30000)
        marca("IA leu a ficha (FREUDENBERG)")
        pausa(1.2)
        clica(painel.get_by_role("button", name="Confirmar classe"), steps=12)
        pausa(0.8)
        sel_mat = painel.locator("select[data-atr='MATERIAL']")
        clica(sel_mat, steps=14)                     # abre as sugestões do histórico
        chip_nbr = painel.locator("button.chip", has_text="NBR").first
        chip_nbr.wait_for(timeout=10000)
        pausa(1.0)                                   # NBR · 333× (82%) no histórico
        clica(chip_nbr, steps=8)                     # resolve a última pendência
        painel.get_by_text("Sem pendências: pronto para aprovar").wait_for(timeout=10000)
        marca("sem pendencias")
        desc = painel.locator("#lateral .desc").first
        desc.evaluate("e => e.scrollIntoView({behavior:'smooth', block:'center'})")
        pausa(0.8)
        mouse_para(desc, steps=16)                   # descrição no padrão PDM
        pausa(1.8)
        mouse_para(painel.locator("#lateral .cand").first, steps=14)  # duplicidade
        pausa(1.6)
        clusters_nav = pg.locator(".side-item[data-nav='clusters']")
        ate(79.4)
        clusters_nav.click()

        # ---------------------------------------- 1:20–1:38 · Códigos juntados
        pg.wait_for_selector("#jn-g-table tbody tr", timeout=20000)
        capitulo("codigos juntados")
        mouse_para(pg.locator("#jn-kpis .card.kpi").nth(0), steps=18)
        pausa(1.6)
        linha1 = pg.locator("#jn-g-table tbody tr").first
        clica(linha1, steps=16)                      # maior capital do plano
        rola_ate(pg.locator("#jn-detalhe"), block="start")
        mouse_para(pg.locator("#jn-d-por-que .callout"), steps=14)   # mesma chave
        pausa(1.6)
        mouse_para(pg.locator("#jn-d-linhas .badge.b-green").first, steps=12)  # FICA
        pausa(1.2)
        mouse_para(pg.locator("#jn-d-linhas .badge.b-err").first, steps=10)    # SAI →
        pausa(1.2)
        rola_ate(pg.locator("#jn-d-cmp"), block="center")            # campo a campo
        mouse_para(pg.locator("#jn-d-cmp td.diff").first, steps=12)
        pausa(1.6)
        rola_ate(pg.locator("#jn-d-imp"), block="center")            # saldo somado
        mouse_para(pg.locator("#jn-d-imp .fx").nth(1), steps=12)
        pausa(1.4)
        mouse_para(pg.locator("#jn-d-imp .fx").nth(2), steps=8)
        pausa(1.2)
        pg.locator("#jn-abas").evaluate(
            "e => e.scrollIntoView({behavior:'smooth', block:'start'})")
        pausa(1.0)
        aba_ncm = pg.locator("#jn-abas [data-aba='ncm']")
        mouse_para(aba_ncm, steps=14)
        ate(97.6)
        aba_ncm.click()

        # ------------------------------------------- 1:38–1:50 · NCM trocado
        pg.wait_for_selector("#jn-n-table tbody tr", timeout=10000)
        capitulo("ncm trocado")
        tiles = pg.locator("#jn-n-tipos .fx")
        mouse_para(tiles.nth(0), steps=16)           # trocado · 1.104
        pausa(1.7)
        mouse_para(tiles.nth(1), steps=10)           # preenchido · 597
        pausa(1.3)
        mouse_para(tiles.nth(3), steps=10)           # continua sem NCM · 611
        pausa(1.3)
        troca = pg.locator("#jn-n-table .troca").first
        rola_ate(troca, block="center")
        mouse_para(troca, steps=14)                  # NCM antigo riscado → novo
        pausa(2.0)
        mouse_para(pg.locator("#jn-n-table .troca").nth(1), steps=10)
        pg.mouse.move(640, 560, steps=12)
        ate(FIM)

        marca("fim")
        video = pg.video
        ctx.close()
        caminho = video.path()
        browser.close()

        info = {
            "webm": str(caminho),
            "corte_cabeca": round(t0 - t_rec0, 2),
            "duracao": FIM,
            "capitulos": capitulos,
        }
        Path("/tmp/demo_mvp_v3/info.json").write_text(json.dumps(info, ensure_ascii=False))
        print(json.dumps(info, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
