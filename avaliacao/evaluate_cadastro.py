# -*- coding: utf-8 -*-
"""V2: avalia unidade, descricao e sobrevivente do pipeline contra os gabaritos curtos.

Uso:
  uv run --no-project --with pandas --with openpyxl python avaliacao/evaluate_cadastro.py \
      [--artefatos artefatos/] [--saida avaliacao/resultado_cadastro.md]

Le de --artefatos: saneado_base.csv (UNIDADE_PDM, UNIDADE_MOTIVO, DESCRICAO_PDM, ID_PDM)
e plano_juncao.csv (CODIGO, ACAO, USAR, ESTOQUE_CONSOLIDADO, CHAVE).
Le de avaliacao/: gold_unidade.csv, gold_descricao.csv, gold_sobrevivente.csv e as
anotacoes A e B (para repetir a concordancia no relatorio).
Le de dados/: o PDM (regras, ordem, valores, formatos) e a base crua (FABRICANTE).

Unidade
  predicao = FILA_FATOR quando UNIDADE_PDM vem vazia e o motivo pede o fator;
  senao, a propria UNIDADE_PDM. Acerto = predicao igual a unidade_esperada.
  ERRO GRAVE (a parte): o gabarito diz FILA_FATOR (embalagem) e o pipeline
  devolveu uma unidade: converteu embalagem sem o fator.
  RISCO (a parte, nao grave pela definicao do plano): o gabarito diz que a troca
  exige fator (KG->PC, UN de cabo->M, UN de tambor->L...) e o pipeline trocou
  a sigla sem pedir o fator.
Descricao
  (a) igualdade exata com DESCRICAO_PDM; (b) "modulo valores": mesma cabeca e
  mesma sequencia de nomes de caixas, ignorando os valores; (c) acerto por caixa;
  (d) cada regra verificavel do PDM, sobre o gabarito (sanidade), sobre as 40
  descricoes do pipeline e sobre TODAS as DESCRICAO_PDM do saneado_base.csv.
Sobrevivente
  acerto do codigo mantido ativo (contra a regra aplicada a mao), acerto do
  ESTOQUE_CONSOLIDADO (NAO_SOMAVEL no gabarito = unidades diferentes no cluster:
  qualquer soma do pipeline e erro), taxa de concorda_com_a_regra e quantas vezes
  o pipeline escolheu o mesmo que suprimentos escolheria.
"""
import argparse
import json
import math
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent

p = argparse.ArgumentParser()
p.add_argument("--artefatos", default=str(REPO / "artefatos"))
p.add_argument("--saida", default=str(RAIZ / "resultado_cadastro.md"))
a = p.parse_args()
ART = Path(a.artefatos)


# ------------------------------------------------------------------ utilidades
def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    m = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return ph, max(0.0, c - m), min(1.0, c + m)


def pct_ic(k, n):
    if n == 0:
        return "—"
    ph, lo, hi = wilson(k, n)
    return f"{ph:.1%} [{lo:.1%}–{hi:.1%}]"


def pct(k, n):
    return f"{k / n:.1%}" if n else "—"


def ws(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def num(s):
    try:
        return float(str(s).strip())
    except ValueError:
        return None


def kappa(pares):
    n = len(pares)
    po = sum(x == y for x, y in pares) / n
    ca, cb = Counter(x for x, _ in pares), Counter(y for _, y in pares)
    pe = sum(ca[c] * cb.get(c, 0) for c in ca) / (n * n)
    if pe >= 1.0:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1 - pe)


def tabela(cab, linhas):
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join("---" for _ in cab) + "|"]
    out += ["| " + " | ".join(str(c).replace("|", "\\|") for c in l) + " |" for l in linhas]
    return "\n".join(out)


# ------------------------------------------------------------------ PDM (xlsx)
X = REPO / "dados/03_padrao_cadastro_PDM.xlsx"
cl = pd.read_excel(X, "CLASSES", dtype=str).fillna("")
at = pd.read_excel(X, "ATRIBUTOS", dtype=str).fillna("")
sob = pd.read_excel(X, "SUBSTANTIVOS_SOBRESSALENTES", dtype=str).fillna("")
con = pd.read_excel(X, "SUBSTANTIVOS_CONEXOES", dtype=str).fillna("")

CABECAS, POR_REF = {}, set()
for r in cl.itertuples():
    cid = r.ID_PDM
    if "REFERENCIA DO FABRICANTE" in r.CRITERIO_IDENTIDADE:
        POR_REF.add(cid)
    if cid == "PDM110":
        CABECAS[cid] = set(sob.iloc[:, 0].str.strip())
    elif cid == "PDM050":
        CABECAS[cid] = set(con.iloc[:, 0].str.strip())
    elif r.QUALIFICADOR:
        CABECAS[cid] = {f"{r.SUBSTANTIVO.strip()} {q.strip()}" for q in r.QUALIFICADOR.split("|")}
    else:
        CABECAS[cid] = {r.SUBSTANTIVO.strip()}

ATR = defaultdict(dict)   # cid -> nome -> dict(ordem, obrig, quando, formato, valores)
for r in at.itertuples():
    ATR[r.ID_PDM][r.ATRIBUTO.strip()] = {
        "ordem": int(r.ORDEM), "obrig": r.OBRIGATORIO.strip() == "S",
        "quando": r.QUANDO_SE_APLICA.strip(), "formato": r.FORMATO,
        "valores": [v.strip() for v in r.VALORES_PERMITIDOS.split("|") if v.strip()]}

LIVRES = {"REFERENCIA FABRICANTE", "MODELO EQUIPAMENTO", "CA", "ROSCA"}  # codigos, sem checar abreviacao
PERMITIDOS_TOK = set()
for cid, d in ATR.items():
    for n, info in d.items():
        PERMITIDOS_TOK |= set(n.split())
        for v in info["valores"]:
            PERMITIDOS_TOK |= set(re.split(r"[\s;:,]+", v))
for hs in CABECAS.values():
    for h in hs:
        PERMITIDOS_TOK |= set(h.split())

# abreviacoes vistas no texto cru desta base (telegrafico): nenhuma pode sobrar na descricao
ABREV = {"PARAF", "SEXT", "ROL", "RIG", "ESF", "MANG", "HIDR", "PNEUM", "IND", "VALV", "RET",
         "ACAB", "ZB", "ZA", "ZINC", "GALV", "AC", "CARB", "COMP", "COMPR", "DIAM", "DI", "MAT",
         "NOM", "PRES", "PRESS", "TRAB", "PT", "REF", "FAB", "FABR", "APLIC", "MOD", "EQUIP",
         "COD", "PN", "P/N", "QTD", "CL", "ESP", "LARG", "ALOJ", "TERM", "ELET", "DISJ", "CONT",
         "LAMP", "LUBR", "LUBRIF", "FILT", "SEG", "TAM", "NR", "CONF", "BICROM", "ROSC", "PCA",
         "PÇ", "POT", "TRANSP", "CORR", "ISOL", "VED", "CILIND", "ESC", "MALEAV", "OX", "SS304",
         "SS316", "AISI", "INT", "EXT", "TRANSV", "MF", "MG", "CAB", "TEFLON"} - PERMITIDOS_TOK


def formato_ok(cid, nome, v):
    """None quando nao ha regra de formato verificavel para a caixa."""
    info = ATR[cid][nome]
    f = info["formato"].lower()
    if info["valores"] and cid != "PDM020":
        return None   # lista: vai para a regra 'valor da lista'
    if nome == "REFERENCIA" and cid == "PDM020":
        return bool(re.fullmatch(r"\d{3,5}(-[0-9A-Z]+)?(/C\d)?", v))
    if nome == "REFERENCIA" and cid == "PDM030":
        return bool(re.fullmatch(r"(5V|SPA|SPB|SPZ|A|B|C)\s?\d+", v))
    if "mm2" in f:
        return bool(re.fullmatch(r"\d+(,\d*[1-9])?MM2", v))
    if nome == "FAIXA":
        return bool(re.fullmatch(r"0-\d+(,\d*[1-9])?BAR", v))
    pol = r"(\d+\.)?\d+/\d+POL|\d+POL"
    mm = r"\d+(,\d*[1-9])?MM"
    if "rosca métrica: número + mm" in f:          # comprimento de parafuso: MM ou POL
        return bool(re.fullmatch(mm + "|" + pol, v))
    if "polegada" in f and "pol" in f:
        return bool(re.fullmatch(pol, v))
    if "+ mm" in f:
        return bool(re.fullmatch(mm, v))
    if "+ bar" in f:
        return bool(re.fullmatch(r"\d+(,\d*[1-9])?BAR", v))
    if f.strip() == "número + a":
        return bool(re.fullmatch(r"\d+(,\d*[1-9])?A", v))
    if f.strip() == "número + w":
        return bool(re.fullmatch(r"\d+(,\d*[1-9])?W", v))
    if f.strip() == "número + m":
        return bool(re.fullmatch(r"\d+(,\d*[1-9])?M", v))
    if f.strip() == "inteiro":
        return bool(re.fullmatch(r"\d+", v))
    if nome == "CA":
        return bool(re.fullmatch(r"\d{5}", v))
    return None


base = pd.read_excel(REPO / "dados/01_base_materiais.xlsx", sheet_name="BASE_MATERIAIS",
                     dtype=str).fillna("").set_index("CODIGO_MATERIAL")
MARCAS = set()
for cid in ("PDM100", "PDM110"):
    MARCAS |= set(ATR[cid]["FABRICANTE"]["valores"])
MARCAS |= {m.strip().upper() for m in base["FABRICANTE"].unique() if len(m.strip()) >= 4}
MARCAS -= PERMITIDOS_TOK

REGRAS = [
    ("R1_cabeca", "começa por substantivo + qualificador da classe (regras 1 e 2)"),
    ("R2_ordem", "caixas da classe, na ordem da coluna ORDEM (regra 1)"),
    ("R3_maiusculas", "maiúsculas, sem acento e sem cedilha (regra 3)"),
    ("R4_abreviacao", "sem abreviação (regra 4)"),
    ("R4_lista", "valor de lista é um dos VALORES_PERMITIDOS (regra 4)"),
    ("R5_formato", "formato de medida: 16,25MM, 1.1/4POL, BAR, MM2 (regras 5 e 6)"),
    ("R7_obrigatorio", "toda caixa obrigatória 'sempre' está presente (regra 7)"),
    ("R7_condicional", "obrigatório condicional presente quando a condição vale, e ausente quando não vale (regra 7)"),
    ("R8_9_fabricante", "fabricante/referência na descrição só em PDM100/PDM110, e lá obrigatórios (regras 8 e 9)"),
]


def _tipo(*ok):
    def f(cab, vals):
        t = vals.get("TIPO", "")
        return None if t in ("", "<PENDENTE>") else t in ok
    return f


def _redutor(cab, vals):
    return cab in ("TE REDUCAO", "LUVA REDUCAO", "BUCHA REDUCAO")


def _cond1(cab, vals):
    c = vals.get("NUMERO CONDUTORES", "")
    return None if not c.isdigit() else c == "1"


# QUANDO_SE_APLICA da aba ATRIBUTOS escrito como teste (cabeca, caixas) -> True/False/None
CONDICIONAIS = {
    "PDM062": [("CORRENTE NOMINAL", _tipo("MINIDISJUNTOR DIN", "CAIXA MOLDADA")),
               ("CAPACIDADE INTERRUPCAO", _tipo("MINIDISJUNTOR DIN", "CAIXA MOLDADA")),
               ("CURVA", _tipo("MINIDISJUNTOR DIN")), ("FAIXA AJUSTE", _tipo("MOTOR"))],
    "PDM061": [("FURO", _tipo("COMPRESSAO OLHAL", "PRE-ISOLADO FORQUILHA", "PRE-ISOLADO OLHAL"))],
    "PDM060": [("COR", _cond1)],
    "PDM050": [("TIPO", lambda c, v: c == "FLANGE"), ("FACE", lambda c, v: c == "FLANGE"),
               ("CONEXAO", lambda c, v: c != "FLANGE"), ("DIAMETRO REDUZIDO", _redutor)],
    "PDM081": [("ESPESSURA", _tipo("CORTE", "DESBASTE")), ("GRAO", _tipo("FLAP"))],
}


def partes(desc):
    segs = [s.strip() for s in str(desc).split(";")]
    cab = segs[0]
    caixas = []
    for s in segs[1:]:
        if not s:
            continue
        n, _, v = s.partition(":")
        caixas.append((n.strip(), v.strip()))
    return cab, caixas


def verificar(desc, cid, fab_cru=""):
    """dict regra -> lista de problemas (vazia = obedece)."""
    v = {r: [] for r, _ in REGRAS}
    cab, caixas = partes(desc)
    if cab not in CABECAS.get(cid, set()):
        v["R1_cabeca"].append(cab)
    if desc != desc.upper() or not desc.isascii():
        v["R3_maiusculas"].append("".join(sorted({c for c in desc if not c.isascii() or c.islower()})))
    ordens = []
    for n, val in caixas:
        if n not in ATR[cid]:
            v["R2_ordem"].append(f"caixa {n} nao e da classe")
            continue
        ordens.append(ATR[cid][n]["ordem"])
        if val in ("<PENDENTE>", ""):
            continue
        info = ATR[cid][n]
        if info["valores"] and n not in LIVRES and val not in info["valores"] and cid != "PDM020":
            v["R4_lista"].append(f"{n}={val}")
        fo = formato_ok(cid, n, val)
        if fo is False:
            v["R5_formato"].append(f"{n}={val}")
        if n not in LIVRES and n != "REFERENCIA":
            for t in re.split(r"[\s;:,]+", val):
                if t in ABREV or (re.fullmatch(r"[A-Z]{2,}\.", t) and t[:-1] not in PERMITIDOS_TOK):
                    v["R4_abreviacao"].append(f"{n}={val}")
                    break
            if re.search(r"(^|\s)[SCP]/", val):
                v["R4_abreviacao"].append(f"{n}={val}")
    if ordens != sorted(ordens) or len(ordens) != len(set(ordens)):
        v["R2_ordem"].append("fora da ORDEM")
    nomes = {n for n, _ in caixas}
    for n, info in ATR[cid].items():
        if info["obrig"] and info["quando"] == "sempre" and n not in nomes:
            v["R7_obrigatorio"].append(n)
    vals = dict(caixas)
    for exigida, cond in CONDICIONAIS.get(cid, []):
        aplica = cond(cab, vals)
        if aplica is None:
            continue
        if aplica and exigida not in nomes:
            v["R7_condicional"].append(f"falta {exigida}")
        if not aplica and exigida in nomes:
            v["R7_condicional"].append(f"{exigida} nao se aplica")
    if cid in POR_REF:
        for n in ("FABRICANTE", "REFERENCIA FABRICANTE"):
            if n not in nomes:
                v["R8_9_fabricante"].append(f"falta {n}")
    else:
        if nomes & {"FABRICANTE", "REFERENCIA FABRICANTE"}:
            v["R8_9_fabricante"].append("caixa de fabricante em classe de especificacao")
        marcas = set(MARCAS)
        if len(fab_cru.strip()) >= 3:
            marcas.add(fab_cru.strip().upper())
        for m in marcas:
            if re.search(r"(^|[\s;:,])" + re.escape(m) + r"($|[\s;:,])", desc):
                v["R8_9_fabricante"].append(f"marca {m} na descricao")
                break
    return v


# ------------------------------------------------------------------ carga
san = pd.read_csv(ART / "saneado_base.csv", dtype=str, keep_default_na=False).set_index("CODIGO_MATERIAL")
plano = pd.read_csv(ART / "plano_juncao.csv", dtype=str, keep_default_na=False)
gu = pd.read_csv(RAIZ / "gold_unidade.csv", dtype=str, keep_default_na=False)
gd = pd.read_csv(RAIZ / "gold_descricao.csv", dtype=str, keep_default_na=False)
gs = pd.read_csv(RAIZ / "gold_sobrevivente.csv", dtype=str, keep_default_na=False)
md = [f"# Resultado: gabarito de cadastro (V2) — unidade, descrição e sobrevivente",
      "",
      f"Gerado por `avaliacao/evaluate_cadastro.py` em {datetime.now():%Y-%m-%d %H:%M}, "
      f"sobre `{ART}`. Gabaritos: `gold_unidade.csv` ({len(gu)}), `gold_descricao.csv` "
      f"({len(gd)}), `gold_sobrevivente.csv` ({len(gs)} clusters). Sorteio: "
      "`20_candidatos_cadastro.py` (semente 20261107); adjudicação: `21_adjudicar_cadastro.py`.",
      "", "IC = intervalo de confiança de 95% de Wilson.", ""]

# ------------------------------------------------------------------ concordancia A x B
CAMPOS = {"unidade": ["id_pdm", "unidade_esperada", "exige_fator"],
          "descricao": ["id_pdm", "descricao"],
          "sobrevivente": ["sobrevivente_esperado", "estoque_consolidado_esperado",
                           "concorda_com_a_regra"]}
ann = {}
for nome in "AB":
    ann[nome] = {(r["tarefa"], r["item_id"]): r for r in
                 (json.loads(l) for l in (RAIZ / f"anotacoes_cadastro_{nome}.jsonl")
                  .read_text(encoding="utf-8").splitlines() if l.strip())}
linhas_k = []
todos = []
nao_triv = []
for t, cs in CAMPOS.items():
    ks = sorted(k for k in ann["A"] if k[0] == t)
    for c in cs:
        ps = [(str(ann["A"][k][c]), str(ann["B"][k][c])) for k in ks]
        todos += ps
        if c != "id_pdm":
            nao_triv += ps
        linhas_k.append([t, c, len(ps), pct(sum(x == y for x, y in ps), len(ps)), f"{kappa(ps):.3f}"])
    if t == "descricao":
        ps = []
        for k in ks:
            da = dict(map(tuple, ann["A"][k]["atributos"]))
            db = dict(map(tuple, ann["B"][k]["atributos"]))
            ps += [(da.get(n, "(fora)"), db.get(n, "(fora)")) for n in sorted(set(da) | set(db))]
        linhas_k.append([t, "por caixa (atributo)", len(ps), pct(sum(x == y for x, y in ps), len(ps)),
                         f"{kappa(ps):.3f}"])
linhas_k.append(["**global**", "todos os campos", len(todos),
                 pct(sum(x == y for x, y in todos), len(todos)), f"{kappa(todos):.3f}"])
linhas_k.append(["**global**", "sem id_pdm (que não divergiu)", len(nao_triv),
                 pct(sum(x == y for x, y in nao_triv), len(nao_triv)), f"{kappa(nao_triv):.3f}"])
n_adj = sum((g["origem_decisao"] == "adjudicado").sum() for g in (gu, gd, gs))
md += ["## 0. Concordância entre as anotações A e B", "",
       "A = analista de cadastro (PDM ao pé da letra); B = suprimentos/almoxarifado (saldo e uso). "
       "Passadas separadas, em ordens diferentes, lendo só a linha crua e o PDM. "
       f"Itens com divergência: {n_adj} (todos adjudicados com justificativa escrita).", "",
       tabela(["tarefa", "campo", "n", "acordo bruto", "kappa de Cohen"], linhas_k), ""]

# ------------------------------------------------------------------ V2.1 unidade
def pred_unidade(cod):
    if cod not in san.index:
        return "AUSENTE_NO_SANEADO", ""
    u, m = san.at[cod, "UNIDADE_PDM"].strip(), san.at[cod, "UNIDADE_MOTIVO"].strip()
    if not u and "fator" in m.lower():
        return "FILA_FATOR", m
    return (u or "VAZIO"), m


res_u = []
for g in gu.to_dict("records"):
    pu, mot = pred_unidade(g["CODIGO_MATERIAL"])
    ok = pu == g["unidade_esperada"]
    grave = g["unidade_esperada"] == "FILA_FATOR" and pu not in ("FILA_FATOR",)
    grave = grave and pu not in ("VAZIO", "AUSENTE_NO_SANEADO")
    orig = g["unidade_original"].replace("Ç", "C")
    risco = (g["exige_fator"] == "SIM" and g["unidade_esperada"] != "FILA_FATOR"
             and pu not in ("FILA_FATOR", "VAZIO") and pu != orig and "fator" not in mot.lower())
    sem_motivo = pu not in ("FILA_FATOR", "VAZIO") and pu != g["unidade_original"] and not mot
    res_u.append({**g, "pred": pu, "motivo": mot, "ok": ok, "grave": grave, "risco": risco,
                  "sem_motivo": sem_motivo})
ru = pd.DataFrame(res_u)
falso = (ru.estrato == "incompativel") & (ru.unidade_esperada == ru.unidade_original)
falsos = [f"{r.item_id} {san.at[r.CODIGO_MATERIAL, 'ID_PDM']}≠{r.id_pdm}" for r in ru[falso].itertuples()]
lin = []
for e in ["sinonimo", "embalagem", "incompativel", "ja_correta"]:
    d = ru[ru.estrato == e]
    lin.append([e, len(d), int(d.ok.sum()), pct_ic(int(d.ok.sum()), len(d)), int(d.grave.sum()),
                int(d.risco.sum())])
lin.append(["**total**", len(ru), int(ru.ok.sum()), pct_ic(int(ru.ok.sum()), len(ru)),
            int(ru.grave.sum()), int(ru.risco.sum())])
md += ["## 1. Unidade de medida (V2.1)", "",
       "Avalia `UNIDADE_PDM` + `UNIDADE_MOTIVO`. Predição `FILA_FATOR` = unidade vazia com motivo "
       "pedindo o fator de conversão.", "",
       tabela(["estrato", "n", "acertos", "precisão [IC 95%]",
               "ERRO GRAVE: converteu embalagem sem fator", "risco: trocou grandeza sem fator"], lin), "",
       f"- **Erros graves (embalagem convertida sem fator): {int(ru.grave.sum())} de "
       f"{int((ru.unidade_esperada == 'FILA_FATOR').sum())} itens de embalagem.**",
       f"- Trocas de grandeza sem fator (o gabarito diz `exige_fator=SIM` e a unidade-alvo está certa, "
       f"mas o saldo muda de significado — KG→PC, UN de cabo→M, UN de tambor→L, UN/PC→PR): "
       f"**{int(ru.risco.sum())} de {int(((ru.exige_fator == 'SIM') & (ru.unidade_esperada != 'FILA_FATOR')).sum())}**. "
       "Não é erro grave pela definição do plano, mas mexe no saldo do mesmo jeito.",
       f"- Alarme de classe incompatível falso (o pipeline trocou a unidade, mas a unidade crua já era "
       f"a da classe certa, lida no texto): **{len(falsos)} de {int((ru.estrato == 'incompativel').sum())}** "
       f"no estrato incompatível. Classe do pipeline x classe do gabarito: {', '.join(falsos) or '—'}.",
       f"- Unidade trocada sem `UNIDADE_MOTIVO` preenchido: {int(ru.sem_motivo.sum())} "
       f"({', '.join(sorted(set(ru[ru.sem_motivo].unidade_original)))})." if ru.sem_motivo.any() else
       "- Toda troca de unidade veio com motivo.", ""]
err = ru[~ru.ok | ru.risco]
if len(err):
    md += ["### Erros e riscos de unidade, um a um", "",
           tabela(["item", "código", "estrato", "crua", "gabarito", "exige fator", "pipeline", "motivo do pipeline",
                   "tipo", "justificativa do gabarito"],
                  [[r.item_id, r.CODIGO_MATERIAL, r.estrato, r.unidade_original, r.unidade_esperada,
                    r.exige_fator, r.pred, r.motivo[:70],
                    "GRAVE" if r.grave else ("erro" if not r.ok else "risco"), r.justificativa[:110]]
                   for r in err.itertuples()]), ""]

# ------------------------------------------------------------------ V2.2 descricao
res_d = []
for g in gd.to_dict("records"):
    cod = g["CODIGO_MATERIAL"]
    pdesc = ws(san.at[cod, "DESCRICAO_PDM"]) if cod in san.index else ""
    pcid = san.at[cod, "ID_PDM"] if cod in san.index else ""
    gdesc = ws(g["descricao_esperada"])
    gc, gcx = partes(gdesc)
    pc, pcx = partes(pdesc)
    gdict, pdict = dict(gcx), dict(pcx)
    caixas_ok = sum(pdict.get(n) == v for n, v in gcx)
    res_d.append({**g, "pdesc": pdesc, "pcid": pcid, "exata": pdesc == gdesc,
                  "modulo": gc == pc and [n for n, _ in gcx] == [n for n, _ in pcx],
                  "cabeca_ok": gc == pc, "classe_ok": pcid == g["id_pdm"],
                  "caixas_ok": caixas_ok, "caixas_n": len(gcx),
                  "dif": [f"{n}: gab={gdict.get(n, '(fora)')} / pipe={pdict.get(n, '(fora)')}"
                          for n in list(dict.fromkeys([n for n, _ in gcx] + [n for n, _ in pcx]))
                          if gdict.get(n) != pdict.get(n)],
                  "viol_gold": verificar(gdesc, g["id_pdm"]),
                  "viol_pipe": verificar(pdesc, pcid, base.at[cod, "FABRICANTE"]) if pcid else None})
rd = pd.DataFrame(res_d)
n = len(rd)
cx_ok, cx_n = int(rd.caixas_ok.sum()), int(rd.caixas_n.sum())
lin = [["igualdade exata com DESCRICAO_PDM", int(rd.exata.sum()), n, pct_ic(int(rd.exata.sum()), n)],
       ["igualdade módulo valores (mesma cabeça e mesmas caixas na mesma ordem)",
        int(rd.modulo.sum()), n, pct_ic(int(rd.modulo.sum()), n)],
       ["cabeça (substantivo + qualificador) igual", int(rd.cabeca_ok.sum()), n,
        pct_ic(int(rd.cabeca_ok.sum()), n)],
       ["classe (ID_PDM) igual", int(rd.classe_ok.sum()), n, pct_ic(int(rd.classe_ok.sum()), n)],
       ["caixas do gabarito com o mesmo valor no pipeline", cx_ok, cx_n, pct_ic(cx_ok, cx_n)]]
por_fam = []
for f, d in rd.groupby("estrato"):
    por_fam.append([f, len(d), int(d.exata.sum()), int(d.modulo.sum()), int(d.cabeca_ok.sum())])

# regras: gabarito, pipeline nos 40, base inteira
cnt_g, cnt_p, cnt_b, ex_b = Counter(), Counter(), Counter(), defaultdict(list)
for r in res_d:
    for k, v in r["viol_gold"].items():
        cnt_g[k] += bool(v)
    if r["viol_pipe"]:
        for k, v in r["viol_pipe"].items():
            cnt_p[k] += bool(v)
tot_b = 0
alguma_b = 0
for cod, r in san.iterrows():
    cid, desc = r["ID_PDM"], r["DESCRICAO_PDM"]
    if not cid or not desc or cid not in ATR:
        continue
    tot_b += 1
    v = verificar(desc, cid, base.at[cod, "FABRICANTE"] if cod in base.index else "")
    alguma_b += any(v.values())
    for k, x in v.items():
        if x:
            cnt_b[k] += 1
            if len(ex_b[k]) < 4:
                ex_b[k].append(f"`{cod}` {cid}: {'; '.join(x)[:90]}")
lin_r = [[desc, f"{cnt_g[k]} / {n}", f"{cnt_p[k]} / {n}", f"{cnt_b[k]:,} / {tot_b:,} ({pct(cnt_b[k], tot_b)})",
          "<br>".join(ex_b[k]) or "—"] for k, desc in REGRAS]
lin_r.append(["**alguma regra**", f"{sum(any(r['viol_gold'].values()) for r in res_d)} / {n}",
              f"{sum(any(r['viol_pipe'].values()) for r in res_d if r['viol_pipe'])} / {n}",
              f"{alguma_b:,} / {tot_b:,} ({pct(alguma_b, tot_b)})", ""])
md += ["## 2. Descrição no padrão PDM (V2.2)", "",
       "Rótulo: a descrição que o PDM manda escrever, com os valores tirados do texto cru "
       "(obrigatório ausente ou ambíguo = `<PENDENTE>`; opcional só se o texto traz).", "",
       tabela(["medida", "acertos", "n", "taxa [IC 95%]"], lin), "",
       tabela(["família", "n", "exata", "módulo valores", "cabeça igual"], por_fam), "",
       "### Regras verificáveis do PDM, uma a uma", "",
       "Contagem de descrições que **violam** cada regra. A coluna do gabarito é sanidade "
       "(tem de ser zero); a da base inteira é o invariante sobre todas as `DESCRICAO_PDM` com classe.", "",
       tabela(["regra", "gabarito (40)", "pipeline nos 40", "pipeline na base inteira", "exemplos na base"], lin_r), ""]
md += ["### Divergências de descrição, uma a uma", ""]
for r in res_d:
    if r["exata"]:
        continue
    vp = {k: v for k, v in (r["viol_pipe"] or {}).items() if v}
    md += [f"- **{r['item_id']}** `{r['CODIGO_MATERIAL']}` ({r['estrato']}, classe gabarito {r['id_pdm']}, "
           f"pipeline {r['pcid'] or '—'}) — módulo valores: {'sim' if r['modulo'] else 'não'}",
           f"  - gabarito: `{r['descricao_esperada']}`",
           f"  - pipeline: `{r['pdesc'] or '(vazia)'}`",
           f"  - caixas diferentes: {'; '.join(r['dif'])[:400] or '—'}"]
    if vp:
        md.append(f"  - regras violadas pelo pipeline: " +
                  "; ".join(f"{k} ({', '.join(v)[:80]})" for k, v in vp.items()))
md.append("")

# ------------------------------------------------------------------ V2.3 sobrevivente
pl = plano.set_index("CODIGO")
res_s = []
for g in gs.to_dict("records"):
    cods = g["codigos"].split("|")
    linhas = pl.reindex(cods)
    presentes = linhas["ACAO"].notna().all()
    ativos = [c for c in cods if presentes and linhas.at[c, "ACAO"] == "MANTER ATIVO"]
    integro = presentes and len(ativos) == 1 and linhas["CHAVE"].nunique() == 1 and \
        all(linhas.at[c, "USAR"] == ativos[0] for c in cods if c != ativos[0])
    ps = ativos[0] if len(ativos) == 1 else ""
    pe = num(linhas.at[ps, "ESTOQUE_CONSOLIDADO"]) if ps else None
    ge = g["estoque_consolidado_esperado"]
    est_ok = (ge != "NAO_SOMAVEL" and pe is not None and abs(pe - float(ge)) < 1e-6)
    res_s.append({**g, "integro": integro, "pred": ps, "pred_est": pe,
                  "sob_ok": ps == g["sobrevivente_esperado"], "est_ok": est_ok,
                  "igual_supr": ps == g["sobrevivente_suprimentos"]})
rs = pd.DataFrame(res_s)
n = len(rs)
k_conc = int((rs.concorda_com_a_regra == "SIM").sum())
lin = [["cluster íntegro no plano (mesma chave, um MANTER ATIVO, bloqueados apontam para ele)",
        int(rs.integro.sum()), n, pct_ic(int(rs.integro.sum()), n)],
       ["sobrevivente = regra aplicada à mão nas linhas cruas", int(rs.sob_ok.sum()), n,
        pct_ic(int(rs.sob_ok.sum()), n)],
       ["ESTOQUE_CONSOLIDADO = soma esperada", int(rs.est_ok.sum()), n, pct_ic(int(rs.est_ok.sum()), n)],
       ["concorda_com_a_regra = SIM (suprimentos escolheria o mesmo código)", k_conc, n, pct_ic(k_conc, n)],
       ["pipeline escolheu o código que suprimentos escolheria", int(rs.igual_supr.sum()), n,
        pct_ic(int(rs.igual_supr.sum()), n)]]
por_e = [[e, len(d), int(d.sob_ok.sum()), int(d.est_ok.sum()), int((d.concorda_com_a_regra == "SIM").sum())]
         for e, d in rs.groupby("estrato")]
md += ["## 3. Sobrevivente e consolidação de estoque (V2.3)", "",
       "Regra escrita (06_juntar.py): ATIVO > completude > movimentação mais recente > valor em estoque > "
       "código mais antigo. No gabarito, a completude foi julgada lendo o texto cru (fração dos "
       "obrigatórios informados), não copiada da coluna COMPLETUDE.", "",
       tabela(["medida", "acertos", "n", "taxa [IC 95%]"], lin), "",
       tabela(["estrato", "n", "sobrevivente certo", "estoque certo", "concorda com a regra"], por_e), ""]
md += ["### Clusters com erro ou em que a regra não convence", "",
       tabela(["cluster", "estrato", "códigos", "gabarito (regra)", "pipeline", "estoque gab.", "estoque pipe",
               "concorda", "suprimentos escolheria", "justificativa"],
              [[r.item_id, r.estrato, r.codigos.replace("|", " "), r.sobrevivente_esperado, r.pred or "—",
                r.estoque_consolidado_esperado, "—" if r.pred_est is None else f"{r.pred_est:g}",
                r.concorda_com_a_regra, r.sobrevivente_suprimentos, r.justificativa[:160]]
               for r in rs.itertuples() if not (r.sob_ok and r.est_ok and r.concorda_com_a_regra == "SIM")]), ""]

# ------------------------------------------------------------------ resumo
md[7:7] = ["## Resumo", "",
           f"- **Unidade:** precisão {pct_ic(int(ru.ok.sum()), len(ru))} em {len(ru)} itens; "
           f"**{int(ru.grave.sum())} erro(s) grave(s)** de embalagem convertida sem fator; "
           f"{int(ru.risco.sum())} troca(s) de grandeza sem fator.",
           f"- **Descrição:** igualdade exata {pct_ic(int(rd.exata.sum()), len(rd))}; módulo valores "
           f"{pct_ic(int(rd.modulo.sum()), len(rd))}; caixas certas {pct_ic(cx_ok, cx_n)}; "
           f"na base inteira, {pct(alguma_b, tot_b)} das {tot_b:,} descrições violam alguma regra verificável.",
           f"- **Sobrevivente:** acerto {pct_ic(int(rs.sob_ok.sum()), n)}; estoque consolidado "
           f"{pct_ic(int(rs.est_ok.sum()), n)}; concorda com a regra {pct_ic(k_conc, n)}.",
           f"- **Concordância A×B:** acordo bruto {pct(sum(x == y for x, y in nao_triv), len(nao_triv))}, "
           f"kappa {kappa(nao_triv):.3f} (campos de rótulo, sem id_pdm); {n_adj} itens adjudicados.", ""]

Path(a.saida).write_text("\n".join(md) + "\n", encoding="utf-8")
print("\n".join(md[7:13]))
print(f"\ngravado: {a.saida}")
