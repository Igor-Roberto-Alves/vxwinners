"""Resolve o "substantivo" digitado (ou o texto de uma descrição) em classes do PDM.

Dois usos:
 - `buscar`: autocomplete de uma consulta curta, com a classe sempre confirmada por uma pessoa;
 - `detectar_no_texto`: acha nomes do PDM dentro de uma descrição longa, para estruturar a base e ler pedidos.
Sem LLM e sem escolha silenciosa: ambiguidade volta como mais de uma opção.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..normalizacao.texto import ABREVIACOES, normaliza, tokens
from ..pdm.modelo import Pdm

# Catálogos de fornecedor chegam em inglês (pedidos do tipo CATALOGO FORNECEDOR).
GLOSSARIO_EN: dict[str, str] = {
    "BALL VALVE": "VALVULA ESFERA", "GATE VALVE": "VALVULA GAVETA", "GLOBE VALVE": "VALVULA GLOBO",
    "CHECK VALVE": "VALVULA RETENCAO", "BUTTERFLY VALVE": "VALVULA BORBOLETA", "OIL SEAL": "RETENTOR",
    "O RING": "ANEL O-RING", "O-RING": "ANEL O-RING", "SAFETY BOOT": "CALCADO SEGURANCA",
    "SAFETY SHOE": "CALCADO SEGURANCA", "SAFETY GLOVE": "LUVA SEGURANCA", "SAFETY GLASSES": "OCULOS SEGURANCA",
    "ELECTRIC CABLE": "CABO ELETRICO", "PIPE FITTING": "CONEXAO", "BALL BEARING": "ROLAMENTO RIGIDO ESFERAS",
    "ROLLER BEARING": "ROLAMENTO ROLOS CONICOS", "HYDRAULIC HOSE": "MANGUEIRA HIDRAULICA",
    "V BELT": "CORREIA TRAPEZOIDAL", "OIL FILTER": "FILTRO OLEO LUBRIFICANTE", "AIR FILTER": "FILTRO AR",
    "FUEL FILTER": "FILTRO COMBUSTIVEL", "HEX BOLT": "PARAFUSO SEXTAVADO", "HEX NUT": "PORCA",
    "FLAT WASHER": "ARRUELA LISA", "SPRING WASHER": "ARRUELA PRESSAO", "THREADED ROD": "BARRA ROSCADA",
    "CIRCUIT BREAKER": "DISJUNTOR", "CONTACTOR": "CONTATOR", "FUSE": "FUSIVEL", "LED LAMP": "LAMPADA LED",
    "PRESSURE GAUGE": "MANOMETRO", "DRILL BIT": "BROCA HELICOIDAL", "WELDING ELECTRODE": "ELETRODO REVESTIDO",
    "FLANGE": "FLANGE", "ELBOW": "COTOVELO", "TEE": "TE", "COUPLING": "LUVA", "NIPPLE": "NIPLE", "UNION": "UNIAO",
    "BUSHING": "BUCHA", "GASKET": "JUNTA", "BEARING": "ROLAMENTO", "FILTER": "FILTRO", "HOSE": "MANGUEIRA",
    "BOLT": "PARAFUSO", "NUT": "PORCA", "WASHER": "ARRUELA", "VALVE": "VALVULA", "PIPE": "TUBO", "CABLE": "CABO",
    "LUBRICANT": "OLEO LUBRIFICANTE", "SENSOR": "SENSOR", "BELT": "CORREIA",
}
_GLOSSARIO_ORDENADO = sorted(GLOSSARIO_EN.items(), key=lambda kv: -len(kv[0]))
# Plurais e variações de gênero comuns em pedidos.
_VARIACOES = {"PARAFUSOS": "PARAFUSO", "PORCAS": "PORCA", "ARRUELAS": "ARRUELA", "VALVULAS": "VALVULA",
              "RETENTORES": "RETENTOR", "ROLAMENTOS": "ROLAMENTO", "MANGUEIRAS": "MANGUEIRA",
              "FILTROS": "FILTRO", "LUVAS": "LUVA", "JUNTAS": "JUNTA", "CORREIAS": "CORREIA", "CABOS": "CABO",
              "SEXTAVADA": "SEXTAVADO", "HIDRAULICA": "HIDRAULICO", "ELETRICA": "ELETRICO",
              "ESFERICA": "ESFERA", "ESFERAS": "ESFERA", "ROLOS": "ROLO", "CONICOS": "CONICO", "FILTRANTE": "FILTRO", "OLEO": "OLEO"}


def prepara(texto: str) -> list[str]:
    """Texto → tokens normalizados, com glossário inglês, plural e abreviações resolvidos."""
    t = " " + re.sub(r"[^A-Z0-9/.\-# ]", " ", normaliza(texto)) + " "
    for en, pt in _GLOSSARIO_ORDENADO:
        t = re.sub(rf"(?<![A-Z0-9]){re.escape(en)}(?![A-Z0-9])", f" {pt} ", t)
    toks = [x for x in re.split(r"[\s\-/]+", t) if x]
    out = []
    for x in toks:
        x = x.strip(".") or x
        x = _VARIACOES.get(x, x)
        x = ABREVIACOES.get(x, x)
        out.extend(x.split())
    return out


@dataclass(frozen=True)
class Sugestao:
    nome: str
    id_pdm: str
    grupo: str
    grupo_descricao: str
    pontos: float
    ambiguo: bool = False
    resto: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class IndiceClasses:
    pdm: Pdm
    frequencias: dict[tuple[str, str], int] = field(default_factory=dict)
    _nomes: list[tuple[str, str, tuple[str, ...]]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        for nome, idp in self.pdm.todos_os_nomes():
            self._nomes.append((nome, idp, tuple(prepara(nome))))

    def _freq(self, idp: str, nome: str) -> float:
        return math.log1p(self.frequencias.get((idp, nome), 0)) / 100

    def _sug(self, nome, idp, pontos, ambiguo=False, resto=()):
        c = self.pdm.classes[idp]
        return Sugestao(nome, idp, c.grupo, self.pdm.grupos.get(c.grupo, ""), round(pontos, 4), ambiguo, tuple(resto))

    # ------------------------------------------------------------ autocomplete
    def buscar(self, consulta: str, *, grupo: str | None = None, limite: int = 5) -> list[Sugestao]:
        q = prepara(consulta)
        if not q:
            return []
        achados = []
        for nome, idp, nt in self._nomes:
            if grupo and self.pdm.classes[idp].grupo != grupo:
                continue
            casados, resto = 0.0, []
            usados: set[int] = set()
            for tq in q:
                melhor = 0.0
                melhor_i = -1
                for i, tn in enumerate(nt):
                    if i in usados:
                        continue
                    if tn == tq:
                        s = 1.0
                    elif len(tq) >= 2 and tn.startswith(tq):
                        s = 0.85
                    elif len(tq) >= 4 and SequenceMatcher(None, tq, tn).ratio() >= 0.85:
                        s = 0.7
                    else:
                        continue
                    if s > melhor:
                        melhor, melhor_i = s, i
                if melhor_i >= 0:
                    usados.add(melhor_i)
                    casados += melhor
                else:
                    resto.append(tq)
            if casados == 0:
                continue
            cobertura_q = casados / len(q)
            cobertura_n = len(usados) / len(nt)
            if cobertura_q < 0.5:
                continue
            pontos = 0.65 * cobertura_q + 0.35 * cobertura_n + self._freq(idp, nome)
            if tuple(q) == nt:
                pontos += 0.2
            achados.append((self._sug(nome, idp, pontos, resto=resto), cobertura_q))
        achados.sort(key=lambda t: (-t[0].pontos, t[0].nome))
        # ambíguo: a consulta inteira casa nomes de mais de uma classe (LUVA: conexão, EPI, sobressalente)
        classes_completas = {a.id_pdm for a, cq in achados if cq >= 0.99}
        ambiguo = len(classes_completas) > 1
        saida = [a for a, _ in achados][:limite]
        if ambiguo:
            saida = [Sugestao(a.nome, a.id_pdm, a.grupo, a.grupo_descricao, a.pontos, True, a.resto) for a in saida]
        return saida

    # ------------------------------------------------------------ texto longo
    def detectar_no_texto(self, texto: str, *, grupo: str | None = None) -> list[Sugestao]:
        """Nomes do PDM inteiros dentro do texto. O mais longo vence; o grupo desempata.

        Quando o grupo é conhecido e só o substantivo aparece (LUVA em EPI01), o nome parcial do
        grupo (LUVA SEGURANCA) entra, mas só se nenhum nome completo do grupo casou.
        """
        toks = prepara(texto)
        bag = set(toks)
        completos, parciais = [], []
        for nome, idp, nt in self._nomes:
            if not nt:
                continue
            classe = self.pdm.classes[idp]
            no_grupo = bool(grupo) and classe.grupo == grupo
            completo = set(nt) <= bag
            parcial = (not completo and no_grupo and len(nt) >= 2 and nt[0] in bag)
            if not (completo or parcial):
                continue
            curto = sum(len(t) for t in nt) <= 3  # TE, CAP: só com grupo coerente
            if curto and not no_grupo:
                continue
            pos = [toks.index(t) for t in nt if t in toks]
            inicio = 0.05 if pos and min(pos) <= 1 else 0.0  # nome no começo da descrição
            bonus = (0.6 if no_grupo else 0.0) + inicio + self._freq(idp, nome)
            if completo:
                completos.append((self._sug(nome, idp, len(nt) + bonus), no_grupo))
            else:
                casados = len(set(nt) & bag)
                # parcial: tokens que casaram, com penalidade; a fração do nome coberta desempata
                parciais.append(self._sug(nome, idp, casados - 0.2 + 0.5 * casados / len(nt) + bonus))
        achados = [s for s, _ in completos]
        if not any(no_grupo for _, no_grupo in completos):
            achados += parciais
        achados.sort(key=lambda s: (-s.pontos, s.nome))
        if len(achados) >= 2 and achados[0].id_pdm != achados[1].id_pdm and achados[0].pontos - achados[1].pontos < 0.1:
            achados = [Sugestao(a.nome, a.id_pdm, a.grupo, a.grupo_descricao, a.pontos, True) for a in achados[:5]]
        return achados[:5]
