# -*- coding: utf-8 -*-
"""Seleciona os candidatos do conjunto-ouro de CLASSE e CARACTERISTICAS dos
PEDIDOS DE CADASTRO (dados/02_pedidos_cadastro.xlsx). Reproduzivel: semente
fixa, regras explicitas, nenhuma escolha manual.

Por que um gabarito separado para os pedidos
--------------------------------------------
O gabarito de caracteristicas (10/11) e o de cadastro V2 (20/21) medem a base
que existe: 23.554 descricoes em MAIUSCULAS, de formato mais ou menos
constante. O pedido e outra coisa. Ele chega por tres canais (PORTAL 279,
EMAIL 156, PLANILHA 85), em quatro formatos de texto, e em 136 dos 520 a
solicitacao e so "Segue ficha tecnica em anexo" - a informacao esta no
CONTEUDO_ANEXO, noutro formato. Medir o pipeline na base nao diz como ele se
comporta na entrada, que e onde o cadastro e de fato decidido.

Independencia do pipeline (mais estrita que a do 10 e a do 20)
--------------------------------------------------------------
Este script le SO dados/02_pedidos_cadastro.xlsx (texto cru) e
dados/03_padrao_cadastro_PDM.xlsx (o padrao). Nada de artefatos/ - nem para
estratificar. O 20_candidatos_cadastro.py tinha permissao de ler
saneado_base.csv para montar estratos; aqui nao foi preciso, porque todo
estrato sai do texto cru e do PDM. Portanto nenhuma coluna de saida do
pipeline (ESTADO, ID_PDM, DESCRICAO_PDM, NCM_PDM...) influencia nem a escolha
dos candidatos nem a anotacao.

A coluna familia_prevista e um PALPITE de selecao (busca do substantivo do PDM
no texto), usada so para estratificar. A classe verdadeira de cada pedido e o
rotulo _CLASSE da anotacao, feito a partir do texto contra o PDM; ela pode
divergir da familia_prevista.

Estratos de selecao (ordem de aplicacao; um pedido fica no primeiro que o pegou)
-------------------------------------------------------------------------------
  fora_pdm         10  nenhum substantivo do PDM aparece no texto (software,
                       mobiliario, servico): o pipeline deve dizer FORA_DO_PDM,
                       e forcar uma classe e erro
  anexo:catalogo   12  TIPO_ANEXO = CATALOGO FORNECEDOR. Linha de catalogo em
                       INGLES, separada por barra: "Generic | Ball valve |
                       1POL, 150#, A216 WCB, RF flanged, reduced bore, lever".
                       Nao existe nada parecido na base
  anexo:ficha      14  TIPO_ANEXO = FICHA TECNICA. "Campo: valor" por linha, em
                       minusculas e com acento ("Diametro eixo: 60 mm",
                       "Tipo: ba", "Material: aco inox 316")
  armadilha:<x>        completa cada armadilha conhecida ate MIN_ARMADILHA
                       itens, contando os que os estratos acima ja trouxeram
  familia:<x>          cotas por familia de classe, com PDM110 (sobressalente)
                       e PDM100 (filtro) a parte, porque sao classes de
                       REFERENCIA DO FABRICANTE e nao de especificacao
  estilo:<e>           preenchimento final, equilibrando email_longo e
                       telegrafico

Saida
-----
  candidatos_pedidos.csv  120 pedidos, linha crua + estrato/familia/estilo/
                          armadilhas + ordem_A e ordem_B (as duas passadas de
                          anotacao veem ordens diferentes, sementes 11 e 97)

Uso: backend/.venv/bin/python avaliacao/22_candidatos_pedidos.py
     (ou: uv run --no-project --with pandas --with openpyxl python ...)
"""
import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
REPO = RAIZ.parent
SEED = 20261108
SEED_ORDEM_A = 11
SEED_ORDEM_B = 97
N_ITENS = 120
MIN_ARMADILHA = 5
COTA = {"fora_pdm": 10, "anexo:catalogo": 12, "anexo:ficha": 14}

rng = np.random.RandomState(SEED)


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s))
                   if not unicodedata.combining(c))


def norm(s):
    return sem_acento(s).upper()


# ------------------------------------------------------------------- pedidos ---
ARQ = REPO / "dados/02_pedidos_cadastro.xlsx"
if not ARQ.exists():                      # o repositorio tambem guarda na raiz
    ARQ = REPO / "02_pedidos_cadastro.xlsx"
ped = pd.read_excel(ARQ, sheet_name="PEDIDOS", dtype=str).fillna("")
COLS_CRUAS = list(ped.columns)
if "ID_PEDIDO" not in COLS_CRUAS:
    sys.exit("ERRO: aba PEDIDOS sem ID_PEDIDO")

# O texto que o anotador le e o que o solicitante mandou: solicitacao + anexo.
# A juncao e feita aqui, sobre as colunas cruas, e nao importada de
# src/saneamento/dados.py - o protocolo proibe rodar o pipeline na anotacao.
ped["_sol"] = ped["TEXTO_SOLICITACAO"].str.strip()
ped["_anx"] = ped["CONTEUDO_ANEXO"].str.strip()
ped["_txt"] = (ped["_sol"] + "\n" + ped["_anx"]).str.strip()
ped["_n"] = ped["_txt"].map(norm)

# --------------------------------------------------------------- substantivos ---
pdm_classes = pd.read_excel(REPO / "dados/03_padrao_cadastro_PDM.xlsx",
                            sheet_name="CLASSES", dtype=str).fillna("")
pdm_sobr = pd.read_excel(REPO / "dados/03_padrao_cadastro_PDM.xlsx",
                         sheet_name="SUBSTANTIVOS_SOBRESSALENTES", dtype=str).fillna("")
pdm_conex = pd.read_excel(REPO / "dados/03_padrao_cadastro_PDM.xlsx",
                          sheet_name="SUBSTANTIVOS_CONEXOES", dtype=str).fillna("")

# familia -> substantivos que a denunciam no texto. Sai do PDM, nao de palpite:
# os substantivos das 44 classes, mais as duas abas de substantivos.
FAMILIA_DE_CLASSE = {
    "PDM001": "fixadores", "PDM002": "fixadores", "PDM003": "fixadores",
    "PDM004": "fixadores", "PDM005": "fixadores", "PDM006": "fixadores",
    "PDM010": "mangueiras", "PDM011": "mangueiras", "PDM012": "mangueiras",
    "PDM013": "mangueiras", "PDM014": "mangueiras",
    "PDM020": "rolamentos", "PDM021": "rolamentos", "PDM022": "rolamentos",
    "PDM023": "rolamentos",
    "PDM030": "transmissao",
    "PDM031": "vedacao", "PDM032": "vedacao", "PDM033": "vedacao", "PDM034": "vedacao",
    "PDM040": "valvulas", "PDM041": "valvulas", "PDM042": "valvulas",
    "PDM043": "valvulas", "PDM044": "valvulas",
    "PDM050": "conexoes_tubo", "PDM051": "conexoes_tubo",
    "PDM060": "eletricos", "PDM061": "eletricos", "PDM062": "eletricos",
    "PDM063": "eletricos", "PDM064": "eletricos", "PDM065": "eletricos",
    "PDM066": "instrumentacao", "PDM067": "instrumentacao",
    "PDM070": "epi", "PDM071": "epi", "PDM072": "epi",
    "PDM080": "solda_ferramenta", "PDM081": "solda_ferramenta", "PDM082": "solda_ferramenta",
    "PDM090": "lubrificante",
    "PDM100": "filtros",
    "PDM110": "sobressalentes",
}

_subst = defaultdict(set)   # familia -> {substantivo normalizado}
for _, r in pdm_classes.iterrows():
    fam = FAMILIA_DE_CLASSE.get(r["ID_PDM"])
    s = norm(r["SUBSTANTIVO"])
    if fam and s and not s.startswith("("):
        _subst[fam].add(s)
for _, r in pdm_conex.iterrows():
    s = norm(r["SUBSTANTIVO_E_QUALIFICADOR"])
    if s:
        _subst["conexoes_tubo"].add(s.split()[0])
for _, r in pdm_sobr.iterrows():
    s = norm(r["SUBSTANTIVO_E_QUALIFICADOR"])
    if s:
        _subst["sobressalentes"].add(s.split()[0])

# Ordem FIXA. Com set, a iteracao varia conforme o hash de string do processo
# (PYTHONHASHSEED), e familia_prevista passava a desempatar diferente a cada
# execucao: o candidatos_pedidos.csv saia com md5 diferente do mesmo codigo e
# da mesma semente. Listas ordenadas e desempate explicito resolvem.
SUBST = {fam: sorted(_subst[fam]) for fam in sorted(_subst)}

# termos em ingles do catalogo do fornecedor, mapeados para a familia. Sem isso
# toda linha de catalogo cairia em fora_pdm, que seria um estrato mentiroso.
INGLES = {
    "fixadores": ["HEX BOLT", "SOCKET", "SCREW", "NUT", "WASHER", "STUD"],
    "mangueiras": ["HOSE"],
    "rolamentos": ["BEARING", "PILLOW BLOCK"],
    "transmissao": ["V-BELT", "BELT"],
    "vedacao": ["O-RING", "OIL SEAL", "GASKET", "SEAL"],
    "valvulas": ["BALL VALVE", "GATE VALVE", "GLOBE VALVE", "CHECK VALVE",
                 "BUTTERFLY VALVE", "VALVE"],
    "conexoes_tubo": ["ELBOW", "TEE", "COUPLING", "FLANGE", "NIPPLE", "PIPE", "REDUCER"],
    "eletricos": ["CABLE", "TERMINAL", "BREAKER", "CONTACTOR", "FUSE", "LAMP", "LED"],
    "instrumentacao": ["PROXIMITY", "SENSOR", "GAUGE", "MANOMETER"],
    "epi": ["GLOVE", "BOOT", "SHOE", "GOGGLE", "SPECTACLE"],
    "solda_ferramenta": ["ELECTRODE", "GRINDING", "FLAP DISC", "DISC", "DRILL"],
    "lubrificante": ["OIL", "GREASE", "LUBRICANT"],
    "filtros": ["FILTER"],
}


def familia_prevista(n):
    """Familia cujo substantivo (PT ou EN) casa com o texto, mais longo primeiro.

    O desempate e explicito - (-tamanho, familia) - para o resultado nao
    depender da ordem de iteracao de nenhuma colecao.
    """
    achadas = []
    for fam in sorted(SUBST):
        for t in SUBST[fam]:
            if re.search(r"\b" + re.escape(t) + r"\b", n):
                achadas.append((-len(t), fam))
                break
    for fam in sorted(INGLES):
        for t in INGLES[fam]:
            if re.search(r"\b" + re.escape(t) + r"\b", n):
                achadas.append((-len(t), fam))
                break
    if not achadas:
        return "nenhuma"
    # o substantivo mais longo ganha: "VALVULA ESFERA" antes de "VALVULA"
    return sorted(achadas)[0][1]


ped["familia_prevista"] = ped["_n"].map(familia_prevista)


# ------------------------------------------------------------------- estilo ---
RE_SAUDACAO = r"\b(BOM DIA|BOA TARDE|BOA NOITE|PREZADOS?|OLA|ATT\b|ATENCIOSAMENTE|OBRIGADO|ABRACO)\b"


def estilo(r):
    if r["TIPO_ANEXO"] == "CATALOGO FORNECEDOR":
        return "catalogo"
    if r["TIPO_ANEXO"] == "FICHA TECNICA":
        return "ficha"
    n = r["_n"]
    if re.search(RE_SAUDACAO, n) or "\n-" in r["_txt"] or len(r["_sol"]) > 160:
        return "email_longo"
    return "telegrafico"


ped["estilo"] = ped.apply(estilo, axis=1)


# --------------------------------------------------------------- armadilhas ---
# As dez primeiras sao as mesmas do 10_candidatos_caracteristicas.py, para os
# dois gabaritos serem comparaveis. As seis ultimas so existem no pedido.
RE_ARMADILHAS = {
    # --- herdadas do gabarito da base ---
    "virgula_decimal": r"\d,\d+\s*(MM2|MM|POL|BAR|KV|V\b|A\b|KA)",
    "polegada_aspas": r"\d\s*\"",
    "polegada_in": r"\d\s*IN\b",
    "polegada_mista": r"\b\d[\s-]\d\s*/\s*\d",
    "rosca_fina": r"\bM-?\d+\s*X\s*\d+[,.]\d",
    "rosca_bitola_comp": r"\bM-?\d+\s*X\s*\d+(?![,.]\d)",
    "pn_ambiguo": r"\bP[/.]?N[:.\s]*\d",
    "classe_pressao_hash": r"\d\s*#",
    "unidade_nao_bar": r"KGF\s*/?\s*CM|\bPSI\b|\bMPA\b|\bKPA\b|\bLBF",
    "abrev_ambigua": (r"\bVALV\.?\s*RET|^RET[\s.,]|\bSENSOR\s+IND\b"
                      r"|\bMANG\.?\s+IND\b|S\s*/\s*AC"),
    "ordem_sem_rotulo": (r"\b\d+(?:,\d+)?\s*MM\b[^0-9:]{0,8}\d+(?:,\d+)?\s*MM\b"
                         r"[^0-9:]{0,8}\d+(?:,\d+)?\s*MM\b"),
    "valor_indefinivel": (r"\b(INOX|SS)\b(?!\s*[-]?\s*(304|316))"
                          r"|\bZINC(?:ADO)?\b(?!\s*(BRANCO|AMARELO))"
                          r"|\bNITRILICA\b|\bBUNA|\bBORRACHA\b(?!\s*(SINTETICA|COM))"),
    # --- so no pedido ---
    # contexto de aplicacao que NAO e atributo: "para a correia TC-04", "pra
    # bomba da barragem". Preencher APLICACAO a partir disso, numa classe de
    # especificacao tecnica, e invencao
    "contexto_aplicacao": (r"\bP(?:ARA|RA)\s+(?:A|O|AS|OS)?\s*(?:PARADA|PROXIMA|REPOSICAO"
                           r"|CORREIA|BOMBA|PAINEL|BRITADOR|MOINHO|PENEIRA|TRANSPORTADOR"
                           r"|PREVENTIVA|MANUTENCAO|ESTOQUE)"),
    # equivalencia entre fabricantes: regra 13 diz que nao e o mesmo item
    "equivalencia": r"\bOU\s+(SIMILAR|EQUIVALENTE|COMPATIVEL)|\bEQUIVALENTE\s+A\b",
    # ruido de cortesia e assinatura no corpo do e-mail
    "ruido_cortesia": RE_SAUDACAO,
    # catalogo em ingles
    "ingles": r"\b(FLANGED|BORE|SHORE|THREADED|WELDED|LEVER|GEAR|STAINLESS|CARBON STEEL)\b",
    # ficha tecnica em minusculas: o texto cru tem letra minuscula em valor
    # que o PDM escreve em maiuscula
    "minuscula": None,          # tratada fora do regex
    # mais de um item no mesmo pedido
    "multi_item": r"\b(\d+\s*\)|ITEM\s*\d|E\s+TAMBEM\b|ALEM\s+DISSO\b)",
}


def armadilhas(r):
    n, bruto = r["_n"], r["_txt"]
    achadas = [k for k, p in RE_ARMADILHAS.items()
               if p is not None and re.search(p, n)]
    # minuscula: metade ou mais das letras do texto em caixa baixa
    letras = [c for c in bruto if c.isalpha()]
    if letras and sum(1 for c in letras if c.islower()) / len(letras) >= 0.5:
        achadas.append("minuscula")
    return "|".join(sorted(achadas))


ped["armadilhas"] = ped.apply(armadilhas, axis=1)


# ------------------------------------------------------------------ sorteio ---
escolhidos: dict[str, str] = {}      # ID_PEDIDO -> estrato


def sorteia(mascara, quantos, estrato):
    """Sorteia `quantos` pedidos ainda nao escolhidos que casam com `mascara`."""
    pool = ped[mascara & ~ped["ID_PEDIDO"].isin(escolhidos)]
    if pool.empty or quantos <= 0:
        return 0
    n = min(quantos, len(pool))
    for i in rng.choice(pool.index.values, size=n, replace=False):
        escolhidos[ped.at[i, "ID_PEDIDO"]] = estrato
    return n


# 1. fora do PDM: nenhum substantivo do PDM nem do catalogo aparece
sorteia(ped["familia_prevista"] == "nenhuma", COTA["fora_pdm"], "fora_pdm")
# 2. e 3. os dois formatos de anexo
sorteia(ped["TIPO_ANEXO"] == "CATALOGO FORNECEDOR", COTA["anexo:catalogo"], "anexo:catalogo")
sorteia(ped["TIPO_ANEXO"] == "FICHA TECNICA", COTA["anexo:ficha"], "anexo:ficha")

# 4. completa cada armadilha ate MIN_ARMADILHA, contando o que ja entrou
for arm in RE_ARMADILHAS:
    tem = ped["armadilhas"].str.contains(rf"(?:^|\|){re.escape(arm)}(?:\||$)", regex=True)
    ja = sum(1 for p in escolhidos if tem[ped["ID_PEDIDO"] == p].any())
    sorteia(tem, MIN_ARMADILHA - ja, f"armadilha:{arm}")

# 5. cotas por familia, proporcionais ao que existe nos 520, com piso de 2
restam = N_ITENS - len(escolhidos)
if restam > 0:
    presentes = [f for f in ped["familia_prevista"].unique() if f != "nenhuma"]
    peso = {f: (ped["familia_prevista"] == f).sum() for f in presentes}
    total = sum(peso.values())
    cotas = {f: max(2, round(restam * peso[f] / total)) for f in presentes}
    for fam in sorted(cotas, key=lambda f: -peso[f]):
        if len(escolhidos) >= N_ITENS:
            break
        falta = min(cotas[fam], N_ITENS - len(escolhidos))
        sorteia(ped["familia_prevista"] == fam, falta, f"familia:{fam}")

# 6. preenchimento final, alternando estilo para nao encher de um so
for est in ["telegrafico", "email_longo", "ficha", "catalogo"]:
    if len(escolhidos) >= N_ITENS:
        break
    sorteia(ped["estilo"] == est, N_ITENS - len(escolhidos), f"estilo:{est}")

sel = ped[ped["ID_PEDIDO"].isin(escolhidos)].copy()
sel["estrato"] = sel["ID_PEDIDO"].map(escolhidos)

# ordem das duas passadas de anotacao: sementes diferentes, para A e B nao
# verem os itens na mesma sequencia (o efeito de ordem e real)
sel = sel.sort_values("ID_PEDIDO").reset_index(drop=True)
sel["ordem_A"] = np.random.RandomState(SEED_ORDEM_A).permutation(len(sel)) + 1
sel["ordem_B"] = np.random.RandomState(SEED_ORDEM_B).permutation(len(sel)) + 1

COLS = (["ordem_A", "ordem_B", "estrato", "familia_prevista", "estilo", "armadilhas"]
        + COLS_CRUAS)
saida = RAIZ / "candidatos_pedidos.csv"
sel[COLS].sort_values("ordem_A").to_csv(saida, index=False, quoting=csv.QUOTE_MINIMAL)

# --------------------------------------------------------------- conferencia ---
print(f"gravado {saida.name}: {len(sel)} pedidos de {len(ped)}\n")
print("por estrato:")
for k, v in sorted(Counter(sel["estrato"]).items(), key=lambda kv: (-kv[1], kv[0])):
    print(f"  {k:28s} {v:3d}")
print("\npor familia prevista:")
for k, v in sorted(Counter(sel["familia_prevista"]).items(), key=lambda kv: -kv[1]):
    print(f"  {k:28s} {v:3d}")
print("\npor estilo:")
for k, v in sorted(Counter(sel["estilo"]).items(), key=lambda kv: -kv[1]):
    print(f"  {k:28s} {v:3d}")
print("\npor canal / urgencia:")
for col in ["CANAL", "URGENCIA"]:
    print(f"  {col}: " + ", ".join(f"{k}={v}" for k, v in Counter(sel[col]).items()))
print("\ncobertura das armadilhas (itens selecionados que a contem):")
faltou, universais = [], []
for arm in RE_ARMADILHAS:
    n = sel["armadilhas"].str.contains(rf"(?:^|\|){re.escape(arm)}(?:\||$)", regex=True).sum()
    nos_520 = ped["armadilhas"].str.contains(rf"(?:^|\|){re.escape(arm)}(?:\||$)", regex=True).sum()
    marca = ""
    if n == len(sel):
        marca = "  <- em 100%: propriedade do canal, nao estrato"
        universais.append(arm)
    elif n < MIN_ARMADILHA:
        marca = "  <- abaixo do minimo"
        faltou.append((arm, n, nos_520))
    print(f"  {arm:22s} {n:3d}  (nos 520: {nos_520:3d}){marca}")
if universais:
    print(f"\nNOTA: {', '.join(universais)} aparece em todos os 120 candidatos - e nos "
          f"{(ped['armadilhas'].str.contains('minuscula')).sum()} dos 520 pedidos. Nao "
          "discrimina estrato: e uma diferenca de canal entre pedido e base, onde a\n"
          "      descricao e toda em MAIUSCULAS. Fica registrada como propriedade, e o\n"
          "      avaliador mede o efeito dela comparando com o gabarito da base.")
if faltou:
    print(f"\nAVISO: {len(faltou)} armadilha(s) abaixo de {MIN_ARMADILHA} item(ns), porque "
          "nos 520 pedidos nao ha mais casos:")
    for a, n, t in faltou:
        print(f"       {a:22s} {n} selecionado(s) de {t} existente(s) nos 520")
