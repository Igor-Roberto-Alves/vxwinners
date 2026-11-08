"""Grava o vídeo de apresentação do MVP navegando de verdade na plataforma.

Requisitos: site em http://127.0.0.1:8080 (http.server na raiz do repo) e o motor
de sugestão em http://127.0.0.1:8700 (servico/api.py). A cena final (api_demo.html)
faz um POST real no /sugerir — nada na tela é fixo.

Uso:
    python3 apresentacao/gravar_demo.py [pasta_saida]

Sai um .webm (screencast do Playwright, 1280x800) na pasta de saída; a conversão
para MP4 (H.264, yuv420p) é feita depois com o ffmpeg do imageio-ffmpeg.
Em WSL sem as libs do Chromium, exporte antes:
    LD_LIBRARY_PATH=/tmp/demo_mvp/libs/usr/lib/x86_64-linux-gnu (libnspr4/libnss3)
"""
import sys
import time
from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8080"
SAIDA = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo_mvp/video"
W, H = 1280, 800

# Cursor visível (bolinha verde) + esconde avisos de ambiente (a faixa e o status
# falam do backend :8000, que não faz parte desta demo).
INIT = """
(() => {
  const instala = () => {
    const st = document.createElement('style');
    st.textContent = '.cad-faixa{display:none!important}#api-status{display:none!important}' +
      '#__cursor{position:fixed;left:0;top:0;width:19px;height:19px;border-radius:50%;' +
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

t0 = time.time()
def marca(nome):
    print(f"[{time.time()-t0:6.1f}s] {nome}", flush=True)

def main():
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

        # ------------------------------------------------ cena 1 · início
        marca("cena 1: inicio")
        pg.goto(f"{BASE}/plataforma.html")
        pg.wait_for_selector("#page-inicio.active", timeout=15000)
        pausa(1.0)
        pg.mouse.move(640, 300, steps=18)
        pausa(3.0)

        # ------------------------------------------------ cena 2 · radar
        marca("cena 2: radar")
        clica(".side-item[data-nav='radar']")
        pg.wait_for_selector("#rad-hero .card.hero", timeout=10000)
        pg.mouse.move(640, 480, steps=14)             # ponto neutro: sem tooltip sobre os números
        pausa(3.8)
        rola_ate("#rad-eficacia-card")
        mouse_para("#rad-eficacia-card tbody tr >> nth=0")
        pausa(1.4)
        mouse_para("#rad-eficacia-card tbody tr >> nth=3", steps=16)
        pausa(2.2)

        # ------------------------------------------------ cena 3 · fila de intervenção
        marca("cena 3: fila de intervencao")
        clica(".side-item[data-nav='intervencao']")
        pg.wait_for_selector("#fi-lista .card .chip-row", timeout=15000)
        pausa(3.0)                                    # KPIs: 3.482 itens, 1.478 a um clique
        cand = "#fi-lista .chip-row > button.btn.sm:not(.ghost)"
        rola_ate(f"{cand} >> nth=0")
        clica(f"{cand} >> nth=0")                     # decisão real: candidato aceito
        pausa(0.6)                                    # a lista re-renderiza e volta ao topo
        mouse_para("#fi-decididos")                   # contador: "1 decisões nesta sessão"
        assert "1 decis" in pg.locator("#fi-decididos").inner_text()
        pausa(1.5)
        segundo = pg.locator("#fi-lista > .card").nth(1).locator(
            ".chip-row > button.btn.sm:not(.ghost):not(.primary)").first
        segundo.evaluate("e => e.scrollIntoView({behavior:'smooth', block:'center'})")
        pausa(1.1)
        box = segundo.bounding_box()
        pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=20)
        pausa(0.5)
        segundo.click()                               # segunda decisão
        pausa(0.6)
        mouse_para("#fi-decididos")                   # "2 decisões nesta sessão"
        assert "2 decis" in pg.locator("#fi-decididos").inner_text()
        pausa(1.6)

        # ------------------------------------------------ cena 4 · base + busca local
        marca("cena 4: base e busca")
        clica(".side-item[data-nav='base']")
        pg.wait_for_selector("#base-table tr", timeout=10000)
        pausa(2.0)                                    # KPIs de qualidade da base
        clica("#bq")
        pg.keyboard.type("filtro oleo", delay=55)     # filtro ao vivo na amostra
        pausa(1.2)
        clica("#base-table tr:has-text('FRAM')")
        pausa(1.2)                                    # baseOpen rola sozinho até o registro
        rola_ate("#base-rec .callout", block="center")
        pausa(2.6)                                    # problemas de qualidade do registro

        # ------------------------------------------------ cena 5 · clusters
        marca("cena 5: clusters")
        clica(".side-item[data-nav='clusters']")
        pg.wait_for_selector("#cl-table tr", timeout=10000)
        pausa(1.6)
        clica("#cl-table tbody tr >> nth=1")          # outro cluster da fila
        pausa(0.8)
        rola_ate("#cl-cmp", block="center")
        pausa(2.6)                                    # comparação lado a lado
        rola_ate("#cl-detail button.btn.primary", block="center")
        clica("#cl-detail button.btn.primary")        # Unificar no código escolhido
        pausa(2.0)                                    # toast + próximo cluster

        # ------------------------------------------------ cena 6 · motor de sugestão ao vivo
        marca("cena 6: api ao vivo")
        pg.goto(f"{BASE}/apresentacao/api_demo.html")
        pg.wait_for_function("window.__done === true", timeout=40000)
        pausa(3.2)

        # ------------------------------------------------ cena 7 · fecho no radar
        marca("cena 7: fecho radar")
        pg.goto(f"{BASE}/plataforma.html#/radar")
        pg.wait_for_selector("#rad-hero .card.hero", timeout=10000)
        pg.mouse.move(640, 500, steps=16)             # área neutra, números à vista
        pausa(4.6)

        marca("fim das cenas")
        video = pg.video
        ctx.close()
        caminho = video.path()
        browser.close()
        print("webm:", caminho)

if __name__ == "__main__":
    main()
