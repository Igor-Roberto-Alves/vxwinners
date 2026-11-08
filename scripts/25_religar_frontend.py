# -*- coding: utf-8 -*-
"""Religa o desenho novo da plataforma ao backend, com as telas do front antigo.

Uso:
  backend/.venv/bin/python scripts/25_religar_frontend.py \
      [--novo apresentacao/interface2.html] \
      [--velho-commit 5715d2d] \
      [--saida plataforma.html] [--conferir]

O PROBLEMA QUE ISTO RESOLVE
---------------------------
O commit cb7fcbb ("add interface nova") substituiu plataforma.html pelo desenho
novo, que e um mockup: carrega ZERO scripts do frontend, nao fala com /api/v1, e
nao tem as telas pedidos, cadastros, revisao, intervencao e ia. Depois dele, o
./rodar.sh passou a servir uma maquete em vez da aplicacao.

A ultima versao ligada e 5715d2d:plataforma.html (154.760 bytes, 5 modulos de
frontend, 111 dos 116 ids que o JS procura).

COMO RELIGA
-----------
O desenho novo e um FORK do shell antigo: compartilha go(), openDrawer(),
baseRender(), radarCalc(), applyTheme() e mais 15 funcoes. Por isso da para
transplantar as telas que funcionam para dentro dele, em vez de reescrever.

E o CSS nao precisa ser fundido: das 55 classes que as telas transplantadas
usam, 54 ja estao no <style> do desenho novo (os dois sao forks do mesmo CSS) e
a unica que falta, cad-filtros, vem de frontend/cadastro.css, que este script
religa.

Passos, na ordem:
  1. os dois <link> de CSS (tema.css, cadastro.css) no <head>
  2. as telas que o JS precisa, vindas do velho, substituindo as de maquete:
     page-clusters e page-radar (o novo tem versao propria, sem os id= que o JS
     procura) e inserindo page-ia, page-intervencao, page-cadastros e
     page-revisao, que o novo nao tem
  3. o iframe do painel em page-cadastro (src=/painel?embutido=1), que e por onde
     busca, cadastro e pedidos funcionam
  4. os cinco itens de menu que faltavam, nos grupos certos
  5. os widgets de cabecalho que o JS escreve: api-status, pill-dados, usuario,
     crumb-page, avatar, drawer-mat
  6. API_URL do mockup (127.0.0.1:8700, o servico de sugestao) trocado por
     mesma origem, que e como o cadastro.js resolve: BASE="" + /api/v1
  7. os cinco <script src> no fim do body, DEPOIS do script inline - a ordem
     importa, porque o cadastro.js faz `goBase = window.go` e precisa que o
     shell ja tenha definido go()

--conferir nao grava nada: so compara o resultado com a lista de ids extraida
dos frontend/*.js e diz quantos faltam.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Nome do produto. O mockup (apresentacao/interface2.html) escreve "nome do
# produto" como placeholder; e aqui, na geracao, que ele vira marca. Trocar de
# nome e trocar esta linha e rodar o script.
NOME_DO_PRODUTO = "Prumo"
# Slug de projeto que o mockup cravou na migalha, herdado do nome antigo.
SLUG_ANTIGO = "catalogo-mro"

CSS = ["frontend/tema.css", "frontend/cadastro.css"]
JS = ["frontend/cadastro.js", "frontend/intervencao.js", "frontend/juncao.js",
      "frontend/regras_ia.js", "frontend/radar.js"]
# telas que o novo tem como maquete e precisam da versao com os id= do JS
SUBSTITUIR = ["clusters", "radar"]
# telas que o novo simplesmente nao tem
INSERIR = ["ia", "intervencao", "cadastros", "revisao"]
MENUS = ["pedidos", "cadastros", "revisao", "intervencao", "ia"]


def secao(html: str, nome: str):
    """Devolve (inicio, fim, texto) da <section id="page-NOME">."""
    m = re.search(r'<section[^>]*id="page-%s"' % re.escape(nome), html)
    if not m:
        return None
    ini = m.start()
    # a secao termina no proximo <section de pagina, no comentario que o precede,
    # ou no </main>/</body>
    resto = html[m.end():]
    fim_rel = len(resto)
    for pat in [r'\n<!--[^\n]*-->\n<section[^>]*id="page-', r'\n<section[^>]*id="page-',
                r'</main>', r'</body>']:
        mm = re.search(pat, resto)
        if mm and mm.start() < fim_rel:
            fim_rel = mm.start()
    fim = m.end() + fim_rel
    return ini, fim, html[ini:fim]


def elemento(html: str, abertura: str) -> str | None:
    """Recorta UM elemento inteiro, contando <div> para fechar no lugar certo.

    Regex nao serve aqui: `<div id="ov-mat".*?</div>\\s*</div>\\s*</div>` casou
    4.614 chars e varreu o <script> do arquivo de origem, o que produziu um
    segundo <script> inline e um 'SyntaxError: Unexpected end of input' - a
    pagina inteira deixava de rodar.
    """
    i = html.find(abertura)
    if i < 0:
        return None
    nivel, j = 0, i
    for m in re.finditer(r'<(/?)div\b[^>]*?(/?)>', html[i:]):
        if m.group(2) == "/":            # <div/> auto-fechada
            continue
        nivel += -1 if m.group(1) else 1
        if nivel == 0:
            j = i + m.end()
            break
    return html[i:j] if j > i else None


def ids_do_js() -> set[str]:
    out = set()
    for f in JS:
        s = (RAIZ / f).read_text(encoding="utf-8")
        for pat in [r'\$\("#([A-Za-z0-9_-]+)"', r'getElementById\("([A-Za-z0-9_-]+)"',
                    r'querySelector\("#([A-Za-z0-9_-]+)"', r"\$\('#([A-Za-z0-9_-]+)'"]:
            out |= set(re.findall(pat, s))
    return out


def religa(novo: str, velho: str) -> tuple[str, list[str]]:
    log = []
    h = novo

    # ---- 1. CSS ---------------------------------------------------------------
    alvo = re.search(r'(<link[^>]+fonts\.googleapis[^>]+>\s*)', h)
    tags = "".join(f'<link rel="stylesheet" href="{c}">\n' for c in CSS)
    if alvo:
        h = h[:alvo.end()] + "\n" + tags + h[alvo.end():]
    else:
        h = h.replace("<style", tags + "<style", 1)
    log.append(f"CSS religado: {', '.join(CSS)}")

    # ---- 2. telas -------------------------------------------------------------
    for nome in SUBSTITUIR:
        velha = secao(velho, nome)
        atual = secao(h, nome)
        if not velha:
            sys.exit(f"ERRO: page-{nome} nao existe no velho")
        if not atual:
            sys.exit(f"ERRO: page-{nome} nao existe no novo (esperava maquete)")
        h = h[:atual[0]] + velha[2] + h[atual[1]:]
        log.append(f"page-{nome}: maquete ({len(atual[2])} ch) -> ligada ({len(velha[2])} ch)")

    ancora = secao(h, "clusters")
    bloco = ""
    for nome in INSERIR:
        velha = secao(velho, nome)
        if not velha:
            sys.exit(f"ERRO: page-{nome} nao existe no velho")
        if secao(h, nome):
            log.append(f"page-{nome}: ja existe, pulado")
            continue
        bloco += "\n\n" + velha[2]
        log.append(f"page-{nome}: inserida ({len(velha[2])} ch)")
    if bloco:
        h = h[:ancora[1]] + bloco + h[ancora[1]:]

    # ---- 3. painel em page-cadastro ------------------------------------------
    if 'id="painel"' not in h:
        mv = re.search(r'<iframe id="painel"[^>]*>\s*</iframe>', velho)
        if not mv:
            mv = re.search(r'<iframe id="painel"[^>]*>', velho)
        if not mv:
            sys.exit("ERRO: nao achei o iframe do painel no velho")
        cad = secao(h, "cadastro")
        if not cad:
            sys.exit("ERRO: page-cadastro nao existe no novo")
        iframe = mv.group(0)
        if not iframe.endswith("</iframe>"):
            iframe += "</iframe>"
        # entra no fim da secao, antes do </section>
        corte = cad[2].rfind("</section>")
        nova = cad[2][:corte] + f'\n  {iframe}\n' + cad[2][corte:] if corte > 0 \
            else cad[2] + f'\n{iframe}\n'
        h = h[:cad[0]] + nova + h[cad[1]:]
        log.append("iframe do painel inserido em page-cadastro")

    # ---- 4. menu --------------------------------------------------------------
    inseridos = []
    for nav in MENUS:
        if re.search(r'data-nav="%s"' % nav, h):
            continue
        mv = re.search(r'<div class="side-item"[^>]*data-nav="%s".*?</div>\s*' % nav,
                       velho, re.S)
        if not mv:
            log.append(f"AVISO: item de menu '{nav}' nao achado no velho")
            continue
        item = mv.group(0)
        # ancora: o item de menu que vem logo antes dele no velho, se existir no novo
        antes = velho[:mv.start()]
        viz = re.findall(r'data-nav="([a-z0-9_-]+)"', antes)
        colocado = False
        for cand in reversed(viz):
            ma = re.search(r'<div class="side-item"[^>]*data-nav="%s".*?</div>\s*' % cand,
                           h, re.S)
            if ma:
                h = h[:ma.end()] + item + h[ma.end():]
                colocado = True
                break
        if not colocado:
            ma = re.search(r'(<div class="side-item".*?</div>\s*)', h, re.S)
            h = h[:ma.end()] + item + h[ma.end():]
        inseridos.append(nav)
    if inseridos:
        log.append(f"itens de menu inseridos: {', '.join(inseridos)}")

    # ---- 5. widgets de cabecalho ---------------------------------------------
    # 5a. a busca do topo no desenho novo e uma <div> decorativa com o texto
    #     "Ir para codigo..." e nenhum input. O shell espera <input id="ir-codigo">.
    if 'id="ir-codigo"' not in h:
        mv = re.search(r'<input id="ir-codigo"[^>]*>', velho)
        md = re.search(r'(<div class="top-search">)(.*?)(</div>)', h, re.S)
        if mv and md:
            kbd = re.search(r'<span[^>]*class="kbd"[^>]*>.*?</span>', md.group(2), re.S)
            svg = re.search(r'<svg.*?</svg>', md.group(2), re.S)
            novo_corpo = (svg.group(0) if svg else "") + mv.group(0) + \
                         (kbd.group(0) if kbd else "")
            h = h[:md.start()] + md.group(1) + novo_corpo + md.group(3) + h[md.end():]
            log.append("busca do topo: <div> decorativa -> input id=ir-codigo")

    # 5b. o desenho novo rotula a barra como "mockup - dados ficticios" num
    #     #api-pill proprio. Numa aplicacao ligada isso e rotulo falso, e o
    #     cadastro.js ja administra #pill-dados por tela (dados reais / saida do
    #     pipeline / demonstracao). Entao o #api-pill sai e o cluster certo entra.
    #     Tirar o elemento sozinho nao basta: o IIFE de saude do desenho novo faz
    #     getElementById('api-pill').textContent sem guarda, e dava
    #     "TypeError: Cannot set properties of null". Esse IIFE falava com o
    #     contrato do servico 8700 ({ok, linhas_base}), que nao e o do backend
    #     ({status, pdm_versao, ...}), e o cadastro.js ja cuida de #api-status.
    #     Por isso ele sai junto.
    mi = re.search(r'/\* saúde: liga o indicador quando o backend responde \*/'
                   r'.*?\}\)\(\);', h, re.S)
    if mi:
        h = h[:mi.start()] + ("/* o IIFE de saude do mockup saiu: o cadastro.js "
                              "administra #api-status contra /api/v1 */") + h[mi.end():]
        log.append("IIFE de saude do mockup removido (apontava para o serviço 8700)")

    mp = re.search(r'<span class="pill" id="api-pill">.*?</span>', h, re.S)
    if mp:
        i = velho.find('id="api-status"')
        j = velho.find('id="usuario"')
        a = velho.rfind("<span", 0, i)
        b = velho.find("</select>", j)
        cluster = velho[a:b + len("</select>")]
        h = h[:mp.start()] + cluster + h[mp.end():]
        log.append("#api-pill ('mockup · dados fictícios') -> api-status + "
                   "pill-dados + seletor de usuario")

    # 5c. o avatar, que o shell usa para as iniciais de quem esta logado
    if 'id="avatar"' not in h:
        mv = re.search(r'<div class="avatar" id="avatar">.*?</div>', velho, re.S)
        ms = re.search(r'(<select[^>]*id="usuario".*?</select>)', h, re.S)
        if mv and ms:
            h = h[:ms.end()] + mv.group(0) + h[ms.end():]
            log.append("avatar inserido ao lado do seletor de usuario")

    # 5d. o drawer do material (ov-mat/drawer-mat/mat-*): no velho ele mora no
    #     fim de page-requisicoes, mas e global - abre de qualquer tela.
    if 'id="ov-mat"' not in h:
        ov = elemento(velho, '<div class="overlay" id="ov-mat">')
        dr = elemento(velho, '<div class="drawer" id="drawer-mat">')
        if ov and dr:
            bloco = ov + "\n" + dr
            i = h.rfind("</body>")
            h = h[:i] + "\n" + bloco + "\n" + h[i:]
            log.append(f"drawer do material inserido ({len(bloco)} ch, recorte "
                       "balanceado)")
        else:
            log.append("AVISO: nao recortei o drawer do velho")

    faltam_hdr = [i for i in ("api-status", "pill-dados", "usuario", "crumb-page",
                              "avatar", "drawer-mat", "ir-codigo")
                  if f'id="{i}"' not in h]
    if faltam_hdr:
        log.append(f"AINDA faltam no cabecalho: {', '.join(faltam_hdr)}")

    # ---- 5e. codigo morto do mockup de clusters ------------------------------
    # O desenho novo traz o proprio simulador de clusters: um array CL com 7
    # clusters FALSOS escritos a mao e as funcoes clScore/clTable/clOpen/
    # clDecide/clNext, que escrevem em #cl-table e #cl-detail. Essa tela foi
    # substituida pela ligada (ids jn-*, servida por juncao.js), entao o
    # simulador virou codigo morto que ainda roda no carregamento (clOpen(0)) e
    # estourava "TypeError: Cannot set properties of null" em #cl-table,
    # abortando o resto do script de inicializacao.
    mc = re.search(r'const CL=\[.*?\nclOpen\(0\);', h, re.S)
    if mc:
        h = h[:mc.start()] + (
            "/* o simulador de clusters do mockup saiu (array CL de 7 clusters\n"
            "   ficticios + clScore/clTable/clOpen/clDecide/clNext): a tela de\n"
            "   juncao agora e a ligada, servida por frontend/juncao.js sobre\n"
            "   frontend/dados/juncao_ncm.json */") + h[mc.end():]
        log.append(f"simulador de clusters do mockup removido ({mc.end() - mc.start()} ch "
                   "de dado ficticio e codigo morto)")

    # ---- 5f. restos de maquete na casca --------------------------------------
    # o item desabilitado "Pedidos de cadastro 520" era o placeholder do mockup
    # para uma tela que ele nao tinha. Agora a tela existe e e viva, e o item
    # aparecia duas vezes no menu.
    md = re.search(r'\s*<div class="side-item disabled">(?:(?!</div>).)*?'
                   r'Pedidos de cadastro.*?</div>', h, re.S)
    if md:
        h = h[:md.start()] + h[md.end():]
        log.append("item de menu duplicado removido (o 'Pedidos de cadastro' "
                   "desabilitado do mockup)")

    # O mockup deixou o nome do produto como placeholder, em 6 lugares (titulo,
    # marca da barra, cabecalho lateral, migalha, marca do rodape e copyright). O nome e o do produto
    # (NOME_DO_PRODUTO): o placeholder fica no mockup, e so a saida leva a marca -
    # assim trocar de nome e uma linha, nao uma varredura por HTML.
    n_nome = h.count("nome do produto")
    if n_nome:
        h = h.replace("nome do produto", NOME_DO_PRODUTO)
        log.append(f"placeholder 'nome do produto' -> {NOME_DO_PRODUTO!r} "
                   f"({n_nome} ocorrencia(s))")

    # A migalha tem um slug de projeto ('catalogo-mro', do nome antigo). Deriva do
    # mesmo lugar, para nao sobrar o nome velho numa tela depois de um rename.
    if SLUG_ANTIGO in h:
        n_slug = h.count(SLUG_ANTIGO)
        h = h.replace(SLUG_ANTIGO, NOME_DO_PRODUTO.lower())
        log.append(f"slug do projeto na migalha: {SLUG_ANTIGO!r} -> "
                   f"{NOME_DO_PRODUTO.lower()!r} ({n_slug} ocorrencia(s))")

    # contagens cravadas no menu que o JS preenche de verdade: deixar o numero do
    # mockup ali mostra valor falso ate o fetch terminar (clusters dizia 1.412;
    # o medido e outro, e o juncao.js o escreve ao carregar).
    mcount = re.search(r'(<div class="side-item"[^>]*data-nav="clusters".*?'
                       r'<span class="count">)([^<]*)(</span>)', h, re.S)
    if mcount and mcount.group(2).strip() not in ("", "—", "-"):
        h = h[:mcount.start()] + mcount.group(1) + "—" + mcount.group(3) + h[mcount.end():]
        log.append(f"contagem de clusters no menu: '{mcount.group(2)}' (do mockup) "
                   "-> '—' ate o juncao.js preencher")

    # ---- 6. API na mesma origem ----------------------------------------------
    n_api = len(re.findall(r"API_URL\s*=\s*'http://127\.0\.0\.1:8700'", h))
    if n_api:
        h = re.sub(r"API_URL\s*=\s*'http://127\.0\.0\.1:8700'",
                   "API_URL=(location.protocol==='file:'?'http://127.0.0.1:8000':'')",
                   h)
        log.append(f"API_URL: {n_api} ocorrencia(s) do servico 8700 -> mesma origem")

    # ---- 7. scripts, DEPOIS do inline ----------------------------------------
    if "frontend/cadastro.js" not in h:
        tags = "".join(f'<script src="{j}"></script>\n' for j in JS)
        i = h.rfind("</body>")
        h = h[:i] + tags + h[i:]
        log.append(f"scripts religados ({len(JS)}), depois do script inline")

    return h, log


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--novo", default="apresentacao/interface2.html")
    ap.add_argument("--velho-commit", default="5715d2d")
    ap.add_argument("--saida", default="plataforma.html")
    ap.add_argument("--conferir", action="store_true")
    a = ap.parse_args()

    novo = (RAIZ / a.novo).read_text(encoding="utf-8")
    velho = subprocess.run(["git", "show", f"{a.velho_commit}:plataforma.html"],
                           cwd=RAIZ, capture_output=True, text=True, check=True).stdout

    h, log = religa(novo, velho)

    print("=== o que foi religado ===")
    for l in log:
        print("  " + l)

    # ---- sanidade estrutural -------------------------------------------------
    # O primeiro corte do drawer varreu o <script> do arquivo de origem e gerou um
    # segundo <script> inline truncado; a pagina parava com SyntaxError e nenhuma
    # tela abria. Agora isso falha aqui, nao no navegador.
    inline = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', h, re.S)
    print(f"\n=== sanidade ===")
    print(f"  scripts inline: {len(inline)} (esperado 1)  tamanhos {[len(x) for x in inline]}")
    if len(inline) != 1:
        sys.exit("ERRO: o recorte quebrou o script inline. Nao gravo assim.")
    tmp = Path("/tmp/_religar_inline.js")
    tmp.write_text(inline[0], encoding="utf-8")
    r = subprocess.run(["node", "--check", str(tmp)], capture_output=True, text=True)
    print("  node --check:", "ok" if r.returncode == 0 else "FALHOU")
    if r.returncode != 0:
        print(r.stderr[:600], file=sys.stderr)
        sys.exit("ERRO: script inline com sintaxe invalida. Nao gravo assim.")
    for t in ("</body>", "</html>"):
        if h.count(t) != 1:
            sys.exit(f"ERRO: {t} aparece {h.count(t)} vezes")
    ab, fe = len(re.findall(r"<div\b", h)), len(re.findall(r"</div>", h))
    print(f"  divs: {ab} abertas, {fe} fechadas" + ("" if ab == fe else "  <- DESBALANCEADO"))

    precisa = ids_do_js()
    tem = {i for i in precisa if re.search(r'id="%s"' % re.escape(i), h)}
    falta = sorted(precisa - tem)
    print(f"\n=== conferencia contra os {len(precisa)} ids que o JS procura ===")
    print(f"  presentes: {len(tem)}   faltam: {len(falta)}")
    if falta:
        print("  faltando: " + " ".join(falta))

    antes = {i for i in precisa if re.search(r'id="%s"' % re.escape(i), novo)}
    print(f"  (o desenho novo tinha {len(antes)}; o velho ligado tinha "
          f"{len({i for i in precisa if re.search(r'id=\"%s\"' % re.escape(i), velho)})})")

    if a.conferir:
        print("\n--conferir: nada gravado")
        return
    Path(RAIZ / a.saida).write_text(h, encoding="utf-8")
    print(f"\ngravado {a.saida}: {len(h)} chars "
          f"(desenho novo tinha {len(novo)}, velho ligado tinha {len(velho)})")


if __name__ == "__main__":
    main()
