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


def normalizar(s: str) -> str:
    """Forma canonica para comparacao: maiusculo, sem acento, espaco colapsado."""
    if s is None:
        return ""
    t = _RUIDO.sub(" ", sem_acento(s).upper())
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
    return _ESPACO.sub(" ", _RUIDO_ESTRUTURAL.sub(" ", sem_acento(s).upper())).strip()


def com_bordas(s: str) -> str:
    """Envolve em espacos para casamento de subcadeia respeitando limite de palavra.

    Evita o classico falso positivo de 'BA' casar dentro de 'BASL'.
    """
    return f" {normalizar(s)} "


def tokens(s: str) -> list[str]:
    return normalizar(s).split()


# Abreviacoes medidas na base legada (ver docs/01-dados.md).
# CAB e ambiguo (CABO x CABECA): resolvido pela classe, nunca aqui.
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


def expandir(s: str, extra: dict[str, str] | None = None) -> str:
    """Expande abreviacoes token a token (regra 4: sem abreviacao).

    O ponto final da abreviacao e removido antes da busca: a base escreve
    'RET.' e 'PARAF.', e sem isso o token nao casa na tabela.
    """
    tabela = dict(ABREVIACOES)
    if extra:
        tabela.update({normalizar(k): normalizar(v) for k, v in extra.items()})
    saida = []
    for t in tokens(s):
        limpo = t.strip(".,;:-")
        saida.append(tabela.get(limpo, tabela.get(t, t)))
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
}

# Secao de cabo: AWG -> mm2 comercial (NBR)
AWG_PARA_MM2 = {
    20: "0,5", 18: "1", 16: "1,5", 14: "2,5", 12: "4", 10: "6", 8: "10",
    6: "16", 4: "25", 2: "35", 1: "50", 0: "70",
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

_BITOLA = re.compile(r"(?<![A-Z0-9])M\s?-?(\d{1,2})(?:\s?[Xx*]\s?(\d{1,4}(?:[.,]\d+)?))?(?:\s?[Xx*]\s?(\d{1,4}(?:[.,]\d+)?))?(?![0-9])")
# 1/2POLX3 1/2POL: bitola x comprimento em polegada (a segunda medida pode ter parte inteira)
_POLEGADA_COMPOSTA = re.compile(
    r"(?<![0-9/.])((?:\d+[ .])?\d+/\d+|\d+)\s?(?:POL|\")\s?[Xx*]\s?((?:\d+[ .])?\d+/\d+|\d+)\s?(?:POL|\")")


def _eh_passo(numero: str) -> bool:
    """O passo da rosca tem casa decimal ou e pequeno (1; 1,25; 1,5). Comprimento de parafuso nunca."""
    return "," in numero or "." in numero or int(numero) <= 3


def _pol(medida: str) -> str:
    """'3 1/2' ou '3.1/2' -> '3.1/2POL'."""
    return re.sub(r"\s", ".", medida.strip()) + "POL"


_REF_LIXO = re.compile(r"\s*(?:[,;]|\bP/\s|\bPARA\b|\bITEM CRITICO\b|\bVER DESENHO\b|\bCONF\b|\bCOMPRA LOCAL\b|\bREF ANTIGA\b).*$")
_REF_REVISAO = re.compile(r"[\s\-/]*\bREV(?:ISAO)?\.?\s*[A-Z0-9]{0,2}$")
_REF_SUFIXO_00 = re.compile(r"[\s\-/]00$")


def referencia_limpa(valor: str | None) -> str:
    """Part number sem o ruido de cadastro, ainda legivel: `5751 9508 65 REV A` -> `5751 9508 65`.

    A base traz sufixo de revisao, observacao colada (`05307 P/ MANUTENCAO`) e `-00` de versao.
    """
    # sobre o texto ainda com pontuacao: a virgula e o `P/` marcam onde a observacao comeca
    t = re.sub(r"\s+", " ", sem_acento(str(valor or "")).upper()).strip()
    t = _REF_LIXO.sub("", t)
    t = _REF_REVISAO.sub("", t)
    if len(re.sub(r"[^A-Z0-9]", "", t)) > 6:
        t = _REF_SUFIXO_00.sub("", t)
    return t.strip(" -/.")


def referencia_canonica(valor: str | None) -> str:
    """Part number para comparar (regra 10): sem ruido, sem separadores e sem zero a esquerda."""
    r = re.sub(r"[^A-Z0-9]", "", referencia_limpa(valor))
    return r.lstrip("0") or r


def separar_rosca_metrica(texto: str) -> dict[str, str]:
    """Desmembra notacao compacta (regra 2 do PDM).

    'M12X50' -> {'BITOLA': 'M12', 'COMPRIMENTO': '50MM', 'ROSCA': 'METRICA GROSSA'}

    O passo ausente implica rosca metrica grossa. Quando o passo aparece
    (M12X1,5X50) a rosca e fina e a decisao fica para a camada de classe.
    """
    t = normalizar(texto)
    m = _BITOLA.search(t)
    if not m:
        p = _POLEGADA_COMPOSTA.search(t)
        return {"BITOLA": _pol(p.group(1)), "COMPRIMENTO": _pol(p.group(2))} if p else {}
    d, b, c = m.group(1), m.group(2), m.group(3)
    # M12X1,5X50: passo e comprimento. M12X1,5: so o passo. M12X50: so o comprimento.
    # Ler o passo como comprimento fechava a mesma chave para parafusos de 35, 60 e 150 mm.
    passo = b if b and (c or _eh_passo(b)) else None
    comprimento = c if c else (b if b and not passo else None)
    out = {"BITOLA": f"M{int(d)}X{passo.replace('.', ',')}" if passo else f"M{int(d)}"}
    if comprimento:
        out["COMPRIMENTO"] = fmt_mm(comprimento) or ""
    tem_passo = bool(passo) or "FINA" in t
    out["ROSCA"] = "METRICA FINA" if tem_passo else "METRICA GROSSA"
    return out
