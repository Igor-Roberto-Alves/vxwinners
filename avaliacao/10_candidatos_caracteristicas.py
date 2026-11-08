# -*- coding: utf-8 -*-
"""Seleciona os candidatos do conjunto-ouro de CARACTERISTICAS TECNICAS, CLASSE
e JUNCAO. Reproduzivel: semente fixa, regras explicitas, nenhuma escolha manual.

Independencia do pipeline
-------------------------
As partes A (caracteristicas) e B (classe) leem SO dados/01_base_materiais.xlsx
(texto cru) e dados/03_padrao_cadastro_PDM.xlsx (o padrao). Nada de artefatos/.

A parte C (juncao) e a unica excecao autorizada pelo protocolo: le
artefatos/saneado_base.csv APENAS para SORTEAR os pares (chave de identidade,
descricao padronizada, similaridade). O rotulo do par nao usa nada disso: a
anotacao e feita sobre pares_juncao_cego.csv, que traz so o texto cru dos dois
codigos, em ordem sorteada, sem chave, sem cluster e sem a fonte do par.

A coluna familia_prevista e um PALPITE de selecao (regex sobre o substantivo do
texto), usado so para estratificar. A classe verdadeira de cada item e o rotulo
ID_PDM da parte B, anotado a partir do texto contra o PDM; ela pode divergir
da familia_prevista e da coluna GRUPO_MERCADORIA, que erra nesta base.

Estratos de selecao (ordem de aplicacao; um item fica no primeiro que o pegou)
-----------------------------------------------------------------------------
  fora_pdm      substantivo que nenhuma classe do PDM cobre (TAMPAO nao esta em
                SUBSTANTIVOS_CONEXOES) e o quase-acerto CAIXA MANCAL
  irma:<x>      classes irmas que se confundem, 4 itens por irma
  armadilha:<x> as armadilhas conhecidas de extracao, 9 itens por armadilha
  grupo_errado  familia do texto != GRUPO_MERCADORIA da coluna
  estilo:<e>    preenchimento das cotas por familia, metade estruturado,
                metade telegrafico

Saidas
------
  candidatos_caracteristicas.csv  240 itens, linha crua + familia/estilo/armadilhas
  pares_juncao_candidatos.csv     150 pares, com fonte_par (so para o avaliador)
  pares_juncao_cego.csv           os mesmos 150 pares as cegas, para anotar
"""
import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

_ap = argparse.ArgumentParser(description=__doc__)
_ap.add_argument("--refazer-pares", action="store_true",
                 help="resorteia os pares de juncao (exige reanotar a parte C)")
REFAZER_PARES = _ap.parse_args().refazer_pares

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
SEED = 20251107
N_ITENS = 240
N_POR_IRMA = 4
N_POR_ARMADILHA = 9

rng = np.random.RandomState(SEED)


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


# ---------------------------------------------------------------- base crua ---
base = pd.read_excel(REPO / "dados/01_base_materiais.xlsx",
                     sheet_name="BASE_MATERIAIS", dtype=str).fillna("")
COLS_BASE = list(base.columns)
base["_curta"] = base["DESCRICAO_CURTA"].map(lambda s: sem_acento(s).upper())
base["_longa"] = base["DESCRICAO_LONGA"].map(lambda s: sem_acento(s).upper())
base["_txt"] = base["_curta"] + " || " + base["_longa"]
# nucleo: sem o prefixo de bloqueio, para o substantivo cair na primeira palavra
base["_nuc"] = base["_longa"].str.replace(
    r"^\s*NAO UTILIZAR\s*[-,]?\s*(USAR COD\.?\s*\d+)?\s*[-,]?\s*", "", regex=True)

# ------------------------------------------------------------------- estilo ---
# estruturado = tem pelo menos dois pares "ATRIBUTO: VALOR"; o resto e telegrafico
base["estilo"] = np.where(base["_longa"].str.count(r":") >= 2,
                          "estruturado", "telegrafico")

# -------------------------------------------------- familia prevista (regex) ---
# ordem importa: o primeiro padrao que casar define a familia.
SOBRESSALENTE = (
    r"ADAPTADOR|ADDAPTADOR|AMORTECEDOR|AMORTEEDOR|ANEL DESGASTE|ANEL EXPULSOR"
    r"|ANEL LABIRINTO|ANEL VEDACAO|DESGASTE|EXPULSOR|LABIRINTO|BARRA TENSORA"
    r"|VERGALHAO TENSORA|BRACO SUSPENSAO|BUCHA|BUHCA|BCUHA|BUCA|CABECOTE"
    r"|CARCACA|CHAPA LATERAL|CHAAP|CILINDRO|CIINDRO|CONCAVO|CONCAOV|CONTRAEIXO"
    r"|CUBO RODA|CUNHA|CUNNHA|DENTE CACAMBA|DENET|DISCO FREIO|EIXO|ENGRENAGEM"
    r"|ENGRNEAGEM|ENGREENAGEM|GRELHA|LAMINA RASPADOR|LEVANTADOR|LEVANTAOR"
    r"|LUVA EIXO|MANDIBULA|MANTO|MATO|PALHETA|PASTILHA|PASTILLHA|PINHAO|PINO"
    r"|PITAO|PISTAO|PLACA|PLCA|RASPADOR|REVESTIMENTO|RODA GUIA|ROLETE|ROLEETE"
    r"|ROTOR|SAPATA|SEGMENTO|SEMGENTO|TAMBOR|TABOR|TAMPA|TAAMPA|TAPMA|TAMPPA"
    r"|TAMA|TELA|VEDACAO EIXO|VEADCAO|VIGA"
)
FAMILIA_REGRAS = [
    # EPI antes de LUVA (LUVA SEGURANCA) e de CALCADO/BOTINA
    ("outras", r"^(LUVA SEG|LUVA DE SEG|CALCADO|CAL\b|BOTINA|BOTA |OCULOS)"),
    # sobressalentes antes de tudo: muitos substantivos colidem (BUCHA, LUVA, TAMPA)
    ("sobressalentes", r"^(" + SOBRESSALENTE + r")\b"),
    ("outras", r"^(FILTRO|FILT|FLTRO|FITRO|FILRTO|FILTRRO|ELEMENTO FILTRANTE)"),
    ("fixadores", r"^(PARAF|PARAAF|PRAFUSO|PARAUSO|PARAUFSO|PAARAFUSO|PARAFSO"
                  r"|PARAFUOS|PARAFSUO|PARFAUSO|PARAAFUSO|PARRAFUSO|PARAFUO"
                  r"|PAAFUSO|PORCA|PCA\b|ARRUELA|ARRUELLA|ARREULA|ARURELA|ARR\b"
                  r"|BARRA ROSCADA|BARRRA|VERGALHAO ROSCAD|VERGALHAO\b)"),
    ("vedacao", r"^(ANEL O|O.?RING|ORING|ANEL RETENTOR|RETENTOR|RET\b|RET\."
                r"|JUNTA|JTA)"),
    ("rolamentos", r"^(ROLAMENTO|ROLAMEENTO|ROLAAMENTO|ROLAMENOT|ROL\b|ROL\."
                   r"|MANCAL|CAIXA MANCAL)"),
    ("valvulas", r"^(VALVULA|VALV|VALUVLA|V.?LVULA)"),
    ("mangueiras", r"^(MANGUEIRA|MANGUERA|MANGUEIAR|MANGGUEIRA|MAGUEIRA|MANG\b"
                   r"|MANG\.|MANGOTE)"),
    ("conexoes", r"^(TUBO|BUCHA REDUCAO|CAP\b|COTOVELO|COTOV|COTOVEELO|COTOVEOL"
                 r"|CURVA|JOELHO|FLANGE|FLG|LUVA REDUCAO|LUVA\b|NIPLE|NIPPLE"
                 r"|TE\b|TE REDUCAO|T REDUCAO|T\b|UNIAO|UNNIAO|TAMPAO)"),
    ("eletricos", r"^(CABO|CONDUTOR|CNDUTOR|TERMINAL ELET|TERM ELET|TERM\b"
                  r"|DISJUNTOR|DIJSUNTOR|DISJ|CONTATOR|CONTACTOR|CONT\b"
                  r"|FUSIVEL|FUS\b|LAMPADA|LAMP)"),
    ("outras", r"^(SENSOR|MANOMETRO|MANOM|ELETRODO|ELETR\b|DISCO|DSCO|BROCA"
               r"|BRROCA|OLEO|LEO\b|CORREIA|COORREIA|CORREIIA|COR\b)"),
]


def familia(nuc):
    for fam, pat in FAMILIA_REGRAS:
        if re.match(pat, nuc):
            return fam
    return "outras"


base["familia_prevista"] = base["_nuc"].map(familia)

GRUPO_DA_FAMILIA = {
    "fixadores": {"FIX01"}, "vedacao": {"VED01"}, "rolamentos": {"ROL01"},
    "valvulas": {"VAL01"}, "conexoes": {"TUB01"}, "eletricos": {"ELE01"},
    "mangueiras": {"MAN01"}, "sobressalentes": {"SOB01"},
    "outras": {"FIL01", "EPI01", "INS01", "SOL01", "FER01", "LUB01", "TRA01"},
}

# --------------------------------------------------------------- armadilhas ---
RE_ARMADILHAS = {
    # vírgula decimal dentro de valor rotulado: SECAO:1,5MM2, DIAMETRO:16,25MM
    "virgula_decimal": r"\d,\d+\s*(MM2|MM|POL|BAR|KV|V\b|A\b|KA)",
    # polegada escrita com aspas: 2"
    "polegada_aspas": r"\d\s*\"",
    # polegada escrita com IN: 1 IN, 3/4 IN
    "polegada_in": r"\d\s*IN\b",
    # fração mista: 1 1/4", 1-3/4"
    "polegada_mista": r"\b\d[\s-]\d\s*/\s*\d",
    # rosca métrica fina: M12X1,5 / M10X1,25X70
    "rosca_fina": r"\bM-?\d+\s*X\s*\d+[,.]\d",
    # bitola + comprimento colados: M12X50 / M16X1M (barra de 1 metro)
    "rosca_bitola_comp": r"\bM-?\d+\s*X\s*\d+(?![,.]\d)",
    # PN 16 (pressão nominal) contra PN 123456 (part number)
    "pn_ambiguo": r"\bP[/.]?N[:.\s]*\d",
    # CL 150# e 150# (classe de pressão)
    "classe_pressao_hash": r"\d\s*#",
    # unidade que não converte sem perda / exige conversão
    "unidade_nao_bar": r"KGF\s*/?\s*CM|\bPSI\b|\bMPA\b|\bKPA\b|\bLBF",
    # abreviação ambígua
    "abrev_ambigua": (r"\bVALV\.?\s*RET|^RET[\s.,]|\bSENSOR\s+IND\b"
                      r"|\bMANG\.?\s+IND\b|S\s*/\s*AC"),
    # ordem de grandezas sem rótulo: RETENTOR 90MM 112MM 8MM
    "ordem_sem_rotulo": (r"\b\d+(?:,\d+)?\s*MM\b[^0-9:]{0,8}\d+(?:,\d+)?\s*MM\b"
                         r"[^0-9:]{0,8}\d+(?:,\d+)?\s*MM\b"),
    # valor que o texto não decide: INOX sem 304/316, ZINCADO sem cor
    "valor_indefinivel": (r"\b(INOX|SS)\b(?!\s*[-]?\s*(304|316))"
                          r"|\bZINC(?:ADO)?\b(?!\s*(BRANCO|AMARELO))"
                          r"|\bNITRILICA\b|\bBUNA|\bBORRACHA\b(?!\s*(SINTETICA|COM))"),
}


def armadilhas(r):
    achadas = [k for k, p in RE_ARMADILHAS.items()
               if re.search(p, r["_txt"]) or re.search(p, r["_nuc"])]
    # descricao curta truncada em 40 caracteres que cortou o ultimo valor
    curta = r["_curta"].rstrip()
    if len(r["DESCRICAO_CURTA"]) == 40 and curta:
        ult = curta.split()[-1]
        if re.search(r"\b" + re.escape(ult) + r"[A-Z0-9]", r["_longa"]):
            achadas.append("curta_truncada")
    # grupo de mercadoria incompativel com a familia do texto
    if r["GRUPO_MERCADORIA"] not in GRUPO_DA_FAMILIA[r["familia_prevista"]]:
        achadas.append("grupo_errado")
    return "|".join(sorted(achadas))


base["armadilhas"] = base.apply(armadilhas, axis=1)

# ------------------------------------------------------------- classes irmas ---
IRMAS = {
    "valv_esfera": r"^VALV(ULA)?\.?\s*(ESF\b|ESFERA)",
    "valv_gaveta": r"^VALV(ULA)?\.?\s*(GAV\b|GAVETA)",
    "valv_globo": r"^VALV(ULA)?\.?\s*GLOBO",
    "valv_retencao": r"^VALV(ULA)?\.?\s*(RET\b|RETENCAO)",
    "valv_borboleta": r"^VALV(ULA)?\.?\s*(BORB\b|BORBOLETA)",
    "rol_rigido": r"^ROL(AMENTO)?\.?\s*(ESF|RIGIDO)",
    "rol_autocomp": r"^ROL(AMENTO)?\.?\s*AUTOCOMP",
    "rol_conico": r"^ROL(AMENTO)?\.?\s*(ROLOS\s*CONICOS|CONICO)",
    # o interno vem antes para nao ser engolido pelo sextavado comum
    "paraf_sext_int": (r"^PARAF\w*[\s.,-]*(CAB\w*[\s.,-]*)?"
                       r"(SEXT\w*[\s.,-]*(INTERNO|ALLEN)|ALLEN|CILINDRICA"
                       r"|ESCAREADA|ABAULADA)"),
    "paraf_sext": r"^PARAF\w*[\s.,-]*(SEXT|HEXAG)",
    "arruela_lisa": r"^(ARRUELA|ARR)\.?\s*(LISA|PLANA)",
    "arruela_pressao": r"^(ARRUELA|ARR)\.?\s*PRESSAO",
    "mang_montada": r"^MANG\w*\.?\s*(HID\w*)?\s*(MONT|C/\s*TERMINA)",
    "mang_avulsa": r"^MANG\w*\.?\s*(HIDR?A?U?L?I?C?A?)\s*(?!MONT|C/\s*TERMINA)",
    "junta_espiralada": r"^(JUNTA|JTA)\s*ESPIRAL",
    "junta_plana": r"^(JUNTA|JTA)\s*(PLANA|VEDACAO)",
}

# ------------------------------------------------------------------- selecao ---
QUOTAS = {"fixadores": 36, "vedacao": 28, "rolamentos": 20, "valvulas": 28,
          "conexoes": 28, "eletricos": 28, "mangueiras": 28,
          "sobressalentes": 24, "outras": 20}
assert sum(QUOTAS.values()) == N_ITENS

usados = {}          # codigo -> estrato
por_familia = Counter()


def amostra(df, n):
    df = df[~df["CODIGO_MATERIAL"].isin(usados)]
    if len(df) == 0:
        return df
    return df.sample(min(n, len(df)), random_state=rng)


def pega(df, estrato, n, respeita_cota=True):
    """Adiciona ate n itens de df no estrato, diversificando familia."""
    df = df[~df["CODIGO_MATERIAL"].isin(usados)]
    if respeita_cota:
        df = df[df["familia_prevista"].map(
            lambda f: por_familia[f] < QUOTAS[f])]
    if len(df) == 0:
        return 0
    # ordena aleatoriamente, depois prioriza familias menos representadas
    df = df.sample(len(df), random_state=rng)
    df = df.assign(_pri=df["familia_prevista"].map(lambda f: por_familia[f]))
    df = df.sort_values("_pri", kind="stable")
    tomados = 0
    for _, r in df.iterrows():
        if tomados >= n:
            break
        f = r["familia_prevista"]
        if respeita_cota and por_familia[f] >= QUOTAS[f]:
            continue
        usados[r["CODIGO_MATERIAL"]] = estrato
        por_familia[f] += 1
        tomados += 1
    return tomados


# 1) fora do PDM: TAMPAO nao esta em SUBSTANTIVOS_CONEXOES; CAIXA MANCAL e quase-acerto
pega(base[base["_nuc"].str.match(r"^TAMPAO")], "fora_pdm", 8)
pega(base[base["_nuc"].str.match(r"^CAIXA MANCAL")], "fora_pdm", 2)

# 2) classes irmas
for irma, pat in IRMAS.items():
    pega(base[base["_nuc"].str.match(pat)], f"irma:{irma}", N_POR_IRMA)

# 3) armadilhas
tem = {k: base["armadilhas"].str.contains(rf"(?:^|\|){re.escape(k)}(?:\||$)",
                                          regex=True)
       for k in list(RE_ARMADILHAS) + ["curta_truncada", "grupo_errado"]}
for k in tem:
    if k == "grupo_errado":
        continue
    pega(base[tem[k]], f"armadilha:{k}", N_POR_ARMADILHA)

# 4) grupo de mercadoria errado na coluna
pega(base[tem["grupo_errado"]], "grupo_errado", 10)

# 5) completa as cotas por familia, metade estruturado / metade telegrafico
for fam, cota in QUOTAS.items():
    falta = cota - por_familia[fam]
    if falta <= 0:
        continue
    pool = base[base["familia_prevista"] == fam]
    meio = falta // 2
    pega(pool[pool["estilo"] == "estruturado"], "estilo:estruturado", meio)
    pega(pool[pool["estilo"] == "telegrafico"], "estilo:telegrafico",
         cota - por_familia[fam])
    pega(pool, "estilo:completa", cota - por_familia[fam])

if len(usados) != N_ITENS:  # ultimo recurso: completa ignorando cota
    pega(base, "estilo:completa", N_ITENS - len(usados), respeita_cota=False)

sel = base[base["CODIGO_MATERIAL"].isin(usados)].copy()
sel["estrato"] = sel["CODIGO_MATERIAL"].map(usados)
sel = sel.sample(len(sel), random_state=rng)          # ordem de anotacao de A
sel.insert(0, "ordem_A", range(1, len(sel) + 1))
sel["ordem_B"] = rng.permutation(len(sel)) + 1        # ordem de anotacao de B

cols = ["ordem_A", "ordem_B", "estrato", "familia_prevista", "estilo",
        "armadilhas"] + COLS_BASE
sel[cols].to_csv(RAIZ / "candidatos_caracteristicas.csv", index=False)

print(f"itens selecionados: {len(sel)}")
print("\n--- por familia_prevista x estilo ---")
print(pd.crosstab(sel["familia_prevista"], sel["estilo"]).to_string())
print("\n--- por estrato ---")
print(sel["estrato"].value_counts().sort_index().to_string())
print("\n--- cobertura de armadilhas (itens selecionados) ---")
cnt = Counter(a for s in sel["armadilhas"] for a in s.split("|") if a)
for k in sorted(set(list(RE_ARMADILHAS) + ["curta_truncada", "grupo_errado"])):
    flag = "OK " if cnt[k] >= 8 else "BAIXO"
    print(f"  {flag} {k:22} {cnt[k]:>3}")
if any(cnt[k] < 8 for k in list(RE_ARMADILHAS) + ["curta_truncada", "grupo_errado"]):
    print("ATENCAO: armadilha com menos de 8 itens", file=sys.stderr)

# =========================================================== parte C: pares ===
SAN = REPO / "artefatos/saneado_base.csv"
if not SAN.exists():
    print("\nartefatos/saneado_base.csv ausente: pares nao gerados", file=sys.stderr)
    sys.exit(0)

san = pd.read_csv(SAN, dtype=str).fillna("")
texto = dict(zip(base["CODIGO_MATERIAL"], base["DESCRICAO_LONGA"]))
curta = dict(zip(base["CODIGO_MATERIAL"], base["DESCRICAO_CURTA"]))
pares = []
vistos = set()


def junta(a, b, fonte):
    k = tuple(sorted((a, b)))
    if a == b or k in vistos or a not in texto or b not in texto:
        return False
    vistos.add(k)
    pares.append({"codigo_1": k[0], "codigo_2": k[1], "fonte_par": fonte})
    return True


# C1) 70 pares com a MESMA chave de identidade
grupos = [g for _, g in san[san["CHAVE_IDENTIDADE"] != ""]
          .groupby("CHAVE_IDENTIDADE")["CODIGO_MATERIAL"] if len(g) >= 2]
rng.shuffle(grupos)
for g in grupos:
    if sum(p["fonte_par"] == "mesma_chave" for p in pares) >= 70:
        break
    cods = list(g)
    i, j = rng.choice(len(cods), 2, replace=False)
    junta(cods[i], cods[j], "mesma_chave")


def atrs(desc):
    """ATRIBUTO: VALOR; ... -> dict. Ignora o substantivo (1o segmento)."""
    d = {}
    for seg in desc.split(";")[1:]:
        if ":" in seg:
            k, v = seg.split(":", 1)
            d[k.strip()] = v.strip()
    return d


# C2) 50 pares da mesma classe que diferem em EXATAMENTE um atributo
san["_atrs"] = san["DESCRICAO_PDM"].map(atrs)
alvo = 50
for pdm, g in san[san["ID_PDM"] != ""].groupby("ID_PDM"):
    if sum(p["fonte_par"] == "um_atributo" for p in pares) >= alvo:
        break
    g = g.sample(min(len(g), 400), random_state=rng)
    recs = list(zip(g["CODIGO_MATERIAL"], g["_atrs"]))
    for i in range(len(recs)):
        if sum(p["fonte_par"] == "um_atributo" for p in pares) >= alvo:
            break
        ca, da = recs[i]
        for cb, db in recs[i + 1:]:
            if set(da) != set(db):
                continue
            dif = [k for k in da if da[k] != db[k]]
            if len(dif) == 1 and da[dif[0]] and db[dif[0]]:
                if junta(ca, cb, "um_atributo"):
                    break

# C3) 30 pares de descricao parecida por palavras, mas chaves diferentes
PARA = re.compile(r"[^A-Z0-9]+")


def toks(s):
    return {t for t in PARA.split(sem_acento(s).upper()) if len(t) > 1}


bloco = defaultdict(list)
for _, r in san.iterrows():
    cod, ch = r["CODIGO_MATERIAL"], r["CHAVE_IDENTIDADE"]
    if cod not in texto:
        continue
    t = toks(texto[cod])
    chave_bloco = " ".join(sorted(t)[:1]) + "|" + (r["ID_PDM"] or "?")
    bloco[chave_bloco].append((cod, ch, t))

chaves_bloco = list(bloco)
rng.shuffle(chaves_bloco)
for cb_ in chaves_bloco:
    if sum(p["fonte_par"] == "texto_parecido" for p in pares) >= 30:
        break
    itens = bloco[cb_][:120]
    for i in range(len(itens)):
        ca, cha, ta = itens[i]
        for cbb, chb, tb in itens[i + 1:]:
            if cha == chb or not cha or not chb:
                continue
            jac = len(ta & tb) / max(1, len(ta | tb))
            if jac >= 0.7:
                if junta(ca, cbb, "texto_parecido"):
                    break
        if sum(p["fonte_par"] == "texto_parecido" for p in pares) >= 30:
            break

dfp = pd.DataFrame(pares)
dfp = dfp.sample(len(dfp), random_state=rng).reset_index(drop=True)
dfp.insert(0, "par_id", [f"P{i:03d}" for i in range(1, len(dfp) + 1)])

# Os pares NAO sao reproduziveis como os itens: eles sao sorteados a partir de
# artefatos/saneado_base.csv (chave de identidade, atributo que difere,
# similaridade), e esse arquivo muda a cada execucao do pipeline. Reexecutando
# com outra versao dos artefatos, P001..P150 continuam existindo mas apontam
# para OUTROS codigos - e as anotacoes, que sao indexadas por par_id, passariam
# a descrever o par errado em silencio. Medido: uma reexecucao trocou os 150
# pares depois de o pipeline ser rodado de novo.
#
# Por isso sobrescrever exige --refazer-pares, e refazer obriga a reanotar a
# parte C. Os itens (parte A e B) nao tem esse problema: saem so da base crua.
arq_pares = RAIZ / "pares_juncao_candidatos.csv"
if arq_pares.exists() and not REFAZER_PARES:
    print(f"\n{arq_pares.name} ja existe: mantido como esta "
          "(use --refazer-pares para resortear, e reanote a parte C depois).",
          file=sys.stderr)
    print(f"pares de juncao: {len(pd.read_csv(arq_pares))} (preservados)")
    sys.exit(0)
dfp.to_csv(arq_pares, index=False)

# versao CEGA usada na anotacao: so o texto cru, sem chave/cluster/fonte
cego = dfp[["par_id", "codigo_1", "codigo_2"]].copy()
for n in ("1", "2"):
    cego[f"curta_{n}"] = cego[f"codigo_{n}"].map(curta)
    cego[f"longa_{n}"] = cego[f"codigo_{n}"].map(texto)
cego = cego.sample(len(cego), random_state=rng)
cego.to_csv(RAIZ / "pares_juncao_cego.csv", index=False)

print(f"\npares de juncao: {len(dfp)}")
print(dfp["fonte_par"].value_counts().to_string())
