#!/usr/bin/env python3
"""Renderiza o deck (index.html) em PNGs 1920x1080 e monta slides_pitch.pdf.

Uso:
    python3 render.py            # renderiza slides + PDF (gera o mockup se faltar)
    python3 render.py --demo     # força recapturar o screenshot da demo ao vivo

O screenshot da demo é tirado de http://127.0.0.1:8082/plataforma.html
(fallback 8081) e composto dentro do mockup de MacBook
(../estilo_figma/demo/raw_1.png, área de tela transparente x 326–2885,
y 66–1729). Se nenhum serviço estiver no ar, gera um retângulo roxo
escuro com o texto "demo ao vivo".
"""

import os
import sys

# libs de sistema para o chromium do playwright (WSL sem libnss etc.)
for _cand in ("/tmp/demo_mvp/libs/usr/lib/x86_64-linux-gnu",
              "/tmp/pwlibs/extract/usr/lib/x86_64-linux-gnu"):
    if os.path.isdir(_cand):
        os.environ["LD_LIBRARY_PATH"] = (
            _cand + ":" + os.environ.get("LD_LIBRARY_PATH", ""))
        break

from PIL import Image, ImageDraw  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_PNG = os.path.join(AQUI, "png")
PASTA_IMG = os.path.join(AQUI, "img")
MOCKUP_BASE = os.path.join(AQUI, "..", "estilo_figma", "demo", "raw_1.png")
MOCKUP_SAIDA = os.path.join(PASTA_IMG, "mockup_demo.png")
POSTER_SAIDA = os.path.join(PASTA_IMG, "poster_demo.png")
PDF_SAIDA = os.path.join(AQUI, "slides_pitch.pdf")
URLS_DEMO = ("http://127.0.0.1:8082/plataforma.html",
             "http://127.0.0.1:8081/plataforma.html")
# área transparente da tela no raw_1.png (3208x1944), medida pixel a pixel
TELA = (326, 66, 2886, 1730)  # left, top, right, bottom (exclusivos)


def captura_tela_demo(pw):
    """Screenshot 1440x900 (dsf=2) da plataforma com a busca preenchida."""
    navegador = pw.chromium.launch()
    pagina = navegador.new_page(
        viewport={"width": 1440, "height": 900}, device_scale_factor=2)
    bruto = None
    for url in URLS_DEMO:
        try:
            pagina.goto(url, wait_until="networkidle", timeout=15000)
            pagina.click("#aba-buscar")
            pagina.fill("#busca", "")
            pagina.type("#busca", "filtro oleo fleetguard lf9009", delay=35)
            pagina.wait_for_selector(
                "#busca-resultados .cartao", timeout=12000)
            pagina.wait_for_timeout(1200)  # resultados + transições
            bruto = pagina.screenshot()
            print(f"[demo] screenshot ao vivo de {url}")
            break
        except Exception as erro:  # tenta a próxima URL
            print(f"[demo] falhou em {url}: {erro}")
    navegador.close()
    return bruto


def tela_reserva():
    """Retângulo roxo escuro com o texto 'demo ao vivo' (fallback)."""
    from PIL import ImageFont
    im = Image.new("RGB", (2880, 1800), "#200d42")
    d = ImageDraw.Draw(im)
    try:
        fonte = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 140)
    except OSError:
        fonte = ImageFont.load_default()
    d.text((1440, 900), "demo ao vivo", font=fonte,
           fill="#d7c3f1", anchor="mm")
    return im


def compor_mockup(tela_im):
    """Encaixa o screenshot na área de tela do MacBook (cover + corte)."""
    base = Image.open(MOCKUP_BASE).convert("RGBA")
    lx, ty, rx, by = TELA
    lw, lh = rx - lx, by - ty  # 2560 x 1664
    # escala "cover" e corte central
    fator = max(lw / tela_im.width, lh / tela_im.height)
    novo = tela_im.resize(
        (round(tela_im.width * fator), round(tela_im.height * fator)),
        Image.LANCZOS)
    cx = (novo.width - lw) // 2
    cy = (novo.height - lh) // 2
    recorte = novo.crop((cx, cy, cx + lw, cy + lh)).convert("RGBA")
    quadro = Image.new("RGBA", base.size, (0, 0, 0, 0))
    quadro.paste(recorte, (lx, ty))
    composto = Image.alpha_composite(quadro, base)
    os.makedirs(PASTA_IMG, exist_ok=True)
    # reduz à metade: sobra de qualidade no slide e o arquivo fica leve
    composto = composto.resize(
        (base.width // 2, base.height // 2), Image.LANCZOS)
    composto.save(MOCKUP_SAIDA)
    print(f"[demo] mockup composto em {MOCKUP_SAIDA} {composto.size}")
    poster_do_mockup(composto)


def poster_do_mockup(mockup_im=None):
    """Recorta a área da tela do mockup: vira o poster do vídeo da demo."""
    if mockup_im is None:
        mockup_im = Image.open(MOCKUP_SAIDA)
    lx, ty, rx, by = (v // 2 for v in TELA)  # mockup salvo à metade
    mockup_im.crop((lx, ty, rx, by)).save(POSTER_SAIDA)
    print(f"[demo] poster do vídeo em {POSTER_SAIDA}")


def gerar_mockup(pw):
    import io
    bruto = captura_tela_demo(pw)
    if bruto is not None:
        tela = Image.open(io.BytesIO(bruto)).convert("RGB")
        origem = "ao vivo"
    else:
        tela = tela_reserva()
        origem = "RESERVA (serviço fora do ar)"
    compor_mockup(tela)
    return origem


def renderizar_slides(pw):
    os.makedirs(PASTA_PNG, exist_ok=True)
    navegador = pw.chromium.launch()
    pagina = navegador.new_page(viewport={"width": 1920, "height": 1080})
    pagina.goto("file://" + os.path.join(AQUI, "index.html"),
                wait_until="networkidle")
    pagina.evaluate("document.fonts.ready.then(() => true)")
    # o vídeo da demo fica parado no poster: sem controles no PNG
    pagina.add_style_tag(
        content="video::-webkit-media-controls{display:none !important}")
    pagina.wait_for_timeout(600)
    slides = pagina.query_selector_all("section.slide")
    if len(slides) != 10:
        raise SystemExit(f"esperava 10 slides, achei {len(slides)}")
    arquivos = []
    for i, slide in enumerate(slides, 1):
        destino = os.path.join(PASTA_PNG, f"slide_{i:02d}.png")
        slide.scroll_into_view_if_needed()
        pagina.wait_for_timeout(150)
        slide.screenshot(path=destino)
        arquivos.append(destino)
        print(f"[render] {destino}")
    navegador.close()
    return arquivos


def montar_pdf(arquivos):
    try:
        import img2pdf
        with open(PDF_SAIDA, "wb") as f:
            f.write(img2pdf.convert(arquivos))
        print(f"[pdf] {PDF_SAIDA} (img2pdf)")
    except ImportError:
        paginas = [Image.open(a).convert("RGB") for a in arquivos]
        paginas[0].save(PDF_SAIDA, save_all=True,
                        append_images=paginas[1:], resolution=96)
        print(f"[pdf] {PDF_SAIDA} (PIL)")


def validar(arquivos):
    for a in arquivos:
        im = Image.open(a)
        assert im.size == (1920, 1080), f"{a}: {im.size} != 1920x1080"
    try:
        from pypdf import PdfReader
        n = len(PdfReader(PDF_SAIDA).pages)
    except ImportError:
        with open(PDF_SAIDA, "rb") as f:
            n = f.read().count(b"/Type /Page\n") or None
        if n is None:
            print("[valida] pypdf ausente; contagem de páginas pulada")
            return
    assert n == 10, f"PDF com {n} páginas (esperava 10)"
    print(f"[valida] ok: 10 PNGs 1920x1080 e PDF com {n} páginas")


def main():
    from playwright.sync_api import sync_playwright
    forca_demo = "--demo" in sys.argv
    with sync_playwright() as pw:
        origem = None
        if forca_demo or not os.path.exists(MOCKUP_SAIDA):
            origem = gerar_mockup(pw)
        elif not os.path.exists(POSTER_SAIDA):
            poster_do_mockup()
        arquivos = renderizar_slides(pw)
    montar_pdf(arquivos)
    validar(arquivos)
    if origem:
        print(f"[demo] origem do screenshot: {origem}")


if __name__ == "__main__":
    main()
