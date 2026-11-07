"""Casamento de um texto contra a lista fechada de valores de um atributo (regras 3 e 4).

Cada etapa é determinística e devolve a confiança: exato (1,0), sinônimo curado (0,95),
contido (0,9/0,85), aproximado (0,8). Ambiguidade nunca é resolvida por sorteio: devolve
None e a lista de candidatos, para a pessoa escolher.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .texto import normaliza, tokens


@dataclass(frozen=True)
class Casamento:
    valor: str | None
    confianca: float = 0.0
    motivo: str = ""
    candidatos: tuple[str, ...] = field(default_factory=tuple)


# Texto inteiro igual à variante → valor canônico (só vale se o canônico estiver na lista do atributo).
DIRETOS: dict[str, str] = {
    # vedação de rolamento (série + sufixo)
    "2RS": "BORRACHA AMBOS LADOS", "2RSH": "BORRACHA AMBOS LADOS", "2RS1": "BORRACHA AMBOS LADOS",
    "2RS2": "BORRACHA AMBOS LADOS", "DDU": "BORRACHA AMBOS LADOS", "2HRS": "BORRACHA AMBOS LADOS",
    "LLU": "BORRACHA AMBOS LADOS", "VEDADO": "BORRACHA AMBOS LADOS",
    "ZZ": "METALICA AMBOS LADOS", "2Z": "METALICA AMBOS LADOS", "2ZR": "METALICA AMBOS LADOS",
    "BLINDADO": "METALICA AMBOS LADOS", "OPEN": "ABERTO", "SEM VEDACAO": "ABERTO",
    # folga
    "CN": "NORMAL", "C0": "NORMAL",
    # aços
    "AISI 316": "ACO INOX 316", "AISI316": "ACO INOX 316", "SS316": "ACO INOX 316", "INOX 316": "ACO INOX 316",
    "A4": "ACO INOX 316", "AISI 304": "ACO INOX 304", "AISI304": "ACO INOX 304", "SS304": "ACO INOX 304",
    "INOX 304": "ACO INOX 304", "A2": "ACO INOX 304",
    # elastômeros e polímeros
    "NITRILICA": "NBR", "NITRILICO": "NBR", "BUNA N": "NBR", "BUNA-N": "NBR", "NITRILO": "NBR",
    "VITON": "FKM (VITON)", "FKM": "FKM (VITON)", "TEFLON": "PTFE",
    # acabamentos (zincado sem cor = branco: convenção do mercado, confiança menor)
    "ZINCADO": "ZINCADO BRANCO", "ZN": "ZINCADO BRANCO", "ZINCADO ELETROLITICO": "ZINCADO BRANCO",
    "HDG": "GALVANIZADO A FOGO", "ZINCADO A QUENTE": "GALVANIZADO A FOGO", "GALVANIZADO A QUENTE": "GALVANIZADO A FOGO",
    "GALV A FOGO": "GALVANIZADO A FOGO", "BLACK OXIDE": "OXIDADO PRETO", "OXIDADO": "OXIDADO PRETO",
    "SEM TRATAMENTO": "SEM ACABAMENTO", "BRUTO": "NATURAL",
}
_CONFIANCA_DIRETO_BAIXA = {"ZINCADO", "ZN", "ZINCADO ELETROLITICO", "OXIDADO", "VEDADO", "BLINDADO", "A2", "A4", "BRUTO"}

# Termos que, sozinhos, são ambíguos no mercado: "galvanizado" pode ser zincado ou a fogo.
AMBIGUOS: dict[str, tuple[str, ...]] = {
    "GALVANIZADO": ("GALVANIZADO A FOGO", "ZINCADO BRANCO", "ZINCADO AMARELO"),
    "GALVANIZADA": ("GALVANIZADO A FOGO", "ZINCADO BRANCO", "ZINCADO AMARELO"),
}


_GENERICAS = {"ACO", "CARBONO", "INOX", "FORJADO", "FUNDIDO", "LIGA", "FERRO", "MALEAVEL"}


def _toks(s: str) -> frozenset[str]:
    return frozenset(tokens(s))


def casa_lista(permitidos: tuple[str, ...] | list[str], texto: str | None) -> Casamento:
    nt = normaliza(texto)
    if not nt:
        return Casamento(None, 0.0, "vazio")
    norm = {v: normaliza(v) for v in permitidos}
    inv = {n: v for v, n in norm.items()}

    if nt in inv:
        return Casamento(inv[nt], 1.0, "exato")

    chave = re.sub(r"[\s\-_/]+", " ", nt).strip()
    if chave in AMBIGUOS:
        cands = tuple(v for v in AMBIGUOS[chave] if v in norm)
        if len(cands) > 1:
            return Casamento(None, 0.0, "ambiguo no mercado", cands)
    canon = DIRETOS.get(nt) or DIRETOS.get(chave)
    if canon:
        alvo = _procura_canonico(canon, norm)
        if alvo:
            conf = 0.85 if (nt in _CONFIANCA_DIRETO_BAIXA or chave in _CONFIANCA_DIRETO_BAIXA) else 0.95
            return Casamento(alvo, conf, f"sinonimo {nt}")

    tt = _toks(nt)
    # valor da lista inteiro dentro do texto (o mais longo vence)
    dentro = [(v, _toks(n)) for v, n in norm.items() if len(_toks(n)) >= 2 or len(n) >= 3]
    dentro = [(v, t) for v, t in dentro if t and t <= tt]
    if dentro:
        maior = max(len(t) for _, t in dentro)
        top = [v for v, t in dentro if len(t) == maior]
        if len(top) == 1:
            return Casamento(top[0], 0.9, "valor da lista contido no texto")
        return Casamento(None, 0.0, "ambiguo", tuple(top))

    # texto inteiro dentro de um único valor da lista
    if len(nt) >= 3:
        contem = [v for v, n in norm.items() if tt and tt <= _toks(n)]
        if len(contem) == 1:
            return Casamento(contem[0], 0.85, "texto contido em um unico valor")
        if len(contem) > 1:
            return Casamento(None, 0.0, "ambiguo", tuple(contem))

    # aproximado, com margem sobre o segundo colocado
    pontos = sorted(((SequenceMatcher(None, nt, n).ratio(), v) for v, n in norm.items()), reverse=True)
    if pontos and pontos[0][0] >= 0.88 and (len(pontos) == 1 or pontos[0][0] - pontos[1][0] >= 0.05):
        return Casamento(pontos[0][1], 0.8, "aproximado")
    return Casamento(None, 0.0, "sem correspondencia")


def _procura_canonico(canon: str, norm: dict[str, str]) -> str | None:
    c = normaliza(canon)
    for v, n in norm.items():
        if n == c:
            return v
    return None


def acha_no_texto(permitidos: tuple[str, ...] | list[str], texto: str) -> Casamento:
    """Procura valores da lista dentro de um texto livre (gazetteer). Só aceita ocorrência
    com fronteira de palavra e valor com ≥3 caracteres (ou letra+dígito), para não confundir
    `8` ou `A` com qualquer número ou letra solta."""
    nt = " " + normaliza(texto) + " "
    achados: list[str] = []
    por_codigo: set[str] = set()
    for v in permitidos:
        n = normaliza(v)
        if not (len(n) >= 3 or (re.search(r"[A-Z]", n) and re.search(r"\d", n))):
            continue
        if re.search(rf"(?<![A-Z0-9]){re.escape(n)}(?![A-Z0-9])", nt):
            achados.append(v)
    # valor "ACO CARBONO FUNDIDO A216 WCB": o texto costuma trazer só o código (A216 WCB)
    for v in permitidos:
        n = normaliza(v)
        resto = [t for t in n.split() if t not in _GENERICAS]
        if len(resto) < len(n.split()) and resto:
            codigo = " ".join(resto)
            if re.search(r"\d", codigo) and len(codigo) >= 3 and v not in achados and \
                    re.search(rf"(?<![A-Z0-9]){re.escape(codigo)}(?![A-Z0-9])", nt):
                achados.append(v)
                por_codigo.add(v)
    for variante, canon in DIRETOS.items():
        if len(variante) >= 3 and re.search(rf"(?<![A-Z0-9]){re.escape(variante)}(?![A-Z0-9])", nt):
            alvo = _procura_canonico(canon, {v: normaliza(v) for v in permitidos})
            if alvo and alvo not in achados:
                achados.append(alvo)
    # um valor contido em outro (ACO INOX 304 dentro de ACO INOX 304 ...): fica o mais longo
    achados = [a for a in achados if not any(a != b and normaliza(a) in normaliza(b) for b in achados)]
    if len(achados) == 1:
        if achados[0] in por_codigo:
            return Casamento(achados[0], 0.9, "codigo do valor da lista no texto")
        return Casamento(achados[0], 0.95, "valor da lista no texto")
    if len(achados) > 1:
        return Casamento(None, 0.0, "ambiguo no texto", tuple(achados))
    return Casamento(None, 0.0, "nao encontrado")
