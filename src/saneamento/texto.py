"""Normalizacao de texto e parsers de grandeza do PDM.

Camada mais baixa do pipeline: nao conhece classe nem atributo, so transforma
texto e numeros para a forma exigida pelo padrao. Tudo aqui e funcao pura e
deterministica, para poder ser testado e repetido.

Regras do PDM implementadas:
  3. texto em maiusculas, sem acento e sem cedilha
  5. polegada: fracao + POL, inteiro separado por ponto (1/2POL, 1.1/4POL)
     milimetro: numero + MM, decimal com virgula (16,25MM)
  6. pressao sempre em BAR; mangueira montada em MM; secao de cabo em MM2
"""

from __future__ import annotations

import re
import unicodedata
from fractions import Fraction

# ------------------------------------------------------------------ texto


def sem_acento(s: str) -> str:
    """Remove acento e cedilha preservando a letra base (regra 3)."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(c)
    )


_ESPACO = re.compile(r"\s+")
_RUIDO = re.compile(r"[^A-Z0-9/.,#\-+%]+")


# Ponto e virgula sao removidos APENAS fora de numero: 'ANEL EXPULSOR,' tem de
# virar 'ANEL EXPULSOR' para casar com o substantivo, mas '16,25MM', '1.1/4POL',
# 'ASME B16.11' e '3.650' precisam manter o separador.
_PONTUACAO_SOLTA = re.compile(r"(?<!\d)[.,]|[.,](?!\d)")


def normalizar_valor(s: str) -> str:
    """Caixa alta sem acento, preservando toda a pontuacao.

    Forma canonica de ARMAZENAMENTO dos valores permitidos do PDM: 'FKM (VITON)'
    tem de sair na descricao exatamente como o padrao escreve. O casamento usa
    normalizar(), que e mais agressivo - por isso Atributo guarda os dois.
    """
    if s is None:
        return ""
    return _ESPACO.sub(" ", sem_acento(s).upper()).strip()


# Aspas depois de numero sao polegada: 2" -> 2POL, 1/2" -> 1/2POL. O _RUIDO
# apaga as aspas, e com elas a unidade: 1.273 registros escrevem polegada assim,
# e o diametro deles chegava as camadas como um numero solto ('VALVULA RET 2
# 300#'). A alternativa \" que regras.RX['POL'] tinha nunca podia casar.
_POLEGADA_ASPAS = re.compile(r"(\d)\s*(?:\"|''|”|″)")


# Fracao mista no formato da regra 5 do PDM: '1 3/4POL' e '1-3/4POL' -> 1.3/4POL.
# Sem isso o gazetteer acha '3/4POL' DENTRO de '1 3/4POL' e a BITOLA 1/2" de um
# parafuso de comprimento 1.3/4" fica ambigua entre 1/2POL e 3/4POL.
# Parte inteira so de 1 a 12, e nunca depois de GRAUS/SCH: 'COTOV GRAUS 90 1/4POL'
# virava 90.1/4POL (o angulo colado na bitola) e o cotovelo perdia a classe.
_FRACAO_MISTA = re.compile(
    r"(?<![0-9/.#])(?<!GRAUS )(?<!SCH )(?<!SCHEDULE )"
    r"([1-9]|1[0-2])[\s\-](\d{1,2}/\d{1,2})\s?POL")
# 'POLX2' -> 'POL X 2': bitola x comprimento em polegada, separados
_POL_X = re.compile(r"POL\s?X\s?(?=\d)")
# Polegada escrita em ingles depois do numero: '3/4 IN', '1 IN CL 150#', '2 INCH'.
# 1.152 ocorrencias na base, todas polegada, e eram o termo nao reconhecido mais
# comum (DIAMETRO NOMINAL '1 IN', '2 IN', '3/4 IN'). So depois de DIGITO: o IN de
# disjuntor vem antes do numero ('3P IN 25A' e corrente nominal) e fica intocado.
_POLEGADA_IN = re.compile(r"(\d)\s?(?:INCHES|INCH|IN)(?![A-Z0-9])")


def _polegada(s: str) -> str:
    s = _POLEGADA_ASPAS.sub(r"\1POL ", s)
    s = _POLEGADA_IN.sub(r"\1POL", s)
    s = _POL_X.sub("POL X ", s)
    return _FRACAO_MISTA.sub(r"\1.\2POL", s)


def normalizar(s: str) -> str:
    """Forma canonica para comparacao: maiusculo, sem acento, espaco colapsado."""
    if s is None:
        return ""
    t = _RUIDO.sub(" ", _polegada(sem_acento(s).upper()))
    return _ESPACO.sub(" ", _PONTUACAO_SOLTA.sub(" ", t)).strip()


_RUIDO_ESTRUTURAL = re.compile(r"[^A-Z0-9/.,#\-+%:;()]+")


def normalizar_estrutura(s: str) -> str:
    """Como normalizar(), mas preserva ':' e ';'.

    A descricao legada usa esses dois sinais para delimitar par ATRIBUTO: VALOR,
    e e dali que saem os rotulos de treino (ver rotulos.py). Para CASAMENTO use
    normalizar(), que transforma a pontuacao em espaco e assim faz 'BITOLA:M14'
    casar com o valor 'M14'.
    """
    if s is None:
        return ""
    return _ESPACO.sub(" ", _RUIDO_ESTRUTURAL.sub(" ", _polegada(sem_acento(s).upper()))).strip()


def com_bordas(s: str) -> str:
    """Envolve em espacos para casamento de subcadeia respeitando limite de palavra.

    Evita o classico falso positivo de 'BA' casar dentro de 'BASL'.
    """
    return f" {normalizar(s)} "


def tokens(s: str) -> list[str]:
    return normalizar(s).split()


# Abreviacoes medidas na base legada (ver docs/01-dados.md).
#
# Esta tabela e o SENTIDO PADRAO de cada token. Quatro entradas tem mais de um
# sentido na base e passam antes por _resolver_por_contexto (ver
# docs/07-abreviacoes.md, que traz a medicao de cada uma): PN, REV, RET, IND.
#
# CAB fica de fora de proposito: na base, 752 dos 759 CAB sao 'CAB SEXTAVADA'
# (cabeca), mas o BERT foi treinado com o texto sem expansao e ve 'CAB'; trocar
# aqui so mudaria a entrada do modelo sem ganho de casamento (nenhum valor do
# PDM contem CABECA).
ABREVIACOES = {
    "PARAF": "PARAFUSO",
    "SEXT": "SEXTAVADO",
    "SEXTAV": "SEXTAVADO",
    "HIDR": "HIDRAULICA",
    "HID": "HIDRAULICA",
    "PNEUM": "PNEUMATICA",
    "IND": "INDUSTRIAL",
    "MANG": "MANGUEIRA",
    "MONT": "MONTADA",
    "ROL": "ROLAMENTO",
    "RET": "RETENTOR",
    "ARR": "ARRUELA",
    "VALV": "VALVULA",
    "ESF": "ESFERA",
    "DIAM": "DIAMETRO",
    "DIAMET": "DIAMETRO",
    "COMP": "COMPRIMENTO",
    "COMPR": "COMPRIMENTO",
    "LARG": "LARGURA",
    "ESP": "ESPESSURA",
    "MAT": "MATERIAL",
    "APLIC": "APLICACAO",
    "MOD": "MODELO",
    "FABR": "FABRICANTE",
    "FAB": "FABRICANTE",
    "MARCA": "FABRICANTE",
    "REF": "REFERENCIA",
    "INT": "INTERNO",
    "EXT": "EXTERNO",
    "LUBR": "LUBRIFICANTE",
    "CONT": "CONTATOR",
    "DISJ": "DISJUNTOR",
    "TERM": "TERMINAL",
    "ELETR": "ELETRICO",
    "ELETRD": "ELETRODO",
    "MANOM": "MANOMETRO",
    "ELEM": "ELEMENTO",
    "REV": "REVESTIDO",
    "ABRAS": "ABRASIVO",
    "CALC": "CALCADO",
    "OCUL": "OCULOS",
    "LAMP": "LAMPADA",
    "SENS": "SENSOR",
    "SEG": "SEGURANCA",
    "EQUIP": "EQUIPAMENTO",
    "CL": "CLASSE",
    "PN": "PART NUMBER",
    "ACAB": "ACABAMENTO",
    "CARB": "CARBONO",
    "ZB": "ZINCADO BRANCO",
    "ZA": "ZINCADO AMARELO",
    "GF": "GALVANIZADO A FOGO",
    "NIT": "NITRILICA",
    "BORR": "BORRACHA",
    "GALV": "GALVANIZADO",
}


# Pressoes nominais da serie PN (EN 1092 / ISO 7005). 'PN 16' e 'PN 25' sao
# VALORES PERMITIDOS do PDM (CLASSE PRESSAO de PDM040-043); expandir o PN deles
# para PART NUMBER destruia o valor antes do casamento literal.
PRESSAO_NOMINAL = frozenset(
    "2.5 2,5 6 10 16 25 40 63 100 160 250 320 400".split()
)

_VALVULA = frozenset({"VALV", "VALVULA"})
_SENSOR = frozenset({"SENS", "SENSOR"})

# Prefixo de barra: S/ACAB, C/TERMINAIS, P/ USO. Exige letra (ou nada) depois da
# barra, para nunca tocar fracao (1/2) nem codigo de peca (6205-2RS/C3).
_RX_BARRA = re.compile(r"^([CSP])/([A-Z][A-Z0-9\-]*)?$")
_BARRA = {"C": "COM", "S": "SEM", "P": "PARA"}
# Siglas de barra que NAO sao prefixo e ficam como estao: S/N (numero de serie)
# e P/N (part number). P/N chegou a ser expandido para PART NUMBER, e o BERT -
# treinado com o texto cru, que tem 'P/N' - passou a etiquetar a palavra
# FABRICANTE vizinha como valor de MATERIAL: 47 registros sairam de SANEADO
# (medicao com BERT em docs/07-abreviacoes.md, secao 5).
_BARRA_SIGLA = {"S/N": "S/N", "P/N": "P/N"}


def _resolver_por_contexto(limpo: str, anterior: str, proximo: str | None) -> str | None:
    """Sentido de um token ambiguo pelo vizinho. None = usar a tabela.

    Cada regra saiu de medicao na base (contexto de cada ocorrencia):
      PN   2.000 ocorrencias: 'PN 16'/'PN 25' e pressao nominal; o resto
           ('METSO PN 123', 'CATERPILLAR PN ...') e part number.
      REV  340: 331 sao 'REV A' colado a um part number (revisao de desenho).
      RET  183: 66 vem depois de VALV/VALVULA -> valvula de RETENCAO.
      IND  61: depois de SENSOR e INDUTIVO; depois de MANG e INDUSTRIAL.
    """
    if limpo == "PN":
        return "PN" if proximo in PRESSAO_NOMINAL else None
    if limpo == "REV":
        if proximo is not None and len(proximo) <= 2 and proximo.isalnum():
            return "REV"                       # REV A, REV 01: revisao
        if proximo is None and any(c.isdigit() for c in anterior):
            return "REV"                       # '...762-9053 REV' no fim da linha
        return None
    if limpo == "RET" and anterior in _VALVULA:
        return "RETENCAO"
    if limpo == "IND" and anterior in _SENSOR:
        return "INDUTIVO"
    return None


def _expandir_barra(limpo: str, tabela: dict[str, str]) -> str | None:
    """S/ACAB -> SEM ACABAMENTO; C/TERMINAIS -> COM TERMINAIS. None = nao e barra."""
    if limpo in _BARRA_SIGLA:
        return _BARRA_SIGLA[limpo]
    m = _RX_BARRA.match(limpo)
    if not m:
        return None
    prefixo, resto = _BARRA[m.group(1)], m.group(2)
    if not resto:
        return prefixo
    # Resto curto e desconhecido fica INTACTO. A DESCRICAO_CURTA e truncada em
    # 40 caracteres e corta 'S/ACAB' em 'S/AC'; expandido, viraria 'SEM AC' e o
    # token solto 'AC' casaria o sinonimo AC -> ACO CARBONO, inventando o
    # MATERIAL de um parafuso que nao o informa (registro 27031887).
    if resto not in tabela and len(resto) < 4:
        return None
    return f"{prefixo} {tabela.get(resto, resto)}"


def expandir(s: str, extra: dict[str, str] | None = None) -> str:
    """Expande abreviacoes token a token (regra 4: sem abreviacao).

    Tres passos por token, nesta ordem:
      1. sentido pelo contexto, para os tokens ambiguos (PN, REV, RET, IND);
      2. prefixo de barra (S/ = SEM, C/ = COM, P/ = PARA; P/N e S/N intocados);
      3. a tabela ABREVIACOES.

    O ponto final da abreviacao e removido antes da busca: a base escreve
    'RET.' e 'PARAF.', e sem isso o token nao casa na tabela.
    """
    tabela = dict(ABREVIACOES)
    if extra:
        tabela.update({normalizar(k): normalizar(v) for k, v in extra.items()})
    brutos = tokens(s)
    limpos = [t.strip(".,;:-") for t in brutos]
    saida = []
    for i, (t, limpo) in enumerate(zip(brutos, limpos)):
        anterior = limpos[i - 1] if i else ""
        proximo = limpos[i + 1] if i + 1 < len(limpos) else None
        r = _resolver_por_contexto(limpo, anterior, proximo)
        if r is None:
            r = _expandir_barra(limpo, tabela)
        if r is None:
            r = tabela.get(limpo, tabela.get(t, t))
        saida.append(r)
    return " ".join(saida)


def juntar(*partes: str) -> str:
    """Concatena textos sem repetir conteudo.

    DESCRICAO_CURTA e, na maioria dos registros, um truncamento da
    DESCRICAO_LONGA. Concatenar as duas duplicaria cada medida e quebraria a
    contagem de grandezas: a classe RETENTOR espera 3 valores em MM, e com o
    texto repetido apareceriam 6, derrubando a atribuicao por dominio.
    """
    saida: list[str] = []
    vistos: set[str] = set()
    for p in partes:
        n = normalizar(p)
        if not n:
            continue
        if n in " ".join(saida):          # ja contido (caso do truncamento)
            continue
        novos = [t for t in n.split() if t not in vistos]
        if not novos:
            continue
        saida.append(" ".join(novos))
        vistos.update(novos)
    return " ".join(saida)


# ------------------------------------------------------------------ numeros

_FRACAO = re.compile(r"^(?:(\d+)[.\s\-])?(\d+)/(\d+)$")


def parse_numero(s: str) -> float | None:
    """Le numero em notacao pt-BR ou en-US, resolvendo ponto-milhar x ponto-decimal.

    '16,25'  -> 16.25   (virgula e sempre decimal)
    '3.650'  -> 3650.0  (ponto + 3 digitos e milhar: 6.000 psi e seis mil)
    '1.5'    -> 1.5     (ponto + 1 ou 2 digitos e decimal)
    '0.591'  -> 0.591   (parte inteira zero nunca e milhar)
    '1.1/4'  -> 1.25    (notacao de polegada do PDM)
    """
    if s is None:
        return None
    bruto = normalizar(s)
    if not bruto:
        return None

    # fracao antes de colapsar espaco: '1 1/2' nao pode virar '11/2'
    m = _FRACAO.match(bruto.replace(" ", " ").strip())
    if not m:
        m = _FRACAO.match(bruto.replace(" ", ""))
    if m:
        inteiro, num, den = m.group(1), int(m.group(2)), int(m.group(3))
        if den == 0:
            return None
        return (int(inteiro) if inteiro else 0) + num / den

    # descarta sufixo de unidade: '15MM' -> '15', '215BAR' -> '215'
    achado = re.match(r"^([0-9][0-9.,]*)", bruto.replace(" ", ""))
    if not achado:
        return None
    t = achado.group(1).rstrip(".,")

    if "," in t:  # virgula presente: ela e o decimal, pontos sao milhar
        t = t.replace(".", "").replace(",", ".")
    elif "." in t:
        inteiro, _, resto = t.partition(".")
        # milhar so quando ha exatamente 3 digitos depois e a parte inteira nao e zero
        if len(resto) == 3 and resto.isdigit() and inteiro not in ("", "0"):
            t = inteiro + resto
    try:
        return float(t)
    except ValueError:
        return None


def _fmt_decimal_ptbr(v: float, casas: int = 2) -> str:
    """Numero no padrao PDM: decimal com virgula, sem zero a direita inutil."""
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.{casas}f}".rstrip("0").rstrip(".").replace(".", ",")


# ------------------------------------------------------------------ grandezas

# ISO 6708: diametro nominal de tubo/valvula/conexao <-> polegada.
# Nao se aplica a mangueira, onde DN costuma ser o diametro interno em mm.
DN_PARA_POL = {
    6: "1/8", 8: "1/4", 10: "3/8", 15: "1/2", 20: "3/4", 25: "1",
    32: "1.1/4", 40: "1.1/2", 50: "2", 65: "2.1/2", 80: "3", 90: "3.1/2",
    100: "4", 125: "5", 150: "6", 200: "8", 250: "10", 300: "12",
    350: "14", 400: "16", 450: "18", 500: "20", 600: "24",
    # Resto da serie da ISO 6708 / ASME B36.10. Faltavam os DN pares entre 500 e
    # 600 e toda a faixa acima de DN 600, que aparece em adutora e linha de
    # polpa. Sem eles fmt_pol('DN 700') devolvia None e a caixa ficava vazia.
    550: "22", 650: "26", 700: "28", 750: "30", 800: "32", 850: "34",
    900: "36", 950: "38", 1000: "40", 1050: "42", 1100: "44", 1200: "48",
    1300: "52", 1400: "56", 1500: "60", 1600: "64", 1800: "72", 2000: "80",
}

# Secao de cabo: AWG -> mm2 comercial (NBR NM 280 / NBR 6880).
# A chave 0 e o AWG 1/0; os calibres maiores (2/0, 3/0, 4/0) nao cabem num
# inteiro positivo e entram como -1, -2, -3, mantendo a ordem natural do calibre
# (quanto menor o numero AWG, maior a secao).
AWG_PARA_MM2 = {
    24: "0,2", 22: "0,34", 20: "0,5", 18: "1", 16: "1,5", 14: "2,5", 12: "4",
    10: "6", 8: "10", 6: "16", 4: "25", 3: "30", 2: "35", 1: "50", 0: "70",
    -1: "95", -2: "120", -3: "150",
}

# Pressao -> BAR (regra 6)
FATOR_BAR = {
    "BAR": 1.0,
    "PSI": 1.0 / 14.503773773,
    "LBF/POL2": 1.0 / 14.503773773,
    "MPA": 10.0,
    "KPA": 0.01,
    "KGF/CM2": 0.980665,
    "ATM": 1.01325,
}


def fmt_mm(valor: float | str) -> str | None:
    """-> '16,25MM' (regra 5: milimetro com decimal em virgula)."""
    v = valor if isinstance(valor, (int, float)) else parse_numero(valor)
    return None if v is None else f"{_fmt_decimal_ptbr(v)}MM"


def fmt_mm2(valor: float | str) -> str | None:
    """-> '1,5MM2' (regra 6: secao de cabo em MM2)."""
    v = valor if isinstance(valor, (int, float)) else parse_numero(valor)
    return None if v is None else f"{_fmt_decimal_ptbr(v)}MM2"


def fmt_metro(valor: float | str) -> str | None:
    v = valor if isinstance(valor, (int, float)) else parse_numero(valor)
    return None if v is None else f"{_fmt_decimal_ptbr(v)}M"


def fmt_pol(valor: float | str) -> str | None:
    """-> '1.1/4POL' (regra 5: fracao + POL, inteiro separado por ponto).

    Aceita float (1.25), fracao textual ('1 1/4', '1-1/4') ou DN ('DN 50').
    """
    if isinstance(valor, str):
        t = normalizar(valor)
        m = re.match(r"^DN\s*(\d+)$", t)
        if m:
            pol = DN_PARA_POL.get(int(m.group(1)))
            return f"{pol}POL" if pol else None
        v = parse_numero(t.replace("POL", "").replace('"', "").strip())
    else:
        v = float(valor)
    if v is None or v <= 0:
        return None
    # aproxima para a fracao comercial mais proxima em oitavos/dezesseis avos
    frac = Fraction(v).limit_denominator(16)
    inteiro, resto = divmod(frac, 1)
    if resto == 0:
        return f"{int(inteiro)}POL"
    if inteiro == 0:
        return f"{resto.numerator}/{resto.denominator}POL"
    return f"{int(inteiro)}.{resto.numerator}/{resto.denominator}POL"


def fmt_bar(valor: float | str, unidade: str = "BAR") -> str | None:
    """Converte para BAR e formata (regra 6: pressao sempre em BAR)."""
    v = valor if isinstance(valor, (int, float)) else parse_numero(valor)
    if v is None:
        return None
    fator = FATOR_BAR.get(normalizar(unidade).replace(" ", ""))
    if fator is None:
        return None
    return f"{_fmt_decimal_ptbr(v * fator, casas=1)}BAR"


def fmt_simples(valor: float | str, sufixo: str) -> str | None:
    """Grandezas de sufixo direto: A (corrente), W (potencia), V (tensao)."""
    v = valor if isinstance(valor, (int, float)) else parse_numero(valor)
    return None if v is None else f"{_fmt_decimal_ptbr(v)}{sufixo}"


def fmt_inteiro(valor: float | str) -> str | None:
    v = valor if isinstance(valor, (int, float)) else parse_numero(valor)
    return None if v is None else str(int(round(v)))


# ------------------------------------------------------------------ rosca

_BITOLA = re.compile(
    r"(?<![A-Z0-9])M\s?-?(\d{1,2})"
    r"(?:\s?[Xx*]\s?(\d{1,4}(?:[.,]\d+)?))?"      # passo OU comprimento
    r"(?:\s?[Xx*]\s?(\d{1,4}(?:[.,]\d+)?))?"      # comprimento, quando houve passo
    r"(?![0-9])"
)


# Passo GROSSO normal (ISO 261). 'M8X1,25' escreve o passo grosso explicitamente:
# e a mesma bitola M8 de rosca grossa, nao uma rosca fina.
PASSO_GROSSO = {3: 0.5, 4: 0.7, 5: 0.8, 6: 1.0, 8: 1.25, 10: 1.5, 12: 1.75,
                14: 2.0, 16: 2.0, 18: 2.5, 20: 2.5, 22: 2.5, 24: 3.0, 27: 3.0,
                30: 3.5, 33: 3.5, 36: 4.0}


def _e_passo(numero: str, diametro: int) -> bool:
    """O segundo numero de M<d>X<n> e passo de rosca fina, nao comprimento?

    Passo metrico vai de 0,2 a 3 (ISO 261). Comprimento de 3 mm ou menos so
    existe em parafuso miudo, entao: decimal ate 3 e sempre passo; inteiro ate 3
    e passo a partir de M6 (M8X1 e rosca fina; M3X3 e comprimento).
    """
    v = float(numero.replace(",", "."))
    if v > 3:
        return False
    return ("," in numero or "." in numero) or diametro >= 6


def separar_rosca_metrica(texto: str) -> dict[str, str]:
    """Desmembra notacao compacta (regra 2 do PDM).

    'M12X50' -> {'BITOLA': 'M12', 'COMPRIMENTO': '50MM', 'ROSCA': 'METRICA GROSSA'}

    O passo ausente implica rosca metrica grossa. Quando o passo aparece, ele faz
    parte da BITOLA, como o PDM escreve: M12X1,5 e M10X1,25 sao valores proprios
    da lista, e itens diferentes de M12 e M10.

      'M12X50'       -> BITOLA M12,      COMPRIMENTO 50MM, ROSCA METRICA GROSSA
      'M12X1,5'      -> BITOLA M12X1,5,                    ROSCA METRICA FINA
      'M10X1,25X70'  -> BITOLA M10X1,25, COMPRIMENTO 70MM, ROSCA METRICA FINA

    Antes o passo era lido como comprimento: 'M10X1,25X70' virava BITOLA M10 e
    COMPRIMENTO 1,25MM, e 'BITOLA:M12X1,5' virava M12 - juntando parafuso de
    rosca fina com o de rosca grossa.
    """
    t = normalizar(texto)
    m = _BITOLA.search(t)
    if not m:
        return {}
    d = int(m.group(1))
    a, b = m.group(2), m.group(3)
    # numero colado a unidade e comprimento, nunca passo: 'M16X1M' e barra de
    # 1 metro, 'M6X3MM' e parafuso de 3 mm
    com_unidade = bool(a) and t[m.end(2):m.end(2) + 1] == "M"
    passo = comprimento = None
    if a and b:
        passo, comprimento = (a, b) if _e_passo(a, d) else (None, a)
    elif a:
        passo, comprimento = (a, None) if (_e_passo(a, d) and not com_unidade) else (None, a)

    if passo and PASSO_GROSSO.get(d) == float(passo.replace(",", ".")):
        passo = None                          # passo grosso escrito: M8X1,25 = M8
    if passo:
        p = passo.replace(".", ",")
        p = p[:-2] if p.endswith(",0") else p
        out = {"BITOLA": f"M{d}X{p}"}
    else:
        out = {"BITOLA": f"M{d}"}
    # 'M16X1M' e 1 METRO: fmt_mm escreveria 1MM. Deixa o comprimento para a
    # gramatica, que conhece a unidade, em vez de gravar mil vezes menos.
    em_metro = com_unidade and t[m.end(2):m.end(2) + 2] != "MM" and comprimento == a and not b
    if comprimento and not em_metro:
        out["COMPRIMENTO"] = fmt_mm(comprimento) or ""
    out["ROSCA"] = "METRICA FINA" if (passo or "FINA" in t) else "METRICA GROSSA"
    return out
