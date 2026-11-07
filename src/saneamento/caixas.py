"""Caixas: cada linha do cadastro virada numa grade de caixas, uma por atributo.

    linha crua   RET. 110MM 15MM BASL NBR
                 |
    caixas       SUJEITO             RETENTOR
                 DIAMETRO EIXO       110MM      NUMERICA
                 DIAMETRO ALOJAMENTO <vazia>    NUMERICA
                 LARGURA             15MM       NUMERICA
                 TIPO                BASL       TEXTUAL
                 MATERIAL            NBR        TEXTUAL

O tipo da caixa decide quem pode preenche-la, e isso importa mais do que parece:

  TEXTUAL   atributo de vocabulario fechado do PDM. Aqui o embedding vale: o
            cadastro escreve 'INOX 316' ou 'AISI 316' e o padrao quer
            'ACO INOX 316'.
  NUMERICA  grandeza com formato fixo (MM, POL, BAR, MM2). Embedding NUNCA
            entra: modelo de vetor nao distingue 110MM de 15MM de forma
            confiavel, e aqui errar troca o diametro do eixo pela largura.
  LIVRE     part number, modelo de equipamento, referencia. Tambem sem
            embedding: 1R-1808 e P551808 sao filtros intercambiaveis, e por
            isso mesmo proximos no texto - mas sao itens DISTINTOS (regra 13).
            Aqui vale normalizacao de string e igualdade exata.

As bandas de confianca sao o contrato com o LLM: ele so e chamado na banda do
meio. Caixa EXATA ou ALTA segue sem chamada; caixa BAIXA e pendencia, nao
palpite.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .pdm import Atributo, Classe, aplica_atributo
from .texto import normalizar

# tipos de caixa
TEXTUAL = "TEXTUAL"
NUMERICA = "NUMERICA"
LIVRE = "LIVRE"

# bandas de confianca
EXATA = "EXATA"           # casamento literal: segue sem LLM
ALTA = "ALTA"             # similaridade alta e com margem: segue sem LLM
BANDA_LLM = "BANDA_LLM"   # parece bater, mas sem folga: LLM valida
BAIXA = "BAIXA"           # nao bate: pendencia, nunca palpite
VAZIA = "VAZIA"           # o texto nao informa

LIMIAR_ALTA = 0.92        # similaridade a partir da qual aceita sem LLM
LIMIAR_BANDA = 0.75       # abaixo disso nem o LLM e chamado: e pendencia
MARGEM_MINIMA = 0.04      # folga exigida entre o 1o e o 2o colocado


@dataclass
class Caixa:
    """Uma celula da grade: um atributo de um registro."""

    atributo: str
    tipo: str
    obrigatoria: bool = False
    bruto: str = ""                      # trecho do texto que caiu aqui
    valor: str | None = None             # valor canonico do PDM
    fonte: str = ""                      # gazetteer|gramatica|bert|embedding|llm|regra_pdm_2
    confianca: float = 0.0
    similaridade: float = 0.0            # cosseno com o 1o colocado
    margem: float = 0.0                  # cosseno(1o) - cosseno(2o)
    banda: str = VAZIA
    alternativas: tuple[str, ...] = ()
    motivo: str = ""

    @property
    def cheia(self) -> bool:
        return self.valor is not None

    @property
    def dispensa_llm(self) -> bool:
        return self.banda in (EXATA, ALTA)

    @property
    def chama_llm(self) -> bool:
        return self.banda == BANDA_LLM

    def como_dict(self) -> dict:
        return {
            "atributo": self.atributo, "tipo": self.tipo, "bruto": self.bruto,
            "valor": self.valor, "fonte": self.fonte, "banda": self.banda,
            "confianca": round(self.confianca, 3),
            "similaridade": round(self.similaridade, 3),
            "margem": round(self.margem, 3),
            "alternativas": list(self.alternativas), "motivo": self.motivo,
        }


@dataclass
class Grade:
    """Todas as caixas de uma linha, mais o que sobrou fora delas."""

    codigo: str
    id_pdm: str = ""
    substantivo: str = ""
    qualificador: str = ""
    caixas: dict[str, Caixa] = field(default_factory=dict)
    sobra: str = ""                      # texto que nao caiu em caixa nenhuma
    texto: str = ""
    confianca_sujeito: float = 0.0
    grupo_corrigido: bool = False

    # ------------------------------------------------------------- consultas

    def do_tipo(self, *tipos: str) -> list[Caixa]:
        return [c for c in self.caixas.values() if c.tipo in tipos]

    def na_banda(self, *bandas: str) -> list[Caixa]:
        return [c for c in self.caixas.values() if c.banda in bandas]

    @property
    def obrigatorias(self) -> list[Caixa]:
        return [c for c in self.caixas.values() if c.obrigatoria]

    @property
    def valores(self) -> dict[str, str | None]:
        return {n: c.valor for n, c in self.caixas.items()}

    @property
    def completude(self) -> float:
        obr = self.obrigatorias
        return sum(1 for c in obr if c.cheia) / len(obr) if obr else 1.0

    @property
    def tudo_bate(self) -> bool:
        """Toda caixa obrigatoria cheia e em banda que dispensa LLM.

        E a condicao do 'caso tudo bata nao chama a LLM': o registro vai direto
        para a juncao.
        """
        obr = self.obrigatorias
        return bool(obr) and all(c.cheia and c.dispensa_llm for c in obr)

    @property
    def para_llm(self) -> list[str]:
        """Caixas na banda do meio: o unico motivo de chamar o LLM."""
        return [c.atributo for c in self.caixas.values() if c.chama_llm]

    @property
    def pendentes(self) -> list[str]:
        return [c.atributo for c in self.obrigatorias if not c.cheia]

    def como_dict(self) -> dict:
        return {
            "codigo": self.codigo, "id_pdm": self.id_pdm,
            "substantivo": self.substantivo, "qualificador": self.qualificador,
            "completude": round(self.completude, 3),
            "tudo_bate": self.tudo_bate,
            "sobra": self.sobra,
            "caixas": [c.como_dict() for c in self.caixas.values()],
        }


# ------------------------------------------------------------------ montagem


def tipo_da_caixa(a: Atributo) -> str:
    """Classifica o atributo no tipo de caixa, pela coluna FORMATO do PDM."""
    if a.fechado:
        return TEXTUAL
    f = normalizar(a.formato)
    if any(u in f for u in ("MM", "POL", "BAR", "INTEIRO", "+ A", "+ W", "+ M",
                            "CERTIFICADO DE APROVACAO")):
        return NUMERICA
    return LIVRE


def grade_vazia(classe: Classe, codigo: str, substantivo: str,
                qualificador: str = "", texto: str = "") -> Grade:
    """Cria a grade com uma caixa por atributo aplicavel da classe."""
    g = Grade(codigo=codigo, id_pdm=classe.id_pdm, substantivo=substantivo,
              qualificador=qualificador, texto=texto)
    for a in sorted(classe.atributos, key=lambda x: x.ordem):
        if not aplica_atributo(a, substantivo):
            continue                      # regra 7: condicional fora do seu caso
        g.caixas[a.nome] = Caixa(
            atributo=a.nome,
            tipo=tipo_da_caixa(a),
            obrigatoria=a.obrigatorio and a.sempre,
        )
    return g


_TOKEN_NUMERICO = re.compile(r"\d+")


def gemeos_numericos(a: str | None, b: str | None) -> bool:
    """True quando dois valores diferem SO por numero ou codigo.

    ACO INOX 304 x ACO INOX 316, DIN 931 x DIN 933, 150# x 300#: tire os digitos
    e sobra exatamente o mesmo texto. Sao os pares que o embedding aproxima mais
    (cosseno 0,94 a 0,97) e os que custam mais caro confundir, porque geram um
    item errado na base. Nestes casos o vetor nao tem direito de decidir.
    """
    if not a or not b or a == b:
        return False
    sem_a = _TOKEN_NUMERICO.sub("#", normalizar(a))
    sem_b = _TOKEN_NUMERICO.sub("#", normalizar(b))
    if sem_a != sem_b:
        return False
    return _TOKEN_NUMERICO.findall(a) != _TOKEN_NUMERICO.findall(b)


def classificar_banda(similaridade: float, margem: float, exato: bool = False,
                      primeiro: str | None = None, segundo: str | None = None,
                      limiar_alta: float = LIMIAR_ALTA,
                      limiar_banda: float = LIMIAR_BANDA,
                      margem_minima: float = MARGEM_MINIMA) -> str:
    """Decide a banda da caixa: similaridade, MARGEM e trava de gemeo numerico.

    A margem e o que protege do erro mais caro deste dominio: similaridade alta
    sozinha nao prova nada quando o segundo colocado esta igualmente perto. Sem
    folga sobre o segundo, a caixa vai para o LLM mesmo com cosseno de 0,97.

    A trava de gemeo numerico e mais forte que a margem: se o 1o e o 2o diferem
    apenas por um numero, nunca sobe para ALTA, qualquer que seja a folga.
    """
    if exato:
        return EXATA
    if similaridade < limiar_banda:
        return BAIXA
    if gemeos_numericos(primeiro, segundo):
        return BANDA_LLM
    if similaridade >= limiar_alta and margem >= margem_minima:
        return ALTA
    return BANDA_LLM


_SEPARADOR = re.compile(r"[;,]|\s-\s")


def fatiar(texto: str) -> list[str]:
    """Quebra a linha nos delimitadores que o cadastro legado usa.

    Primeiro recurso de fatiamento, antes de qualquer modelo: 60% dos registros
    separam os atributos com ';' ou ',' e muitos usam ' - '.
    """
    return [p.strip() for p in _SEPARADOR.split(texto or "") if p.strip()]
