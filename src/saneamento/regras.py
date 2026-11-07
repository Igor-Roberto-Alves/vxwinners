"""Camada 1 - regras lexicas: as restricoes do PDM das quais nao se pode fugir.

Duas tarefas, ambas deterministicas:

  SUJEITO        classifica o registro numa das 44 classes, casando substantivo e
                 qualificador dentro do GRUPO_MERCADORIA (que esta 100% preenchido
                 e reduz 44 classes a 1-3 candidatas).

  CARACTERISTICAS  preenche atributo por atributo. 74,9% dos atributos obrigatorios
                 tem lista de valores permitidos: isso e casamento contra dicionario,
                 nao tarefa de modelo de linguagem. O resto e grandeza numerica com
                 formato fixo, que e gramatica.

Esta camada nunca inventa valor. Quando o texto nao diz, devolve None.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .pdm import Atributo, Classe, Pdm, aplica_atributo
from .rotulos import pares
from .sinonimos import SINONIMOS
from .texto import (
    com_bordas,
    expandir,
    fmt_bar,
    fmt_inteiro,
    fmt_metro,
    fmt_mm,
    fmt_mm2,
    fmt_pol,
    fmt_simples,
    normalizar,
    parse_numero,
    separar_rosca_metrica,
)


@dataclass
class Candidato:
    """Proposta de valor para um atributo, com a evidencia que a sustenta."""

    atributo: str
    valor: str | None = None
    fonte: str = "regras"
    confianca: float = 0.0
    evidencia: str = ""
    alternativas: tuple[str, ...] = ()
    ambiguo: bool = False
    motivo: str = ""


@dataclass
class Sujeito:
    classe: Classe | None = None
    substantivo: str = ""
    qualificador: str = ""
    confianca: float = 0.0
    empate: tuple[str, ...] = ()
    evidencia: str = ""
    grupo_corrigido: bool = False


# --------------------------------------------------------------- classificacao


class ClassificadorLexico:
    def __init__(self, pdm: Pdm):
        self.pdm = pdm
        self._ext = None          # extrator usado so para testar evidencia de irmao

    def classificar(self, texto: str, grupo: str | None = None) -> Sujeito:
        """Classifica dentro do grupo e, se nada casar, tenta as 44 classes.

        O GRUPO_MERCADORIA da base esta errado em parte dos registros (o item
        12711820 e um retentor cadastrado em TUB01). Quando a busca restrita ao
        grupo nao acha nada mas a busca ampla acha, o resultado vem com
        grupo_corrigido=True: corrigir o grupo e entregavel, nao efeito colateral.
        """
        from .sinonimos import expandir_sujeito

        texto = expandir_sujeito(texto)
        no_grupo = self.pdm.por_grupo.get(grupo or "")
        if no_grupo:
            s = self._buscar(texto, no_grupo)
            if s.classe is not None:
                return self._preferir_irmao_especifico(texto, s)
        s = self._buscar(texto, list(self.pdm.classes.values()))
        if s.classe is not None and no_grupo:
            s = self._preferir_irmao_especifico(texto, s)

        # Grupo de classe unica: trocar de grupo e pior que aceitar a unica
        # classe possivel com confianca baixa. 'ELEMENTO FILTRANTE OLEO ...'
        # estava em FIL01 e virava OLEO LUBRIFICANTE por causa da palavra OLEO.
        if no_grupo and len(no_grupo) == 1:
            unica = no_grupo[0]
            if s.classe is None or s.classe.grupo != unica.grupo:
                return Sujeito(classe=unica, substantivo=unica.substantivos[0],
                               qualificador=unica.qualificadores[0] if len(unica.qualificadores) == 1 else "",
                               confianca=0.50,
                               evidencia=f"unica classe do grupo {unica.grupo}")

        if s.classe is not None and no_grupo:
            s.grupo_corrigido = True
            s.confianca = min(s.confianca, 0.70)
        return s

    def _preferir_irmao_especifico(self, texto: str, s: Sujeito) -> Sujeito:
        """Troca para um irmao mais especifico quando o texto evidencia as caixas
        exclusivas dele.

        PDM011 (mangueira hidraulica MONTADA) e PDM010 (mangueira avulsa) mais
        COMPRIMENTO, TERMINAL A, TERMINAL B e MATERIAL TERMINAIS. A base escreve
        131 montadas como 'MANGUEIRA HIDRAULICA C/TERMINAIS', sem a palavra
        MONTADA em lugar nenhum - so as caixas exclusivas revelam o que o item e.

        A regra e estrutural, nao decorada: vale para qualquer par de classes do
        PDM em que o qualificador de uma seja superconjunto do da outra. A troca
        exige evidencia em pelo menos metade das caixas exclusivas (minimo 2),
        para nao virar por um sinal fraco isolado.
        """
        c = s.classe
        if c is None:
            return s
        meus = set(s.qualificador.split())
        nomes_meus = {a.nome for a in c.atributos}

        melhor = None
        for irmao in self.pdm.por_grupo.get(c.grupo, []):
            if irmao.id_pdm == c.id_pdm or s.substantivo not in irmao.substantivos:
                continue
            if not any(set(q.split()) > meus for q in irmao.qualificadores):
                continue                     # nao e mais especifico que o atual
            exclusivas = [a for a in irmao.atributos
                          if a.obrigatorio and a.nome not in nomes_meus]
            if len(exclusivas) < 2:
                continue
            if self._ext is None:
                self._ext = ExtratorLexico(self.pdm)
            achadas = self._ext.extrair(texto, irmao, s.substantivo)
            evidencias = sum(1 for a in exclusivas if achadas.get(a.nome)
                             and achadas[a.nome].valor)
            minimo = max(2, (len(exclusivas) + 1) // 2)
            if evidencias >= minimo and (melhor is None or evidencias > melhor[0]):
                melhor = (evidencias, irmao, exclusivas)

        if melhor is None:
            return s
        evidencias, irmao, exclusivas = melhor
        qual = max((q for q in irmao.qualificadores if set(q.split()) > meus),
                   key=len, default=irmao.qualificadores[0] if irmao.qualificadores else "")
        return Sujeito(
            classe=irmao, substantivo=s.substantivo, qualificador=qual,
            confianca=min(s.confianca, 0.85),
            grupo_corrigido=s.grupo_corrigido,
            evidencia=(f"{s.substantivo} {qual} (trocado de {c.id_pdm}: "
                       f"{evidencias}/{len(exclusivas)} caixas exclusivas evidenciadas)"),
        )

    def _buscar(self, texto: str, candidatas: list[Classe]) -> Sujeito:
        t = com_bordas(expandir(texto))
        achados: list[tuple[int, int, Classe, str, str]] = []
        for c in candidatas:
            melhor_s, subst = 0, ""
            for s in c.substantivos:
                if s and com_bordas(s) in t and len(s) > melhor_s:
                    melhor_s, subst = len(s), s
            if not melhor_s:
                continue
            melhor_q, qual = 0, ""
            for q in c.qualificadores:
                # Qualificador casa por CONJUNTO DE TOKENS, nao como string
                # contigua: o PDM escreve 'HIDRAULICA MONTADA' e a base escreve
                # 'MONTADA HIDRAULICA'. Com casamento contiguo, 325 dos 444
                # registros de PDM010 eram mangueira montada classificada como
                # mangueira avulsa. O substantivo continua contiguo, porque ali a
                # ordem faz parte do nome ('ANEL EXPULSOR').
                tokens_q = q.split()
                if not all(com_bordas(x) in t for x in tokens_q):
                    continue
                peso = sum(len(x) for x in tokens_q)
                if peso > melhor_q:
                    melhor_q, qual = peso, q
            achados.append((melhor_s + melhor_q, melhor_q, c, subst, qual))

        if not achados:
            return Sujeito()

        achados.sort(key=lambda x: (-x[0], -x[1]))
        topo = [a for a in achados if a[0] == achados[0][0]]
        _, com_qual, classe, subst, qual = achados[0]
        # confianca: substantivo+qualificador casados e sem empate e o caso forte
        if len(topo) > 1:
            conf = 0.55
        elif com_qual:
            conf = 0.95
        else:
            conf = 0.80 if len(classe.qualificadores) <= 1 else 0.70
        return Sujeito(
            classe=classe,
            substantivo=subst,
            qualificador=qual,
            confianca=conf,
            empate=tuple(a[2].id_pdm for a in topo) if len(topo) > 1 else (),
            evidencia=f"{subst} {qual}".strip(),
        )


# ------------------------------------------------------------------ extracao

# Padroes de grandeza. Mantidos simples de proposito: o que eles nao resolvem
# e justamente o residuo que vai para o BERT e para o LLM.
RX = {
    "MM": re.compile(r"(?<![A-Z0-9,.])(\d+(?:[.,]\d+)?)\s*MM(?![0-9A-Z])"),
    "MM2": re.compile(r"(\d+(?:[.,]\d+)?)\s*MM\s?2(?![0-9])"),
    "POL": re.compile(r"(?<![A-Z0-9])(\d+(?:[.\s\-]\d+/\d+|/\d+)?)\s*(?:POL|\"|INCH)(?![A-Z])"),
    "DN": re.compile(r"(?<![A-Z0-9])DN\s?(\d{1,3})(?![0-9])"),
    "BAR": re.compile(r"(\d+(?:[.,]\d+)?)\s*(BAR|PSI|MPA|KPA|KGF/CM2|ATM)(?![A-Z0-9])"),
    "A": re.compile(r"(?<![A-Z0-9])(\d+(?:[.,]\d+)?)\s*A(?![A-Z0-9])"),
    "W": re.compile(r"(?<![A-Z0-9])(\d+(?:[.,]\d+)?)\s*W(?![A-Z0-9])"),
    "M": re.compile(r"(?<![A-Z0-9])(\d+(?:[.,]\d+)?)\s*M(?![A-Z0-9])"),
    "CA": re.compile(r"(?<![0-9])(\d{5})(?![0-9])"),
    "BITOLA": re.compile(r"(?<![A-Z0-9])M\s?-?(\d{1,2})(?![0-9])"),
    # inteiro solto: nao pode capturar o numero de dentro de uma unidade.
    # Sem o (?![0-9A-Z]), 'SECAO 35MM2' virava NUMERO CONDUTORES = 35, e o erro
    # cascateava para a chave de identidade, juntando itens diferentes.
    "INT": re.compile(r"(?<![A-Z0-9,./\-])(\d{1,3})(?![0-9A-Z,./\-])"),
}

# Teto de passadas da extracao condicional (regra 7). Tres, e o limite e
# obrigatorio, nao defensivo: as condicoes do PDM nao sao monotonas. "somente
# MINIDISJUNTOR DIN" fica MAIS aplicavel quando o contexto cresce e "todas,
# exceto conexoes para solda de topo (BW)" fica MENOS; um par dessas duas se
# alternaria indefinidamente. O PDM de hoje nao tem cadeia mais longa que duas
# (TIPO -> CURVA, TIPO -> ESPESSURA), entao a segunda passada basta; a terceira
# existe para absorver um encadeamento novo sem reescrever o laco, e a quarta
# seria sinal de condicao circular na planilha, nao de atributo a extrair.
PASSADAS_CONDICIONAL = 3

# Restricao de dominio para desempatar grandezas de mesma unidade na mesma classe.
# Vale mais que qualquer modelo: alojamento e sempre maior que eixo, que e maior
# que largura. Peso menor = valor menor.
PESO_DOMINIO = {
    "DIAMETRO ALOJAMENTO": 3, "DIAMETRO EXTERNO": 3, "DIAMETRO NOMINAL": 3,
    "DIAMETRO EIXO": 2, "DIAMETRO INTERNO": 2, "ALTURA": 2, "COMPRIMENTO": 2,
    "LARGURA": 1, "ESPESSURA": 1,
}


def _familias(a: Atributo) -> tuple[str, ...]:
    """Parsers de grandeza que servem o atributo, em ordem de preferencia.

    Alguns formatos citam duas unidades: PDM001 COMPRIMENTO e "rosca metrica:
    numero + MM (50MM); rosca em polegada: fracao + POL (2.1/4POL)". Tenta MM
    primeiro, depois POL.
    """
    f = normalizar(a.formato)
    if "MM2" in f:
        return ("MM2",)
    if "CERTIFICADO DE APROVACAO" in f:
        return ("CA",)
    # BITOLA cita "M + diametro em mm", mas nao e uma medida em MM: e a
    # designacao da rosca (M12). Sem esta guarda BITOLA disputaria com
    # COMPRIMENTO os numeros em MM e as duas ficariam ambiguas.
    if "M + DIAMETRO" in f:
        return ("BITOLA",)
    fams = []
    if "MM" in f:
        fams.append("MM")
    if "POL" in f or "POLEGADA" in f:
        fams.append("POL")
    if "BAR" in f:
        fams.append("BAR")
    if "+ A" in f or f.endswith(" A"):
        fams.append("A")
    if "+ W" in f:
        fams.append("W")
    if "+ M" in f or f.endswith(" M"):
        fams.append("M")
    if not fams and f == "INTEIRO":
        fams.append("INT")
    return tuple(fams)


def _familia(a: Atributo) -> str | None:
    fams = _familias(a)
    return fams[0] if fams else None


def _formatar(familia: str, valor, unidade: str = "") -> str | None:
    if familia == "MM":
        return fmt_mm(valor)
    if familia == "MM2":
        return fmt_mm2(valor)
    if familia == "POL":
        return fmt_pol(valor)
    if familia == "BAR":
        return fmt_bar(valor, unidade or "BAR")
    if familia == "M":
        return fmt_metro(valor)
    if familia in ("A", "W"):
        return fmt_simples(valor, familia)
    if familia in ("CA", "INT"):
        return fmt_inteiro(valor)
    if familia == "BITOLA":
        n = fmt_inteiro(valor)
        return f"M{n}" if n else None
    return None


class ExtratorLexico:
    def __init__(self, pdm: Pdm, aprendizado=None):
        from .validador import Validador

        self.pdm = pdm
        self.validador = Validador(pdm)
        # dicionario alimentado pelo LLM/BERT em execucoes anteriores
        self.aprendizado = aprendizado
        # Sinonimos relevantes por atributo, calculados uma vez. Sem este cache,
        # seriam ~150 buscas de subcadeia por atributo por registro.
        self._sin: dict[tuple[str, str], list[tuple[str, str]]] = {}

    def _sinonimos_do(self, a: Atributo) -> list[tuple[str, str]]:
        """[(termo a procurar, valor canonico)], do mais longo para o mais curto.

        A chave do cache precisa ser (classe, atributo), nunca so o nome: os 93
        nomes de atributo do PDM sao GLOBAIS, e 'TIPO' existe em retentor
        (B1|BA|BAB|BASL), em cabo (FLEXIVEL|RIGIDO|...) e em disjuntor
        (MINIDISJUNTOR DIN|CAIXA MOLDADA|MOTOR). Indexando so pelo nome, a
        primeira classe processada envenenava o cache de todas as outras.
        """
        chave_cache = (a.id_pdm, a.nome)
        if chave_cache not in self._sin:
            chaves = a.chaves
            pares = [(k, chaves[normalizar(v)]) for k, v in SINONIMOS.items()
                     if normalizar(v) in chaves]
            self._sin[chave_cache] = sorted(pares, key=lambda x: -len(x[0]))
        return self._sin[chave_cache]

    # ---------------------------------------------------------- vocabulario

    def _por_gazetteer(self, t: str, a: Atributo) -> Candidato:
        """Casa os valores permitidos do atributo, com limite de palavra e match mais longo.

        Quando nenhum valor aparece literalmente, tenta o dicionario de sinonimos
        de dominio: a base escreve 'MINI DISJUNTOR' e 'DIN' onde o PDM exige
        'MINIDISJUNTOR DIN', e 'AISI 316' onde exige 'ACO INOX 316'.
        """
        chaves = a.chaves
        achados = [k for k in chaves if com_bordas(k) in t]
        if not achados:
            for termo, canonico in self._sinonimos_do(a):
                if com_bordas(termo) in t:
                    return Candidato(a.nome, canonico, "sinonimo", 0.94,
                                     termo, ambiguo=False)
            # dicionario aprendido: o que o LLM/BERT ja resolveu antes, para a
            # mesma duvida nao voltar a custar uma chamada
            if self.aprendizado is not None:
                aprendido = self.aprendizado.consultar(a, t)
                if aprendido:
                    confiavel = self.aprendizado.confiavel(a.nome, aprendido)
                    return Candidato(a.nome, aprendido, "aprendido",
                                     0.93 if confiavel else 0.80,
                                     "dicionario aprendido", ambiguo=False)
            return Candidato(a.nome, None, "gazetteer", 0.0)
        achados.sort(key=len, reverse=True)
        # subcadeia de um valor maior nao conta como alternativa:
        # ACO INOX 316 engloba INOX 316, e so o mais longo vale
        achados = [k for k in achados
                   if not any(k != o and com_bordas(k) in com_bordas(o) for o in achados)]
        distintos = [chaves[k] for k in achados]
        if len(distintos) == 1:
            return Candidato(a.nome, distintos[0], "gazetteer", 0.98, distintos[0])
        return Candidato(
            a.nome, distintos[0], "gazetteer", 0.45, distintos[0],
            alternativas=tuple(distintos), ambiguo=True,
        )

    # ---------------------------------------------------------- grandezas

    def _por_gramatica(self, t: str, classe: Classe, alvo: Atributo,
                       substantivo: str = "",
                       conhecidos: dict[str, str | None] | None = None) -> Candidato:
        ultimo = Candidato(alvo.nome, None, "gramatica", 0.0)
        for fam in _familias(alvo):
            c = self._uma_familia(t, classe, alvo, substantivo, fam, conhecidos)
            if c.valor is not None:
                return c
            if c.ambiguo:
                ultimo = c
        return ultimo

    def _uma_familia(self, t: str, classe: Classe, alvo: Atributo,
                     substantivo: str, fam: str,
                     conhecidos: dict[str, str | None] | None = None) -> Candidato:
        # Atributos da mesma classe que disputam a mesma familia de grandeza.
        # Inclui o obrigatorio CONDICIONAL que se aplica com os valores ja
        # conhecidos: classe.obrigatorios filtra quando=='sempre' e deixava
        # DIAMETRO REDUZIDO fora da disputa, entao numa BUCHA REDUCAO ele caia no
        # ramo de irmao unico e recebia o MESMO numero que DIAMETRO NOMINAL (o
        # primeiro do texto), em vez do segundo. O conjunto de irmaos tem de ser
        # o mesmo para todos eles, senao a atribuicao posicional troca medidas -
        # e trocar espessura por diametro cria item errado na base.
        # Irmaos de grandeza: TODO atributo da mesma familia disputa os numeros do
        # texto, obrigatorio ou nao. Filtrar por obrigatorio deixava o opcional
        # como "irmao unico", e irmao unico copia o primeiro numero que achar:
        # SECAO de PDM031 recebia o valor de DIAMETRO INTERNO, e as tres
        # dimensoes de PDM004 (todas opcionais) nunca passavam pela restricao de
        # dominio. Medido no gabarito: DIAMETRO INTERNO tinha recall de 66,5%.
        irmaos = [a for a in classe.atributos
                  if fam in _familias(a)
                  and aplica_atributo(a, substantivo, conhecidos)]
        achados = self._achar(t, fam)

        if not achados:
            return Candidato(alvo.nome, None, "gramatica", 0.0)

        if len(irmaos) <= 1:
            bruto, unidade = achados[0]
            val = _formatar(fam, bruto, unidade)
            conf = 0.90 if len(achados) == 1 else 0.60
            return Candidato(
                alvo.nome, val, "gramatica", conf, f"{bruto}{unidade}",
                alternativas=tuple(_formatar(fam, b, u) or f"{b}{u}" for b, u in achados)
                if len(achados) > 1 else (),
                ambiguo=len(achados) > 1,
            )

        # Menos numeros que caixas: distribui pelas de MAIOR PRIORIDADE e deixa
        # as de menor honestamente vazias, em vez de declarar tudo ambiguo.
        #
        # Reconcilia duas exigencias que pareciam opostas:
        #   - 'DISCO ABRASIVO CORTE 115MM' tem um numero e tres caixas em MM
        #     (DIAMETRO obrigatorio, ESPESSURA condicional, FURO opcional). O
        #     diametro ja estava certo e nao pode ser perdido.
        #   - mas caixa OPCIONAL nao pode copiar o primeiro numero que achar, que
        #     e como SECAO de PDM031 recebia o valor de DIAMETRO INTERNO.
        # A prioridade resolve: obrigatorio sempre > obrigatorio condicional >
        # opcional. Com um numero so, ele vai para o obrigatorio e as outras
        # ficam vazias.
        if len(achados) < len(irmaos):
            def prioridade(a):
                return (0 if (a.obrigatorio and a.sempre) else
                        1 if a.obrigatorio else 2, a.ordem)
            elegiveis = sorted(irmaos, key=prioridade)[:len(achados)]
            if alvo.nome not in {x.nome for x in elegiveis}:
                return Candidato(alvo.nome, None, "gramatica", 0.0,
                                 motivo=f"{len(achados)} numero(s) em {fam} para "
                                        f"{len(irmaos)} caixas: prioridade foi para "
                                        f"{[x.nome for x in elegiveis]}")
            return self._atribuir_por_dominio(fam, elegiveis, achados, alvo)

        # mais numeros que caixas: nao da para escolher sem inventar
        if len(achados) > len(irmaos):
            return Candidato(
                alvo.nome, None, "gramatica", 0.0,
                alternativas=tuple(f"{b}{u}" for b, u in achados),
                ambiguo=True,
            )
        return self._atribuir_por_dominio(fam, irmaos, achados, alvo)

    @staticmethod
    def _achar(t: str, fam: str) -> list[tuple[str, str]]:
        """Numeros da familia encontrados no texto, na ordem de leitura."""
        if fam == "BAR":
            return [(m.group(1), m.group(2)) for m in RX["BAR"].finditer(t)]
        if fam == "POL":
            achados = [(m.group(1), "POL") for m in RX["POL"].finditer(t)]
            achados += [(f"DN {m.group(1)}", "") for m in RX["DN"].finditer(t)]
            return achados
        if fam == "MM":  # MM2 nao e MM
            return [(m.group(1), "") for m in RX["MM"].finditer(t) if not RX["MM2"].match(m.group(0))]
        return [(m.group(1), "") for m in RX[fam].finditer(t)]

    @staticmethod
    def _atribuir_por_dominio(fam, irmaos, achados, alvo) -> Candidato:
        """Casa n numeros com n atributos usando restricao de dominio.

        Se todos os irmaos tem peso de dominio conhecido, ordena por grandeza
        (maior numero -> atributo de maior peso). Caso contrario cai na ordem de
        leitura do texto contra a coluna ORDEM do PDM.
        """
        pesos = [PESO_DOMINIO.get(a.nome) for a in irmaos]
        valores = [(parse_numero(b) or 0.0, b, u) for b, u in achados]

        if all(p is not None for p in pesos) and len(set(pesos)) == len(pesos):
            ordenados = sorted(zip(pesos, irmaos), key=lambda x: -x[0])
            valores.sort(key=lambda x: -x[0])
            fonte, conf = "dominio", 0.85
        else:
            ordenados = [(0, a) for a in sorted(irmaos, key=lambda a: a.ordem)]
            fonte, conf = "ordem_pdm", 0.65

        for (_, a), (_, bruto, unidade) in zip(ordenados, valores):
            if a.nome == alvo.nome:
                return Candidato(alvo.nome, _formatar(fam, bruto, unidade),
                                 fonte, conf, f"{bruto}{unidade}")
        return Candidato(alvo.nome, None, fonte, 0.0)

    # ---------------------------------------------------------- orquestracao

    def _por_rotulo(self, rotulados: dict[str, str], a: Atributo) -> Candidato:
        """CAMADA 0: o proprio cadastro escreveu o nome da caixa ao lado do valor.

        59,9% dos registros tem pares 'ATRIBUTO: VALOR' na descricao longa. Para
        esses a resposta nao precisa de inferencia nenhuma: basta ler o rotulo.

        Isto faltava, e custava caro. Medido contra gabarito independente (os
        proprios rotulos, nos 3.230 registros fora do treino do BERT), as tres
        maiores fontes de erro do pipeline eram todas a mesma causa - ignorar o
        rotulo e tentar adivinhar pela posicao:

          REFERENCIA FABRICANTE  precisao 73,2%  o BERT engolia a palavra seguinte
                                                 ('MM1728484 APLICACAO')
          DIAMETRO INTERNO       recall   66,5%  'DIAMETRO INTERNO:45MM' escrito,
                                                 caixa vazia, porque a gramatica
                                                 so conta concorrente obrigatorio
          COMPRIMENTO            precisao 95,6%  'BITOLA:M-24X2, COMPRIMENTO:220MM'
                                                 virava 2MM - pegou o passo da rosca

        O parser `pares()` ja existia: era usado para gerar os 61.869 rotulos de
        treino do BERT por distant supervision. Ou seja, o rotulo ensinava o
        modelo a adivinhar o que ele mesmo ja dizia, e na extracao era jogado
        fora. Camada barata construida e nao ligada - o terceiro caso deste
        projeto, depois de sinonimos.py e do dicionario aprendido.

        O valor ainda passa pelo validador: rotulo nao autoriza valor invalido.
        """
        valor = rotulados.get(a.nome)
        if not valor:
            return Candidato(a.nome, None, "rotulo", 0.0)
        v = self.validador.valor(a, valor)
        if not v.ok:
            return Candidato(a.nome, None, "rotulo", 0.0,
                             motivo=f"rotulado como {valor!r}: {v.motivo}")
        return Candidato(a.nome, v.valor, "rotulo", 0.99, valor)

    def _um_atributo(self, t: str, bruto: str, rosca: dict, classe: Classe,
                     a: Atributo, substantivo: str,
                     conhecidos: dict[str, str | None] | None,
                     rotulados: dict[str, str] | None = None) -> Candidato:
        # camada 0: o rotulo esta escrito na linha
        if rotulados:
            c = self._por_rotulo(rotulados, a)
            if c.valor is not None:
                return c
        if a.fechado:
            c = self._por_gazetteer(t, a)
            if c.valor is None:
                c = self._por_gazetteer(bruto, a)
        else:
            c = self._por_gramatica(t, classe, a, substantivo, conhecidos)

        # regra 2 do PDM: notacao compacta M12X50 tem prioridade sobre o resto
        if a.nome in rosca and rosca[a.nome]:
            c = Candidato(a.nome, rosca[a.nome], "regra_pdm_2", 0.92,
                          "notacao compacta M<bitola>X<comprimento>")
        return c

    def extrair(self, texto: str, classe: Classe,
                substantivo: str = "", texto_estruturado: str = "") -> dict[str, Candidato]:
        """Extrai em passadas, porque a condicao de um atributo depende do valor de outro.

        A regra 7 nao se decide numa leitura so. A coluna QUANDO_SE_APLICA cita
        VALORES de outro atributo ("somente MINIDISJUNTOR DIN" fala do TIPO),
        mas na primeira leitura nenhum valor existe ainda. Avaliando uma unica
        vez com valores desconhecidos, todo condicional governado por valor -
        e nao pelo substantivo - ficava fora da grade e NUNCA era extraido:
        PDM062 inteiro (CORRENTE NOMINAL, FAIXA AJUSTE, CURVA, CAPACIDADE
        INTERRUPCAO), PDM081 ESPESSURA e GRAO, PDM061 FURO, PDM050 SCHEDULE.
        Em 'DISJUNTOR ... MINI DISJUNTOR ... 3P IN 25A CURVA C', 'IN 25A' e
        'CURVA C' estavam escritos na linha e terminavam na sobra do texto -
        com PDM062 em 0% de SANEADO, porque validador.chave_identidade JA
        exigia esses condicionais e nunca os recebia.

        Cada passada so ACRESCENTA atributo; o que entrou na grade nao sai, e
        o valor achado numa passada nao e reextraido na seguinte. As duas
        propriedades sao deliberadas:

        - nao sair: "todas, exceto conexoes para solda de topo (BW)" fica MENOS
          aplicavel conforme o contexto cresce. Deixar a caixa cair fora
          apagaria um valor ja achado, e chave_identidade conta com ele -
          atributo preenchido que nao se aplica entra na chave de qualquer
          forma, para nao juntar itens que diferem nele.
        - nao reextrair: na primeira passada DIAMETRO de PDM081 disputa a
          familia MM sozinho e fica com o unico numero do texto; quando
          ESPESSURA entra na segunda, o numero continua onde estava e ESPESSURA
          fica honestamente vazia, em vez de as duas virarem ambiguas.
        """
        t = com_bordas(expandir(texto))
        bruto = com_bordas(texto)
        rosca = separar_rosca_metrica(texto)
        # camada 0: pares 'ATRIBUTO: VALOR' escritos na propria linha.
        # Ultimo vence quando o rotulo repete: a base as vezes corrige adiante.
        # `pares()` precisa dos dois-pontos, e o Pipeline entrega o texto ja
        # normalizado (juntar/normalizar trocam ':' por espaco). Sem receber a
        # versao estruturada, a camada 0 nunca via par nenhum: a fonte 'rotulo'
        # ficava em ZERO - a quarta camada deste projeto ligada sem efeito.
        rotulados = {nome: valor for nome, valor in pares(texto_estruturado or texto)}

        out: dict[str, Candidato] = {}
        conhecidos: dict[str, str | None] = {}
        for _ in range(PASSADAS_CONDICIONAL):
            novos = [a for a in classe.atributos
                     if a.nome not in out
                     and aplica_atributo(a, substantivo, conhecidos)]
            if not novos:
                break                 # ponto fixo: nenhuma condicao nova abriu
            for a in novos:
                out[a.nome] = self._um_atributo(t, bruto, rosca, classe, a,
                                                substantivo, conhecidos, rotulados)
            # Realimenta so o que tem valor. None nao e informacao e, pior,
            # aplica_atributo le campo vazio como "ainda nao sei" e devolve True
            # - e por isso que COR segue aplicavel enquanto NUMERO CONDUTORES
            # nao vem, em vez de ser descartada por falta de evidencia.
            conhecidos = {n: c.valor for n, c in out.items() if c.valor}
        return out
