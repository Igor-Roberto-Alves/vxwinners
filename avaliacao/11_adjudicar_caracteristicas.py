# -*- coding: utf-8 -*-
"""Adjudica as anotacoes independentes A e B das CARACTERISTICAS, da CLASSE e da
JUNCAO, e produz o conjunto-ouro. Mesmo metodo do 01_adjudicar.py.

Entradas
--------
  avaliacao/candidatos_caracteristicas.csv  universo de itens (240)
  avaliacao/pares_juncao_candidatos.csv     universo de pares (150) + fonte_par
  avaliacao/anotacoes_carac_A.jsonl         persona A (uma passada, ordem_A)
  avaliacao/anotacoes_carac_B.jsonl         persona B (outra passada, ordem_B)
  dados/03_padrao_cadastro_PDM.xlsx         para conferir atributo x classe
  avaliacao/revisao_humana_caracteristicas_respondida.csv   (opcional)

Alinhamento por (CODIGO_MATERIAL, campo), onde campo e:
  _CLASSE   um rotulo por item: ID_PDM ou FORA_DO_PDM
  _JUNCAO   um rotulo por par (CODIGO_MATERIAL = par_id): MESMO_ITEM |
            ITENS_DIFERENTES | INDETERMINADO
  <nome>    um rotulo por atributo obrigatorio que se aplica ao item

Comparacao do rotulo:
  atributos -> status + valor normalizado (maiusculo sem acento, espacos
               colapsados; part number e referencia so [A-Z0-9]; numero com
               virgula decimal e zero final irrelevante normalizados)
  _CLASSE e _JUNCAO -> so o valor, porque o proprio valor ja carrega o caso
               indecidivel (FORA_DO_PDM, INDETERMINADO)

Divergencia = rotulo diferente. Cada uma exige uma entrada em ADJUDICACOES,
escrita a mao pelo adjudicador depois de reexaminar o texto cru e o PDM; se
faltar alguma, o script ABORTA. Ele nunca decide sozinho.

Saidas
------
  avaliacao/gold_caracteristicas.csv          (item x atributo)
  avaliacao/gold_classe.csv                   (item)
  avaliacao/gold_juncao.csv                   (par)
  avaliacao/concordancia_caracteristicas.json acordo bruto e kappa de Cohen
  avaliacao/revisao_humana_caracteristicas.csv planilha para a conferencia humana
"""
import csv
import json
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
SEED_REVISAO = 20251107
FRACAO_REVISAO = 0.10

STATUS_VALIDOS = {"DEFINIDO", "AUSENTE", "INDEFINIVEL"}
JUNCAO_VALIDOS = {"MESMO_ITEM", "ITENS_DIFERENTES", "INDETERMINADO"}
# atributos cujo valor e codigo de catalogo: compara so [A-Z0-9]
CAMPOS_CODIGO = {"REFERENCIA", "REFERENCIA FABRICANTE", "MODELO EQUIPAMENTO"}

# ---------------------------------------------------------------------------
# Decisao do ADJUDICADOR para cada divergencia entre A e B.
# Escrita a mao, uma por uma, relendo o texto cru do item em
# candidatos_caracteristicas.csv (ou os dois textos do par em
# pares_juncao_cego.csv) contra dados/03_padrao_cadastro_PDM.xlsx.
#
# Regras que o adjudicador fixou ao decidir, e que valem para todo o gold:
#  R1. Material sem nenhuma palavra de material no texto -> AUSENTE. Preencher
#      a partir da classe de resistencia e extrapolacao.
#  R2. Material com palavra generica no texto (ACO, ACO ESPECIAL, INOX) ->
#      usa-se a lista do PDM e os outros atributos para desambiguar, quando a
#      combinacao deixa um unico valor possivel.
#  R3. No PDM050, ACO INOX A403 WP316 e ACO CARBONO A234 WPB sao conexoes de
#      solda de topo (atributo SCHEDULE, norma ASME B16.9). Item com CLASSE
#      PRESSAO, rosca, solda de encaixe, flange ou norma ASME B16.11/B16.5 e
#      forjado: A182 F316 ou A105.
#  R4. No vocabulario do PDM, ZINCADO e o eletrolitico e GALVANIZADO A FOGO e a
#      imersao a quente. Texto com "GALVANIZADO" -> GALVANIZADO A FOGO.
#  R5. A folga de rolamento esta no sufixo da referencia (o PDM diz isso no
#      formato de REFERENCIA): referencia sem /C3 = folga NORMAL.
#  R6. Part number: vale o formato do fabricante, inclusive a pontuacao que o
#      cadastro registra na coluna REFERENCIA_FABRICANTE; sufixo de revisao
#      (REV A) nao faz parte do part number. A comparacao entre anotadores e no
#      avaliador ignora pontuacao, entao 529-26-87581 e 5292687581 (item
#      27810757) contam como o mesmo rotulo e nao viram divergencia; o gold
#      guarda a grafia do fabricante, que e a que A anotou.
# ---------------------------------------------------------------------------
ADJUDICACOES = {
    ("10858863", "MATERIAL"): {
        "y_gold": "ACO LIGA", "status": "DEFINIDO", "evidencia": "ACO ESPECIAL | 12.9",
        "justificativa": "decisao do adjudicador (R2): o texto traz material (ACO ESPECIAL) e "
                         "a classe 12.9 do PDM002 so existe fora do inox (as opcoes inox sao "
                         "A2-70 e A4-70), logo ACO LIGA e o unico valor possivel da lista",
        "confianca": "MEDIA",
    },
    ("19469152", "MATERIAL"): {
        "y_gold": "ACO LIGA", "status": "DEFINIDO", "evidencia": "ACO ESPECIAL | CL 12.9",
        "justificativa": "decisao do adjudicador (R2): mesmo caso de 10858863 - ACO ESPECIAL "
                         "com classe 12.9 no PDM002 so pode ser ACO LIGA",
        "confianca": "MEDIA",
    },
    ("20504737", "MATERIAL"): {
        "y_gold": "", "status": "AUSENTE", "evidencia": "",
        "justificativa": "decisao do adjudicador (R1): PARAFUSO HEXAGONAL MA M20X80 8.8 S/ACAB "
                         "DIN 933 nao tem nenhuma palavra de material; deduzir ACO CARBONO da "
                         "classe 8.8 e extrapolacao, e preencher conta como invencao",
        "confianca": "MEDIA",
    },
    ("16613005", "MATERIAL"): {
        "y_gold": "ACO INOX FORJADO A182 F316", "status": "DEFINIDO",
        "evidencia": "FLANGE; TIPO:SOBREPOSTO SO; MAT:INOX; NORMA CONSTRUCAO:ASME B16.5",
        "justificativa": "decisao do adjudicador (R3): flange ASME B16.5 e peca forjada; "
                         "A403 WP316 e conexao de solda de topo (B16.9). Como as duas opcoes "
                         "inox do PDM050 sao 316, resta ACO INOX FORJADO A182 F316",
        "confianca": "ALTA",
    },
    ("22181613", "MATERIAL"): {
        "y_gold": "ACO INOX FORJADO A182 F316", "status": "DEFINIDO",
        "evidencia": "INOX 316 SOLDA ENCAIXE SW ASME B16.11",
        "justificativa": "decisao do adjudicador (R3): classe 3000# com solda de encaixe e "
                         "norma ASME B16.11 e conexao forjada; A403 WP316 e de solda de topo",
        "confianca": "ALTA",
    },
    ("23167204", "MATERIAL"): {
        "y_gold": "ACO INOX FORJADO A182 F316", "status": "DEFINIDO",
        "evidencia": "MATERIAL DE INOX 316 TIPO CONEXAO ROSCA ASME B16.11",
        "justificativa": "decisao do adjudicador (R3): classe 6000# com rosca e ASME B16.11 e "
                         "conexao forjada A182 F316",
        "confianca": "ALTA",
    },
    ("23460268", "MATERIAL"): {
        "y_gold": "ACO INOX FORJADO A182 F316", "status": "DEFINIDO",
        "evidencia": "INOX SW ASME B16.11",
        "justificativa": "decisao do adjudicador (R3): as duas opcoes inox do PDM050 sao 316 e "
                         "SW com B16.11 define a forjada A182 F316; o 304/316 nao esta em jogo",
        "confianca": "MEDIA",
    },
    ("26334178", "ACABAMENTO"): {
        "y_gold": "GALVANIZADO A FOGO", "status": "DEFINIDO", "evidencia": "GALVANIZADO",
        "justificativa": "decisao do adjudicador (R4): no vocabulario do PDM o eletrolitico se "
                         "escreve ZINCADO (branco/amarelo) e a imersao a quente GALVANIZADO A "
                         "FOGO, que e o unico 'galvanizado' da lista do PDM003",
        "confianca": "MEDIA",
    },
    ("13065631", "FOLGA"): {
        "y_gold": "NORMAL", "status": "DEFINIDO", "evidencia": "CODIGO:6000 ZZ",
        "justificativa": "decisao do adjudicador (R5): o PDM020 diz que a referencia traz o "
                         "sufixo de folga (/C3); referencia 6000-ZZ sem sufixo e folga normal "
                         "(CN), que e o padrao da designacao ISO",
        "confianca": "MEDIA",
    },
    ("21446483", "DIAMETRO INTERNO"): {
        "y_gold": "1.1/4POL", "status": "DEFINIDO", "evidencia": "DI:DN31",
        "justificativa": "decisao do adjudicador: DN31 (DN31,5) e um diametro da serie de "
                         "mangueiras hidraulicas e corresponde a 1.1/4POL; nao e erro de "
                         "digitacao",
        "confianca": "MEDIA",
    },
    ("29452826", "APLICACAO"): {
        "y_gold": "", "status": "INDEFINIVEL", "evidencia": "MANGUEIRA MULTIUSO AR COMPRIMIDO",
        "justificativa": "decisao do adjudicador: MULTIUSO e AR COMPRIMIDO sao dois valores da "
                         "lista do PDM012 e o texto traz os dois sem hierarquia; escolher um e "
                         "sorteio, logo o atributo e indefinivel",
        "confianca": "MEDIA",
    },
    ("P067", "_JUNCAO"): {
        "y_gold": "MESMO_ITEM", "status": "DEFINIDO",
        "evidencia": "UNF 1 IN/1\" x 1 POL SAE GRAU 5 carbono GALV FOGO x GALVANIZADO ASME B18.2.1",
        "justificativa": "decisao do adjudicador (R4): GALVANIZADO no vocabulario do PDM e "
                         "GALVANIZADO A FOGO, logo os dois registros tem os mesmos obrigatorios",
        "confianca": "MEDIA",
    },
    ("P149", "_JUNCAO"): {
        "y_gold": "INDETERMINADO", "status": "INDEFINIVEL",
        "evidencia": "SANDVIK REF:6903113-73 x SANDVIK REF 690.3113-73-00",
        "justificativa": "decisao do adjudicador: mesmo fabricante e mesma raiz de codigo, mas o "
                         "sufixo -00 da numeracao Sandvik pode designar outra versao da peca; so "
                         "com o texto cru nao se decide",
        "confianca": "MEDIA",
    },
}


# ------------------------------------------------------------- normalizacao ---
def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def norm_valor(v):
    """Normalizacao leve, usada no que o gold guarda: maiusculo, sem acento,
    espacos colapsados. Preserva a grafia do fabricante (pontos e hifens)."""
    return re.sub(r"\s+", " ", sem_acento(v or "").upper().strip())


def norm_cmp(campo, v):
    """Normalizacao de comparacao: part number sem pontuacao e numero sem zero
    decimal inutil (35,0MM = 35MM)."""
    v = norm_valor(v)
    if campo in CAMPOS_CODIGO:
        return re.sub(r"[^A-Z0-9]", "", v)
    m = re.fullmatch(r"(\d+)(?:,(\d*?)0*)?\s*([A-Z0-9/#]*)", v)
    if m:
        inteiro, dec, unid = m.group(1), m.group(2) or "", m.group(3)
        return inteiro + ("," + dec if dec else "") + unid
    return v


def rotulo(campo, anot):
    if campo in ("_CLASSE", "_JUNCAO"):
        return norm_cmp(campo, anot["y_gold"])
    return anot["status"] + "|" + norm_cmp(campo, anot["y_gold"])


def resumo(campo, anot):
    return anot["status"] + ":" + norm_cmp(campo, anot["y_gold"])


def kappa_cohen(pares):
    n = len(pares)
    if n == 0:
        return None
    po = sum(a == b for a, b in pares) / n
    ca, cb = Counter(a for a, _ in pares), Counter(b for _, b in pares)
    pe = sum(ca[c] * cb.get(c, 0) for c in ca) / (n * n)
    if pe >= 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


# ------------------------------------------------------------------- cargas ---
def carrega(nome):
    arq = RAIZ / f"anotacoes_carac_{nome}.jsonl"
    d = {}
    for i, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
        linha = linha.strip()
        if not linha:
            continue
        r = json.loads(linha)
        if r["status"] not in STATUS_VALIDOS:
            sys.exit(f"{arq.name}:{i}: status invalido {r['status']!r}")
        campo = r["campo"].strip()
        if campo == "_JUNCAO" and r["y_gold"] not in JUNCAO_VALIDOS:
            sys.exit(f"{arq.name}:{i}: rotulo de juncao invalido {r['y_gold']!r}")
        k = (str(r["CODIGO_MATERIAL"]).strip(), campo)
        if k in d:
            sys.exit(f"{arq.name}:{i}: par duplicado {k}")
        d[k] = r
    return d


def atributos_obrigatorios():
    """ID_PDM -> conjunto de atributos com OBRIGATORIO=S."""
    atr = pd.read_excel(REPO / "dados/03_padrao_cadastro_PDM.xlsx",
                        sheet_name="ATRIBUTOS", dtype=str).fillna("")
    obrig = defaultdict(set)
    for _, r in atr.iterrows():
        if r["OBRIGATORIO"].strip().upper() == "S":
            obrig[r["ID_PDM"].strip()].add(r["ATRIBUTO"].strip())
    return obrig


def main():
    # --- universo ----------------------------------------------------------
    with open(RAIZ / "candidatos_caracteristicas.csv", newline="", encoding="utf-8") as f:
        cand = list(csv.DictReader(f))
    estrato = {r["CODIGO_MATERIAL"].strip(): r["estrato"] for r in cand}
    with open(RAIZ / "pares_juncao_candidatos.csv", newline="", encoding="utf-8") as f:
        pares = list(csv.DictReader(f))
    fonte_par = {r["par_id"]: r["fonte_par"] for r in pares}

    A, B = carrega("A"), carrega("B")
    if set(A) != set(B):
        falta, sobra = set(A) - set(B), set(B) - set(A)
        sys.exit(f"universos de A e B diferentes: so em A {sorted(falta)[:5]} "
                 f"({len(falta)}) / so em B {sorted(sobra)[:5]} ({len(sobra)})")

    # cobertura: uma classe por item, uma juncao por par
    for nome, d in (("A", A), ("B", B)):
        itens = {c for (c, campo) in d if campo == "_CLASSE"}
        if itens != set(estrato):
            sys.exit(f"anotador {nome}: _CLASSE nao cobre os 240 itens "
                     f"(faltam {len(set(estrato) - itens)})")
        pp = {c for (c, campo) in d if campo == "_JUNCAO"}
        if pp != set(fonte_par):
            sys.exit(f"anotador {nome}: _JUNCAO nao cobre os {len(fonte_par)} pares "
                     f"(faltam {len(set(fonte_par) - pp)})")

    # cada atributo anotado tem de ser obrigatorio na classe que o anotador deu
    obrig = atributos_obrigatorios()
    problemas = []
    for nome, d in (("A", A), ("B", B)):
        classe = {c: d[(c, "_CLASSE")]["y_gold"] for c in estrato}
        for (cod, campo) in d:
            if campo.startswith("_"):
                continue
            pdm = classe[cod]
            if pdm == "FORA_DO_PDM" or campo not in obrig.get(pdm, set()):
                problemas.append(f"{nome}: {cod} {campo!r} nao e obrigatorio em {pdm}")
    if problemas:
        sys.exit("atributo fora da classe anotada:\n  " + "\n  ".join(problemas[:20]))

    # --- acordo e kappa ----------------------------------------------------
    chaves = sorted(A)
    por_campo = defaultdict(list)
    divergencias = []
    for k in chaves:
        cod, campo = k
        ra, rb = rotulo(campo, A[k]), rotulo(campo, B[k])
        por_campo[campo].append((ra, rb))
        if ra != rb:
            divergencias.append(k)

    metricas = {}
    for campo in sorted(por_campo):
        ps = por_campo[campo]
        metricas[campo] = {"n": len(ps),
                           "acordo": round(sum(a == b for a, b in ps) / len(ps), 4),
                           "kappa": round(kappa_cohen(ps), 4)}

    def bloco(filtro):
        ps = [p for campo, lst in por_campo.items() if filtro(campo) for p in lst]
        return {"n": len(ps),
                "acordo": round(sum(a == b for a, b in ps) / len(ps), 4),
                "kappa": round(kappa_cohen(ps), 4)}

    glob_carac = bloco(lambda c: not c.startswith("_"))
    glob_classe = bloco(lambda c: c == "_CLASSE")
    glob_juncao = bloco(lambda c: c == "_JUNCAO")
    glob_tudo = bloco(lambda c: True)

    print("=== acordo A x B por atributo ===")
    for campo, m in metricas.items():
        if campo.startswith("_"):
            continue
        print(f"  {campo:<24} n={m['n']:>4}  acordo={m['acordo']:.4f}  kappa={m['kappa']:.4f}")
    for nome, m in (("CARACTERISTICAS", glob_carac), ("CLASSE", glob_classe),
                    ("JUNCAO", glob_juncao), ("GLOBAL", glob_tudo)):
        print(f"  {nome:<24} n={m['n']:>4}  acordo={m['acordo']:.4f}  kappa={m['kappa']:.4f}")

    print(f"\ndivergencias: {len(divergencias)}")
    for k in divergencias:
        print(f"  {k[0]} {k[1]}: A={resumo(k[1], A[k])}  B={resumo(k[1], B[k])}")

    pendentes = [k for k in divergencias if k not in ADJUDICACOES]
    if pendentes:
        sys.exit(f"\n{len(pendentes)} divergencia(s) sem decisao em ADJUDICACOES - "
                 "releia o texto cru e o PDM e escreva a decisao:\n"
                 + "\n".join(f"  {k}" for k in pendentes))
    for k in ADJUDICACOES:
        if k not in divergencias:
            sys.exit(f"ADJUDICACOES tem par sem divergencia: {k}")

    # --- correcoes humanas (opcional) --------------------------------------
    corr = {}
    resp = RAIZ / "revisao_humana_caracteristicas_respondida.csv"
    if resp.exists():
        with open(resp, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("concordo_discordo", "").strip().upper() != "DISCORDO":
                    continue
                k = (r["CODIGO_MATERIAL"].strip(), r["campo"].strip())
                corr[k] = {"y_gold": r.get("valor_certo", "").strip(),
                           "status": (r.get("status_certo", "").strip().upper()
                                      or "DEFINIDO"),
                           "comentario": r.get("comentario", "").strip()}
        print(f"\nrevisao humana: {len(corr)} correcao(oes) incorporada(s)")

    # --- gold --------------------------------------------------------------
    linhas = []
    for k in chaves:
        cod, campo = k
        base = {"CODIGO_MATERIAL": cod,
                "estrato": estrato.get(cod) or fonte_par.get(cod, ""),
                "campo": campo,
                "anot_A": resumo(campo, A[k]), "anot_B": resumo(campo, B[k])}
        if k in corr:
            c = corr[k]
            linhas.append({**base, "y_gold": norm_valor(c["y_gold"]), "status": c["status"],
                           "evidencia": A[k]["evidencia"],
                           "justificativa": "revisao humana: " + (c["comentario"] or "valor corrigido"),
                           "origem_decisao": "revisao_humana", "confianca": "ALTA"})
        elif k in ADJUDICACOES:
            d = ADJUDICACOES[k]
            linhas.append({**base, "y_gold": norm_valor(d["y_gold"]), "status": d["status"],
                           "evidencia": d["evidencia"], "justificativa": d["justificativa"],
                           "origem_decisao": "adjudicado",
                           "confianca": d.get("confianca", "MEDIA")})
        else:
            a = A[k]
            linhas.append({**base, "y_gold": norm_valor(a["y_gold"]), "status": a["status"],
                           "evidencia": a["evidencia"] or B[k]["evidencia"],
                           "justificativa": a["justificativa"] or B[k]["justificativa"],
                           "origem_decisao": "acordo", "confianca": "ALTA"})

    COLS = ["CODIGO_MATERIAL", "estrato", "campo", "y_gold", "status", "evidencia",
            "justificativa", "anot_A", "anot_B", "origem_decisao", "confianca"]

    def grava(nome, filtro):
        sel = [l for l in linhas if filtro(l["campo"])]
        with open(RAIZ / nome, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(sel)
        return sel

    carac = grava("gold_caracteristicas.csv", lambda c: not c.startswith("_"))
    classe = grava("gold_classe.csv", lambda c: c == "_CLASSE")
    juncao = grava("gold_juncao.csv", lambda c: c == "_JUNCAO")

    # --- sanidade ----------------------------------------------------------
    for l in carac:
        coerente = (l["status"] == "DEFINIDO") == (l["y_gold"] != "")
        assert l["status"] == "INDEFINIVEL" or coerente, f"status x y_gold incoerente: {l}"
    assert len(classe) == len(estrato), "gold_classe.csv nao cobre os itens"
    assert len(juncao) == len(fonte_par), "gold_juncao.csv nao cobre os pares"
    nao_def = sum(1 for l in carac if l["status"] in ("AUSENTE", "INDEFINIVEL"))
    assert nao_def >= 60, f"so {nao_def} rotulos AUSENTE/INDEFINIVEL (minimo 60)"

    # --- concordancia ------------------------------------------------------
    exemplos = [{"codigo": k[0], "campo": k[1], "A": resumo(k[1], A[k]),
                 "B": resumo(k[1], B[k]),
                 "decisao_final": ADJUDICACOES[k]["status"] + ":"
                                  + norm_cmp(k[1], ADJUDICACOES[k]["y_gold"]),
                 "justificativa": ADJUDICACOES[k]["justificativa"]}
                for k in divergencias]
    conc = {"por_atributo": {c: m for c, m in metricas.items() if not c.startswith("_")},
            "classe": glob_classe, "juncao": glob_juncao,
            "caracteristicas": glob_carac, "global": glob_tudo,
            "divergencias_adjudicadas": len(divergencias),
            "exemplos_divergencia": exemplos}
    (RAIZ / "concordancia_caracteristicas.json").write_text(
        json.dumps(conc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # --- planilha da conferencia humana ------------------------------------
    rng = random.Random(SEED_REVISAO)
    obrigatorias, resto = [], []
    for l in linhas:
        if l["status"] == "INDEFINIVEL" or l["origem_decisao"] in ("adjudicado",
                                                                   "revisao_humana"):
            obrigatorias.append(("indefinivel_ou_divergencia", l))
        else:
            resto.append(l)
    amostra = rng.sample(resto, round(FRACAO_REVISAO * len(resto)))
    revisao = obrigatorias + [("amostra_10pct", l) for l in amostra]
    textos = {r["CODIGO_MATERIAL"]: (r["DESCRICAO_CURTA"], r["DESCRICAO_LONGA"])
              for r in cand}
    with open(RAIZ / "pares_juncao_cego.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            textos[r["par_id"]] = (r["longa_1"], r["longa_2"])
    COLS_REV = ["motivo", "CODIGO_MATERIAL", "campo", "texto_1", "texto_2",
                "y_gold", "status", "evidencia", "justificativa", "anot_A", "anot_B",
                "origem_decisao", "concordo_discordo", "valor_certo", "status_certo",
                "comentario"]
    with open(RAIZ / "revisao_humana_caracteristicas.csv", "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS_REV)
        w.writeheader()
        for motivo, l in sorted(revisao, key=lambda t: (t[0], t[1]["CODIGO_MATERIAL"],
                                                        t[1]["campo"])):
            t1, t2 = textos.get(l["CODIGO_MATERIAL"], ("", ""))
            w.writerow({"motivo": motivo, **{c: l[c] for c in
                        ("CODIGO_MATERIAL", "campo", "y_gold", "status", "evidencia",
                         "justificativa", "anot_A", "anot_B", "origem_decisao")},
                        "texto_1": t1, "texto_2": t2,
                        "concordo_discordo": "", "valor_certo": "", "status_certo": "",
                        "comentario": ""})

    # --- resumo ------------------------------------------------------------
    print("\n=== distribuicao de status (gold de caracteristicas) ===")
    dist = Counter(l["status"] for l in carac)
    for s in ("DEFINIDO", "AUSENTE", "INDEFINIVEL"):
        print(f"  {s:<12} {dist[s]:>4} ({dist[s] / len(carac):.1%})")
    print(f"\n=== classe ===\n  {Counter(l['y_gold'] for l in classe).most_common(6)}")
    print(f"=== juncao ===\n  {Counter(l['y_gold'] for l in juncao).most_common()}")
    print(f"\ngold_caracteristicas.csv: {len(carac)} rotulos | "
          f"gold_classe.csv: {len(classe)} | gold_juncao.csv: {len(juncao)}")
    print(f"revisao_humana_caracteristicas.csv: {len(revisao)} linhas "
          f"({len(obrigatorias)} obrigatorias + {len(amostra)} da amostra de 10%)")
    print("concordancia_caracteristicas.json gravado")


if __name__ == "__main__":
    main()
