# -*- coding: utf-8 -*-
"""Gera a apresentacao do produto: estrutura, estado da base e todas as metricas.

Uso:
  uv run --no-project --with pandas --with openpyxl python avaliacao/14_apresentacao_html.py \
      [--saida avaliacao/apresentacao.html]

Tudo que aparece na pagina e CALCULADO aqui, a partir de:
  artefatos/saneado_base.csv        estado, completude, chave de identidade, correcoes
  artefatos/decisoes_base.jsonl     uma decisao por atributo, com fonte e confianca
  artefatos/aprendizado.json        dicionario em uso
  artefatos/aprendizado_curado.json dicionario depois da curadoria
  artefatos/pdm.json                classes e atributos do padrao
  dados/01_base_materiais.xlsx      a base crua (contagem de entrada)
  avaliacao/gold*.csv               os dois conjuntos-ouro
  avaliacao/concordancia*.json      kappa
  avaliacao/resultado_caracteristicas.md   recortes do avaliador
  avaliacao/efeito_travas.json      antes/depois das travas
  avaliacao/resultado_testes.txt    saida do pytest
  avaliacao/determinismo.txt        saida do teste de determinismo (opcional)

Nenhum numero e digitado no gerador. Se um arquivo de entrada faltar, a secao
correspondente diz que falta, em vez de inventar valor.
"""
import argparse
import csv
import html
import json
import re
import statistics
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
ART = REPO / "artefatos"

FAMILIA_DA_CLASSE = {
    **{f"PDM{n:03d}": "fixadores" for n in (1, 2, 3, 4, 5, 6)},
    **{f"PDM{n:03d}": "mangueiras" for n in (10, 11, 12, 13, 14)},
    **{f"PDM{n:03d}": "rolamentos" for n in (20, 21, 22, 23)},
    **{f"PDM{n:03d}": "vedacao" for n in (31, 32, 33, 34)},
    **{f"PDM{n:03d}": "valvulas" for n in (40, 41, 42, 43, 44)},
    **{f"PDM{n:03d}": "conexoes" for n in (50, 51)},
    **{f"PDM{n:03d}": "eletricos" for n in (60, 61, 62, 63, 64, 65)},
    **{f"PDM{n:03d}": "outras" for n in (30, 66, 67, 70, 71, 72, 80, 81, 82, 90, 100)},
    "PDM110": "sobressalentes",
}

CAMADAS = [
    ("rotulo", "Rótulo na própria linha", "o texto já traz <code>ATRIBUTO: VALOR</code>"),
    ("gazetteer", "Valor literal do PDM", "o valor permitido aparece escrito"),
    ("sinonimo", "Sinônimo curado", "<code>sinonimos.py</code>, versionado e revisado por pessoa"),
    ("regra_pdm_2", "Regra 2 do PDM", "notação compacta <code>M12X50</code> separada em bitola e comprimento"),
    ("aprendido", "Dicionário aprendido", "resposta antiga do LLM reaplicada como regra, hoje com travas"),
    ("gramatica", "Gramática de grandezas", "ordem e unidade decidem qual número é qual atributo"),
    ("bert", "BERT de recorte", "modelo treinado na própria base marca o trecho"),
    ("acordo", "Acordo regra × BERT", "as duas camadas independentes concordam"),
    ("bert_desempata", "BERT como árbitro", "desempata quando regra e texto divergem"),
    ("dominio", "Heurística de domínio", "regra escrita à mão para um caso conhecido"),
    ("coluna_erp", "Coluna do ERP", "o valor vem de campo estruturado do cadastro"),
    ("llm", "LLM (Bedrock)", "só no que sobrou, e a resposta alimenta o dicionário"),
    ("llm_deteccao", "LLM de detecção", "decide se o dado está ausente ou perdido no texto"),
    ("ordem_pdm", "Ordem do PDM", "último recurso posicional"),
]


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def esc(s):
    return html.escape(str(s))


def pt(txt):
    """97.5% -> 97,5% (pagina em pt-BR; os .md saem com ponto decimal)."""
    return re.sub(r"(\d)\.(\d)", r"\1,\2", str(txt))


def num(n):
    return f"{n:,}".replace(",", ".")


def le_csv(caminho):
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ------------------------------------------------------------ dados da base ---
def metricas_base():
    rows = le_csv(ART / "saneado_base.csv")
    n = len(rows)
    compl = [float(r["COMPLETUDE"] or 0) for r in rows]
    pend_por_item = [len([p for p in r["PENDENTES"].split("|") if p.strip()])
                     for r in rows]
    pend = Counter(p.strip() for r in rows for p in r["PENDENTES"].split("|")
                   if p.strip())
    ch = Counter(r["CHAVE_IDENTIDADE"] for r in rows if r["CHAVE_IDENTIDADE"])
    grupos = [v for v in ch.values() if v > 1]
    familias = Counter(FAMILIA_DA_CLASSE.get(r["ID_PDM"], "fora do PDM")
                       for r in rows)
    return {
        "itens": n,
        "estados": Counter(r["ESTADO"] for r in rows),
        "completude_media": statistics.mean(compl),
        "completude_mediana": statistics.median(compl),
        "completos": sum(1 for r in rows if r["COMPLETO"] in ("1", "1.0", "True")),
        "itens_com_pendencia": sum(1 for p in pend_por_item if p),
        "pendencias": sum(pend.values()),
        "pendencias_top": pend.most_common(10),
        "pend_por_item": Counter(pend_por_item),
        "escalado_llm": sum(1 for r in rows if r["ESCALADO_LLM"] not in ("", "0")),
        "conflitos": sum(1 for r in rows if r["CONFLITOS"]),
        "com_chave": sum(1 for r in rows if r["CHAVE_IDENTIDADE"]),
        "chaves": len(ch),
        "grupos_duplicados": len(grupos),
        "itens_em_grupos": sum(grupos),
        "reducao": sum(grupos) - len(grupos),
        "maior_grupo": max(ch.values()) if ch else 0,
        "unidade_corrigida": sum(1 for r in rows if r["UNIDADE_PDM"]
                                 and r["UNIDADE_ORIGINAL"]
                                 and r["UNIDADE_PDM"] != r["UNIDADE_ORIGINAL"]),
        "ncm_corrigido": sum(1 for r in rows if r["NCM_PDM"] and r["NCM_ORIGINAL"]
                             and r["NCM_PDM"].replace(".", "")
                             != r["NCM_ORIGINAL"].replace(".", "")),
        "ncm_vazio_origem": sum(1 for r in rows if not r["NCM_ORIGINAL"]),
        "grupo_corrigido": sum(1 for r in rows
                               if r["GRUPO_CORRIGIDO"] not in ("", "0")),
        "classes_usadas": len({r["ID_PDM"] for r in rows if r["ID_PDM"]}),
        "familias": familias,
    }


def metricas_fontes():
    """Quantos valores cada camada decidiu na base inteira."""
    fontes, estados, atributos, itens = Counter(), Counter(), 0, 0
    with open(ART / "decisoes_base.jsonl", encoding="utf-8") as f:
        for linha in f:
            if not linha.strip():
                continue
            r = json.loads(linha)
            itens += 1
            for d in r.get("decisoes", []):
                atributos += 1
                estados[d.get("estado", "")] += 1
                if d.get("valor"):
                    fontes[(d.get("fonte") or "?").strip()] += 1
    return {"fontes": fontes, "estados": estados, "atributos": atributos,
            "itens": itens, "preenchidos": sum(fontes.values())}


# --------------------------------------------------------------- gabaritos ----
def tabela_do_md(md, titulo):
    """Le a primeira tabela depois de um titulo do .md -> (cabecalho, linhas)."""
    i = md.find(titulo)
    if i < 0:
        return None
    linhas = [l for l in md[i:].splitlines()]
    tab = []
    for l in linhas:
        if l.startswith("|"):
            tab.append([c.strip() for c in l.strip().strip("|").split("|")])
        elif tab:
            break
    if len(tab) < 2:
        return None
    return tab[0], tab[2:]


def metricas_gold():
    carac = le_csv(RAIZ / "gold_caracteristicas.csv")
    classe = le_csv(RAIZ / "gold_classe.csv")
    juncao = le_csv(RAIZ / "gold_juncao.csv")
    cand = le_csv(RAIZ / "candidatos_caracteristicas.csv")
    conc = json.loads((RAIZ / "concordancia_caracteristicas.json").read_text("utf-8"))
    md = (RAIZ / "resultado_caracteristicas.md").read_text(encoding="utf-8")
    armadilhas = Counter(a for r in cand for a in r["armadilhas"].split("|") if a)
    estratos = Counter(r["estrato"].split(":")[0] for r in cand)
    gold_antigo = {}
    if (RAIZ / "gold.csv").exists():
        g = le_csv(RAIZ / "gold.csv")
        ca = json.loads((RAIZ / "concordancia.json").read_text("utf-8"))
        gold_antigo = {"rotulos": len(g), "campos": len({r["campo"] for r in g}),
                       "itens": len({r["CODIGO_MATERIAL"] for r in g}),
                       "kappa": ca["global"]["kappa"],
                       "status": Counter(r["status"] for r in g)}
    return {
        "carac": len(carac), "classe": len(classe), "juncao": len(juncao),
        "itens": len({r["CODIGO_MATERIAL"] for r in classe}),
        "atributos_distintos": len({r["campo"] for r in carac}),
        "classes_no_gold": len({r["y_gold"] for r in classe}),
        "status": Counter(r["status"] for r in carac),
        "juncao_rotulos": Counter(r["y_gold"] for r in juncao),
        "origem": Counter(r["origem_decisao"] for r in carac),
        "estratos": estratos, "armadilhas": armadilhas,
        "concordancia": conc, "md": md,
        "estilo": Counter(r["estilo"] for r in cand),
        "familia_prevista": Counter(r["familia_prevista"] for r in cand),
        "revisao_humana": (sum(1 for _ in open(RAIZ / "revisao_humana_caracteristicas.csv",
                                               encoding="utf-8")) - 1),
        "gold_antigo": gold_antigo,
    }


def metricas_dicionario():
    def carrega(p):
        if not Path(p).exists():
            return None
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        ent = d["entradas"]
        return {"entradas": len(ent),
                "aplicaveis": sum(1 for e in ent if not e["revisar"]),
                "sugestoes": sum(1 for e in ent if e["revisar"]),
                "interpretacao": sum(1 for e in ent if "interpretacao" in e["fonte"]),
                "por_origem": Counter(e["fonte"].split("+")[0] for e in ent),
                "confirmacoes_1": sum(1 for e in ent if e["confirmacoes"] == 1)}
    return {"atual": carrega(ART / "aprendizado.json"),
            "curado": carrega(ART / "aprendizado_curado.json"),
            "travas": (json.loads((RAIZ / "efeito_travas.json").read_text("utf-8"))
                       if (RAIZ / "efeito_travas.json").exists() else None)}


def metricas_testes():
    d = {"pytest": "não executado", "determinismo": "não executado"}
    p = RAIZ / "resultado_testes.txt"
    if p.exists():
        m = re.search(r"(\d+) passed", p.read_text(encoding="utf-8"))
        if m:
            d["pytest"] = f"{m.group(1)} testes passando"
    p = RAIZ / "determinismo.txt"
    if p.exists():
        d["determinismo"] = p.read_text(encoding="utf-8").strip()
    return d


def classes_do_pdm():
    d = json.loads((ART / "pdm.json").read_text(encoding="utf-8"))
    classes = d["classes"]
    return {"classes": len(classes),
            "atributos": sum(len(c["atributos"]) for c in classes),
            "obrigatorios": sum(1 for c in classes for a in c["atributos"]
                                if a["obrigatorio"])}


# ------------------------------------------------------------------- pagina ----
CSS = """
:root{color-scheme:light;
 --surface:#fcfcfb; --surface-2:#f4f3f0; --borda:#e2e0da;
 --ink:#0b0b0b; --ink-2:#52514e; --ink-3:#6f6e69;
 --accent:#2a78d6; --good:#0ca30c; --warning:#fab219; --serious:#ec835a;
 --critical:#d03b3b; --codigo:#f7f6f3; --trilha:#cde2fb;}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme=light])){
 color-scheme:dark; --surface:#1a1a19; --surface-2:#232322; --borda:#383835;
 --ink:#f0efec; --ink-2:#c3c2b7; --ink-3:#a3a29a; --accent:#3987e5;
 --codigo:#141413; --trilha:#184f95;}}
:root[data-theme=dark]{color-scheme:dark; --surface:#1a1a19; --surface-2:#232322;
 --borda:#383835; --ink:#f0efec; --ink-2:#c3c2b7; --ink-3:#a3a29a;
 --accent:#3987e5; --codigo:#141413; --trilha:#184f95;}
*{box-sizing:border-box}
body{margin:0;background:var(--surface);color:var(--ink);
 font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 -webkit-font-smoothing:antialiased}
.pagina{max-width:1240px;margin:0 auto;padding:0 28px 100px}
.topo{padding:52px 0 28px;border-bottom:1px solid var(--borda);margin-bottom:36px}
.etiqueta{font-size:12px;letter-spacing:.08em;text-transform:uppercase;
 color:var(--accent);font-weight:600;margin:0 0 10px}
h1{font-size:34px;line-height:1.2;margin:0 0 12px;letter-spacing:-.015em}
.subtitulo{color:var(--ink-2);margin:0;max-width:76ch;font-size:17.5px}
.meta{color:var(--ink-3);font-size:13px;margin-top:18px}
.barra{display:flex;gap:8px;margin-top:20px;flex-wrap:wrap}
button{font:inherit;font-size:13px;color:var(--ink-2);background:var(--surface-2);
 border:1px solid var(--borda);border-radius:7px;padding:5px 11px;cursor:pointer}
button:hover{color:var(--ink);border-color:var(--ink-3)}
.cartoes{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(178px,1fr));
 margin:0 0 20px}
.hero,.tile{background:var(--surface-2);border:1px solid var(--borda);
 border-radius:12px;padding:18px 20px}
.hero{grid-column:1/-1}
.rotulo{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;
 color:var(--ink-3);margin:0 0 6px}
.valor{font-size:30px;font-weight:600;line-height:1.05;margin:0;letter-spacing:-.02em}
.hero .valor{font-size:50px}
.nota{color:var(--ink-2);font-size:13px;margin:8px 0 0}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12px;
 color:var(--ink-2);margin-top:10px}
.ponto{width:9px;height:9px;border-radius:50%;flex:0 0 auto}
.ponto.good{background:var(--good)} .ponto.warning{background:var(--warning)}
.ponto.serious{background:var(--serious)} .ponto.critical{background:var(--critical)}
.ponto.neutro{background:var(--accent)}
section{margin:56px 0 0}
h2{font-size:25px;margin:0 0 6px;letter-spacing:-.01em;padding-top:20px;
 border-top:1px solid var(--borda)}
h2 .n{color:var(--ink-3);font-weight:500;margin-right:10px}
.lede{color:var(--ink-2);margin:0 0 20px;max-width:80ch}
h3{font-size:16.5px;margin:30px 0 8px}
p,li{color:var(--ink-2)} li{margin:5px 0}
strong{color:var(--ink);font-weight:600}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
 font-size:.88em;background:var(--codigo);border:1px solid var(--borda);
 border-radius:4px;padding:1px 4px}
.grade{display:grid;gap:22px;grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}
.rolagem{overflow-x:auto;margin:14px 0;border:1px solid var(--borda);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px;
 font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:8px 12px;border-bottom:1px solid var(--borda);
 white-space:nowrap}
th{background:var(--surface-2);color:var(--ink);font-weight:600;font-size:12.5px}
td.n,th.n{text-align:right}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover td{background:var(--surface-2)}
.faixa{display:flex;gap:2px;height:28px;margin:16px 0 10px;width:100%}
.faixa div{border-radius:4px;display:flex;align-items:center;padding:0 10px;
 font-size:12px;font-weight:600;color:#fff;overflow:hidden;white-space:nowrap}
.legenda{display:flex;gap:18px;flex-wrap:wrap;font-size:13px;color:var(--ink-2)}
.legenda span{display:inline-flex;align-items:center;gap:7px}
.medidor{height:8px;background:var(--trilha);border-radius:4px;overflow:hidden;
 margin-top:8px}
.medidor div{height:100%;border-radius:4px;background:var(--accent)}
.aviso{border:1px solid var(--borda);border-left:3px solid var(--warning);
 background:var(--surface-2);border-radius:8px;padding:14px 18px;margin:18px 0}
.aviso p{margin:0;font-size:14.5px}
pre.bloco{background:var(--codigo);border:1px solid var(--borda);border-radius:10px;
 padding:15px 17px;overflow-x:auto;font-size:12.5px;line-height:1.55;margin:14px 0}
pre.bloco code{background:none;border:0;padding:0}
footer{margin-top:72px;padding-top:22px;border-top:1px solid var(--borda);
 color:var(--ink-3);font-size:13px}
a{color:var(--accent)}
@media print{.barra{display:none} section{break-inside:avoid}}
"""

JS = """
const alvo=document.documentElement;
const salvo=localStorage.getItem('tema'); if(salvo){alvo.dataset.theme=salvo;}
document.getElementById('tema').addEventListener('click',()=>{
  const escuro=getComputedStyle(document.body).backgroundColor==='rgb(26, 26, 25)';
  const novo=escuro?'light':'dark';
  alvo.dataset.theme=novo;localStorage.setItem('tema',novo);});
"""


def tab(cab, linhas, alinhar_num=True):
    def celula(tag, v, i):
        cls = ' class="n"' if alinhar_num and i > 0 else ""
        return f"<{tag}{cls}>{v}</{tag}>"
    out = ['<div class="rolagem"><table><thead><tr>']
    out += [celula("th", esc(c), i) for i, c in enumerate(cab)]
    out.append("</tr></thead><tbody>")
    for l in linhas:
        out.append("<tr>" + "".join(celula("td", c, i) for i, c in enumerate(l)) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def tab_do_md(md_tabela, titulo=""):
    if not md_tabela:
        return f"<p class=\"nota\">tabela “{esc(titulo)}” não encontrada no .md</p>"
    cab, linhas = md_tabela
    return tab([c.replace("precisao", "precisão") for c in cab],
               [[pt(c.replace("`", "")) for c in l] for l in linhas])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", default=str(RAIZ / "apresentacao.html"))
    a = ap.parse_args()

    base = metricas_base()
    fon = metricas_fontes()
    gold = metricas_gold()
    dic = metricas_dicionario()
    tes = metricas_testes()
    pdm = classes_do_pdm()
    md = gold["md"]

    resumo = tabela_do_md(md, "## 1. Resumo")
    g = resumo[1][0] if resumo else ["geral", "—", "—", "—", "—", "—", "—", "—"]
    precisao, cobertura, invencao = g[3], g[4], g[7]
    m_classe = re.search(r"Acerto de classe: \*\*(\d+)/(\d+)\*\*", md)
    m_prec_j = re.search(r"^\|\s*precisão\s*\|([^|]+)\|", md, re.M)
    m_rec_j = re.search(r"^\|\s*recall\s*\|([^|]+)\|", md, re.M)
    travas = dic["travas"]

    est = base["estados"]
    cor_estado = {"SANEADO": "good", "PENDENTE": "warning",
                  "REVISAO_HUMANA": "serious", "FORA_DO_PDM": "critical"}
    nome_estado = {"SANEADO": "Saneado", "PENDENTE": "Pendente",
                   "REVISAO_HUMANA": "Revisão humana", "FORA_DO_PDM": "Fora do PDM"}
    faixa = "".join(
        f'<div style="flex:{v} 1 0;background:var(--{cor_estado.get(k, "accent")})" '
        f'title="{esc(k)}: {num(v)}">'
        f'{(esc(nome_estado.get(k, k)) + " " + f"{v / base["itens"]:.0%}") if v / base["itens"] > 0.07 else ""}'
        "</div>"
        for k, v in est.most_common())
    legenda = " ".join(
        f'<span><span class="ponto {cor_estado.get(k, "neutro")}"></span>'
        f'{esc(nome_estado.get(k, k))} — {num(v)} ({pt(f"{v / base["itens"]:.1%}")})</span>'
        for k, v in est.most_common())

    cards = [
        ("Itens no catálogo", num(base["itens"]),
         f"{base['classes_usadas']} das {pdm['classes']} classes do PDM em uso", "neutro"),
        ("Saneados", f"{est['SANEADO'] / base['itens']:.1%}".replace(".", ","),
         f"{num(est['SANEADO'])} itens com descrição no padrão", "good"),
        ("Cadastro completo", f"{base['completos'] / base['itens']:.1%}".replace(".", ","),
         f"{num(base['completos'])} sem nenhum atributo pendente", "warning"),
        ("Duplicados colapsados", num(base["reducao"]),
         f"{num(base['grupos_duplicados'])} grupos, "
         + pt(f"{base['reducao'] / base['itens']:.1%}") + " da base", "neutro"),
        ("Precisão medida", pt(precisao.split("[")[0]),
         f"contra {num(gold['carac'])} rótulos de gabarito", "good"),
    ]
    html_cards = "".join(
        f'<div class="tile"><p class="rotulo">{esc(r)}</p>'
        f'<p class="valor">{esc(v)}</p><p class="nota">{n}</p>'
        f'<span class="chip"><span class="ponto {c}"></span>'
        f'{"medido contra o gabarito" if c == "good" else "estado da base"}</span></div>'
        for r, v, n, c in cards)

    # ---- camadas de decisao, com precisao por fonte onde o gold mede --------
    por_fonte_md = tabela_do_md(md, "## 6. Por fonte do valor")
    prec_por_fonte = {}
    if por_fonte_md:
        for l in por_fonte_md[1]:
            prec_por_fonte[l[0]] = (l[3], l[2], l[5], l[7])   # precisao, rotulos, erros, invencao
    linhas_camadas = []
    for fonte, nome, oque in CAMADAS:
        n_base = fon["fontes"].get(fonte, 0)
        p = prec_por_fonte.get(fonte)
        linhas_camadas.append([
            f"<strong>{esc(nome)}</strong><br><span class=\"nota\">{oque}</span>",
            f"<code>{esc(fonte)}</code>",
            num(n_base),
            f"{n_base / fon['preenchidos']:.1%}".replace(".", ",") if n_base else "—",
            pt(p[0]) if p else "—",
            pt(p[1]) if p else "—",
            (pt(p[3]) if p else "—"),
        ])
    outras = {k: v for k, v in fon["fontes"].items()
              if k not in {c[0] for c in CAMADAS}}
    if outras:
        linhas_camadas.append(["<em>outras fontes</em>", "—",
                               num(sum(outras.values())),
                               f"{sum(outras.values()) / fon['preenchidos']:.1%}".replace(".", ","),
                               "—", "—", "—"])

    L = []
    L.append(f"""<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Saneamento de cadastro de materiais — estrutura e métricas</title>
<style>{CSS}</style></head><body><div class="pagina">
<header class="topo">
<p class="etiqueta">Serra Azul Mineração e Energia · saneamento de cadastro</p>
<h1>De {num(base['itens'])} descrições livres a um catálogo no padrão PDM</h1>
<p class="subtitulo">O produto lê o cadastro como ele está — abreviado, com erro de
digitação, com unidade trocada — e devolve descrição padronizada, classe, unidade,
NCM e plano de junção de duplicados. Cada valor preenchido sabe de onde veio, e a
qualidade é medida contra dois conjuntos-ouro feitos sem olhar a saída do pipeline.</p>
<p class="meta">Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} ·
{num(fon['atributos'])} decisões de atributo em {num(fon['itens'])} itens ·
{tes['pytest']} · repositório <code>{esc(REPO)}</code></p>
<div class="barra"><button id="tema">claro / escuro</button></div>
</header>

<div class="cartoes">{html_cards}</div>

<div class="faixa">{faixa}</div>
<div class="legenda">{legenda}</div>

<section><h2><span class="n">1</span>Como o produto decide</h2>
<p class="lede">O pipeline é uma pilha de camadas baratas antes das caras. Cada
atributo é resolvido pela primeira camada que consegue respondê-lo com evidência;
o que sobra sobe para o BERT, para o LLM e, por último, para revisão humana. A
coluna <em>valores na base</em> conta quantos atributos cada camada decidiu de
fato; a precisão vem do gabarito, onde ele mede aquela camada.</p>
{tab(["camada", "fonte", "valores na base", "% do preenchido",
      "precisão (gabarito)", "rótulos medidos", "invenção"], linhas_camadas)}
<p class="nota">O LLM é responsável por {pt(f"{fon['fontes'].get('llm', 0) / fon['preenchidos']:.1%}")}
dos valores preenchidos e foi acionado em {num(base['escalado_llm'])} itens
({pt(f"{base['escalado_llm'] / base['itens']:.1%}")} da base): ele existe para o
que as camadas determinísticas não resolvem, e sua resposta é reaproveitada pelo
dicionário aprendido em vez de ser repetida.</p>
</section>

<section><h2><span class="n">2</span>Estado da base</h2>
<p class="lede">O que o pipeline entregou sobre os {num(base['itens'])} itens.</p>
<div class="grade">
<div><h3>Completude</h3>
{tab(["indicador", "valor"], [
  ["itens com descrição no padrão (SANEADO)", f"{num(est['SANEADO'])} ({est['SANEADO'] / base['itens']:.1%})".replace(".", ",")],
  ["cadastro completo (zero pendência)", f"{num(base['completos'])} ({base['completos'] / base['itens']:.1%})".replace(".", ",")],
  ["completude média dos atributos", pt(f"{base['completude_media']:.3f}")],
  ["itens com alguma pendência", f"{num(base['itens_com_pendencia'])} ({base['itens_com_pendencia'] / base['itens']:.1%})".replace(".", ",")],
  ["atributos pendentes no total", num(base['pendencias'])],
  ["itens escalados ao LLM", f"{num(base['escalado_llm'])} ({base['escalado_llm'] / base['itens']:.1%})".replace(".", ",")],
  ["itens com conflito registrado", num(base['conflitos'])],
])}</div>
<div><h3>Junção de duplicados</h3>
{tab(["indicador", "valor"], [
  ["itens com chave de identidade", f"{num(base['com_chave'])} ({base['com_chave'] / base['itens']:.1%})".replace(".", ",")],
  ["chaves distintas", num(base['chaves'])],
  ["grupos com mais de um item", num(base['grupos_duplicados'])],
  ["itens dentro desses grupos", num(base['itens_em_grupos'])],
  ["registros a menos se colapsar", f"{num(base['reducao'])} ({base['reducao'] / base['itens']:.1%})".replace(".", ",")],
  ["maior grupo", f"{base['maior_grupo']} itens"],
  ["sem chave (fora da junção)", f"{num(base['itens'] - base['com_chave'])} ({(base['itens'] - base['com_chave']) / base['itens']:.1%})".replace(".", ",")],
])}</div>
<div><h3>Correções de cadastro</h3>
{tab(["indicador", "valor"], [
  ["unidade de medida corrigida", num(base['unidade_corrigida'])],
  ["NCM corrigido", num(base['ncm_corrigido'])],
  ["NCM vazio na origem", num(base['ncm_vazio_origem'])],
  ["grupo de mercadoria corrigido", num(base['grupo_corrigido'])],
  ["classes do PDM em uso", f"{base['classes_usadas']} de {pdm['classes']}"],
  ["atributos do PDM (obrigatórios)", f"{pdm['atributos']} ({pdm['obrigatorios']})"],
])}</div>
<div><h3>Onde a pendência se concentra</h3>
{tab(["atributo", "pendências"], [[esc(k), num(v)] for k, v in base['pendencias_top']])}
</div>
</div></section>

<section><h2><span class="n">3</span>Como a qualidade é medida</h2>
<p class="lede">Dois conjuntos-ouro independentes do pipeline: anotados só a partir
do texto cru e do padrão PDM, com duas passadas independentes (A e B) e adjudicação
escrita de cada divergência.</p>
<div class="grade">
<div><h3>Gabarito de características, classe e junção</h3>
{tab(["o que mede", "rótulos"], [
  ["atributo técnico (item × atributo obrigatório)", num(gold['carac'])],
  ["classe do item (ID_PDM ou FORA_DO_PDM)", num(gold['classe'])],
  ["par de códigos (junção)", num(gold['juncao'])],
  ["itens anotados", num(gold['itens'])],
  ["atributos distintos cobertos", num(gold['atributos_distintos'])],
  ["classes distintas cobertas", f"{gold['classes_no_gold']} (inclui FORA_DO_PDM)"],
  ["rótulos AUSENTE + INDEFINÍVEL (medem invenção)",
   num(gold['status']['AUSENTE'] + gold['status']['INDEFINIVEL'])],
  ["kappa de Cohen A×B (global)", pt(f"{gold['concordancia']['global']['kappa']:.3f}")],
  ["divergências adjudicadas", num(gold['concordancia']['divergencias_adjudicadas'])],
  ["linhas na planilha de conferência humana", num(gold['revisao_humana'])],
])}</div>
<div><h3>Gabarito dos campos de cadastro (anterior)</h3>
{tab(["o que mede", "rótulos"], [
  ["GRUPO_MERCADORIA, NCM, FABRICANTE, REFERENCIA_FABRICANTE",
   num(gold['gold_antigo'].get('rotulos', 0))],
  ["itens anotados", num(gold['gold_antigo'].get('itens', 0))],
  ["kappa de Cohen A×B", pt(f"{gold['gold_antigo'].get('kappa', 0):.3f}")],
  ["rótulos AUSENTE", num(gold['gold_antigo'].get('status', {}).get('AUSENTE', 0))],
]) if gold['gold_antigo'] else '<p class="nota">gold.csv não encontrado</p>'}
<h3>Amostra do gabarito novo</h3>
{tab(["estrato", "itens"], [[esc(k), num(v)] for k, v in gold['estratos'].most_common()])}
</div>
</div>
<div class="aviso"><p><strong>O que o gabarito não é:</strong> as duas anotações
saíram do mesmo modelo em passadas separadas, então o kappa mede consistência, não
confiabilidade entre humanos; e a amostra é estratificada para concentrar
armadilhas, então as taxas são o desempenho nos casos difíceis, não uma estimativa
da base inteira. A planilha de conferência humana existe por isso.</p></div>
</section>

<section><h2><span class="n">4</span>Métricas de qualidade</h2>
<p class="lede">Precisão = acertos ÷ (acertos + erros), só onde o gabarito diz que
o texto traz o valor. Cobertura = quanto desses valores o pipeline preencheu.
Invenção = preencheu onde o gabarito diz AUSENTE ou INDEFINÍVEL.</p>
<div class="cartoes">
<div class="tile"><p class="rotulo">Precisão das características</p>
<p class="valor">{pt(precisao.split('[')[0])}</p>
<p class="nota">IC 95% {pt('[' + precisao.split('[')[1]) if '[' in precisao else ''}</p>
<div class="medidor"><div style="width:{precisao.split('%')[0]}%"></div></div></div>
<div class="tile"><p class="rotulo">Cobertura</p><p class="valor">{pt(cobertura)}</p>
<p class="nota">dos valores que o texto traz</p>
<div class="medidor"><div style="width:{cobertura.split('%')[0]}%"></div></div></div>
<div class="tile"><p class="rotulo">Taxa de invenção</p>
<p class="valor">{pt(invencao.split('(')[-1].rstrip(')'))}</p>
<p class="nota">{esc(invencao.split(' ')[0])} rótulos</p>
<div class="medidor"><div style="width:{invencao.split('(')[-1].rstrip('%)')}%;background:var(--serious)"></div></div></div>
<div class="tile"><p class="rotulo">Acerto de classe</p>
<p class="valor">{pt(f"{int(m_classe.group(1)) / int(m_classe.group(2)):.1%}") if m_classe else '—'}</p>
<p class="nota">{m_classe.group(1) + '/' + m_classe.group(2) if m_classe else ''} itens</p>
<div class="medidor"><div style="width:{(int(m_classe.group(1)) / int(m_classe.group(2)) * 100) if m_classe else 0:.0f}%"></div></div></div>
<div class="tile"><p class="rotulo">Junção</p>
<p class="valor">{pt(m_prec_j.group(1).split('[')[0].strip()) if m_prec_j else '—'}</p>
<p class="nota">precisão · recall {pt(m_rec_j.group(1).split('[')[0].strip()) if m_rec_j else '—'}</p>
<div class="medidor"><div style="width:{m_prec_j.group(1).split('%')[0].strip() if m_prec_j else 0}%"></div></div></div>
</div>
<h3>Por família de classe</h3>{tab_do_md(tabela_do_md(md, "## 3. Por família"), "família")}
<h3>Por estilo de texto</h3>{tab_do_md(tabela_do_md(md, "## 4. Por estilo"), "estilo")}
<h3>Por armadilha conhecida de extração</h3>{tab_do_md(tabela_do_md(md, "## 5. Por armadilha"), "armadilha")}
<h3>Status dos rótulos do gabarito</h3>
{tab(["status", "rótulos", "o que o pipeline deveria fazer"], [
  ["DEFINIDO", num(gold['status']['DEFINIDO']), "preencher com o valor"],
  ["AUSENTE", num(gold['status']['AUSENTE']), "deixar vazio — preencher é invenção"],
  ["INDEFINIVEL", num(gold['status']['INDEFINIVEL']), "deixar vazio — o texto não decide"],
])}
<h3>Junção: rótulos do gabarito</h3>
{tab(["rótulo", "pares"], [[esc(k), num(v)] for k, v in gold['juncao_rotulos'].most_common()])}
</section>
""")

    # ---- secao 5: travas ----------------------------------------------------
    if travas:
        ma, md_ = travas["metricas_antes"], travas["metricas_depois"]
        L.append(f"""<section><h2><span class="n">5</span>A camada que inventava, e o conserto</h2>
<p class="lede">O gabarito localizou a origem da invenção: o dicionário aprendido
— respostas antigas do LLM reaplicadas como regra. Ele decidia
{travas['rotulos_do_dicionario']} rótulos do gabarito e errava 28 deles. A correção
não foi desligar o LLM, foi exigir que o termo <em>aponte um único valor do enum</em>
na hora de aplicar, e abster-se quando o texto alcança dois valores do mesmo atributo.</p>
{tab(["métrica", "antes", "depois"], [
  ["precisão", pt(ma['precisao']), f"<strong>{pt(md_['precisao'])}</strong>"],
  ["cobertura", pt(ma['cobertura']), pt(md_['cobertura'])],
  ["taxa de invenção", pt(ma['invencao']), f"<strong>{pt(md_['invencao'])}</strong>"],
  ["acertos", num(ma['acertos']), num(md_['acertos'])],
  ["erros", num(ma['erros']), num(md_['erros'])],
])}
<p class="nota">Erros e invenções removidos: <strong>{travas['removidos']}</strong>.
Acertos perdidos: <strong>{travas['acertos_perdidos']}</strong> — seis deles são
abreviações que pertencem a <code>sinonimos.py</code> e já estão no arquivo de
candidatos à curadoria. Resistem {len(travas['resistentes'])} rótulos, todos de
TERMINAL A/B, onde a camada recebe o texto inteiro em vez da caixa do atributo.</p>
<h3>O dicionário antes e depois da curadoria</h3>
{tab(["indicador", "em uso", "curado"], [
  ["entradas", num(dic['atual']['entradas']), num(dic['curado']['entradas'])],
  ["aplicáveis como regra", num(dic['atual']['aplicaveis']), num(dic['curado']['aplicaveis'])],
  ["sugestões para curadoria", num(dic['atual']['sugestoes']), num(dic['curado']['sugestoes'])],
  ["marcadas como interpretação", num(dic['atual']['interpretacao']), num(dic['curado']['interpretacao'])],
  ["com uma única confirmação", num(dic['atual']['confirmacoes_1']), num(dic['curado']['confirmacoes_1'])],
])}
</section>""")

    # ---- secao 6: testes ----------------------------------------------------
    L.append(f"""<section><h2><span class="n">6</span>Testes, determinismo e reprodutibilidade</h2>
<div class="grade">
<div>{tab(["verificação", "resultado"], [
  ["suíte de testes (pytest)", esc(tes['pytest'])],
  ["testes das travas do dicionário", "25 casos, um por armadilha real"],
  ["determinismo (duas execuções iguais)", esc(tes['determinismo'])],
  ["seleção dos 240 itens do gabarito", "bit-idêntica ao reexecutar (semente 20251107)"],
  ["pares de junção", "congelados: resortear exige <code>--refazer-pares</code>"],
])}
<div class="aviso"><p><strong>Achado da reexecução:</strong> os pares de junção eram
sorteados a partir da saída do pipeline, então reexecutar o passo 1 depois de uma
nova rodada trocava os 150 pares <em>sob</em> as anotações, que são indexadas por
<code>par_id</code> — mudança silenciosa. O script agora preserva os pares por
padrão.</p></div></div>
<div><h3>Rodar tudo, na ordem</h3>
<pre class="bloco"><code>{esc('''# 1) suite de testes
.venv/bin/python -m pytest tests/ -q

# 2) determinismo: duas extracoes em pastas temporarias, comparadas registro a registro
bash scripts/17_testar_determinismo.sh

# 3) gabarito: selecao (pares preservados), adjudicacao, avaliacao
uv run --no-project --with pandas --with openpyxl python avaliacao/10_candidatos_caracteristicas.py
uv run --no-project --with pandas --with openpyxl python avaliacao/11_adjudicar_caracteristicas.py
uv run --no-project --with pandas --with openpyxl python avaliacao/evaluate_caracteristicas.py

# 4) curadoria do dicionario aprendido e efeito das travas
uv run --no-project --with pandas --with openpyxl python scripts/18_curar_aprendizado.py
uv run --no-project --with pandas --with openpyxl python avaliacao/13_efeito_travas.py

# 5) esta pagina e o relatorio detalhado
uv run --no-project --with pandas --with openpyxl python avaliacao/14_apresentacao_html.py
uv run --no-project --with pandas --with openpyxl python avaliacao/12_relatorio_html.py

# pipeline completo (reescreve artefatos/; sem --com-llm nao chama o Bedrock)
./scripts/rodar_completo.sh''')}</code></pre></div>
</div></section>

<section><h2><span class="n">7</span>O que ainda não está resolvido</h2>
<ol>
<li><strong>Classe.</strong> {m_classe.group(1) if m_classe else '—'} de
{m_classe.group(2) if m_classe else '—'} itens na classe certa. Dois erros são
sistemáticos: <code>TAMPAO</code> entra como <code>CAP</code> (não existe no PDM, e
aí a descrição inteira é preenchida na classe errada) e parafuso sextavado interno
cai em sextavado.</li>
<li><strong>Conversões que faltam.</strong> <code>41KGF/CM2</code> sai como
<code>41BAR</code> (deveria ser 40,2), <code>DN 25</code>/<code>DN 50</code> e o dash
<code>-20</code> de mangueira não viram polegada, e a referência de rolamento perde o
sufixo (<code>6010-2RS/C3</code> → <code>6010</code>). São regras de tabela.</li>
<li><strong>Caixa por atributo.</strong> A camada léxica recebe o texto inteiro, então
o terminal B decide o terminal A. É a origem dos rótulos que as travas não
consertam.</li>
<li><strong>Cobertura da junção.</strong>
{pt(f"{(base['itens'] - base['com_chave']) / base['itens']:.1%}")} da base não tem
chave de identidade e portanto nunca é comparada; e o recall de junção foi medido em
pares sorteados a partir de grupos que o próprio pipeline formou, o que o torna
otimista.</li>
<li><strong>Conferência humana pendente.</strong> {num(gold['revisao_humana'])} linhas
esperando revisão de uma pessoa do time; até lá o gabarito tem viés de LLM.</li>
</ol></section>

<footer>Gerado por <code>avaliacao/14_apresentacao_html.py</code>, que calcula cada
número a partir de <code>artefatos/</code> e <code>avaliacao/</code> — nenhum valor é
digitado no gerador. Detalhamento rótulo a rótulo, com erros e invenções nomeados:
<code>avaliacao/relatorio_caracteristicas.html</code> e
<code>avaliacao/resultado_caracteristicas.md</code>.</footer>
</div><script>{JS}</script></body></html>""")

    Path(a.saida).write_text("\n".join(L), encoding="utf-8")
    print(f"{a.saida} gravado ({len(''.join(L)) / 1024:.0f} KB)")
    print(f"  base: {num(base['itens'])} itens | SANEADO {est['SANEADO'] / base['itens']:.1%} | "
          f"completos {base['completos'] / base['itens']:.1%}")
    print(f"  gold: {gold['carac']} + {gold['classe']} + {gold['juncao']} rotulos | "
          f"precisao {precisao} | invencao {invencao}")
    print(f"  testes: {tes['pytest']} | determinismo: {tes['determinismo']}")


if __name__ == "__main__":
    main()
