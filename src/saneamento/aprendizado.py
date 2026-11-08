"""Dicionario aprendido: o que o LLM e o BERT resolvem nao e perguntado de novo.

O problema que isto resolve: o cache do `llm.py` e indexado por hash do TEXTO
INTEIRO, entao ele so evita rechamada no registro identico. Se 'AISI 316'
aparece em 200 descricoes diferentes, sao 200 chamadas para a mesma duvida.

Aqui a chave e o TERMO, nao o texto. Resolvido uma vez, vale para todo registro
que contenha aquele termo, em qualquer classe cujo enum aceite o valor.

    cache do llm.py            aprendizado.py
    ----------------           --------------
    sha256(texto completo)     (atributo, termo)
    evita repetir o registro   evita repetir o PROBLEMA

Duas salvaguardas, as duas vindas de bugs reais deste projeto:

1. **Validacao contra o enum na LEITURA, nunca so na escrita.** Os 93 nomes de
   atributo do PDM sao globais: 'TIPO' existe em retentor (B1|BA|BAB|BASL), em
   cabo (FLEXIVEL|RIGIDO) e em disjuntor (MINIDISJUNTOR DIN|...). Guardar
   ('TIPO','MINI DISJUNTOR') -> 'MINIDISJUNTOR DIN' e correto, mas ao ler para o
   TIPO de um retentor o valor nao esta no enum daquele atributo e e recusado.

2. **So aprende caixa TEXTUAL (vocabulario fechado).** Em caixa NUMERICA o
   mapeamento termo->valor nao generaliza: '110MM' nao significa "diametro do
   eixo", a atribuicao e posicional. Aprender isso como dicionario criaria erro
   sistematico - esse e o trabalho do BERT, nao de um dicionario.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path

from .texto import normalizar

# Termo curto demais nao vira entrada: 'C', 'D', 'A' casariam em qualquer texto.
MINIMO_TERMO = 2
# Termo longo demais e descricao inteira, nao termo: nao generaliza.
MAXIMO_TERMO = 40
# Quantos codigos de origem guardar por entrada. O que a auditoria precisa e
# poder abrir A linha que originou a regra e algumas irmas; guardar as 255 seria
# duplicar a lista de aplicacoes, que o publicador da tela ja reconstroi.
MAXIMO_ORIGENS = 20

# Rotulos que o PROPRIO pipeline grava no campo `evidencia` quando a camada que
# resolveu a caixa nao recortou trecho nenhum do texto:
#
#   regras.py:351    Candidato(..., "dicionario aprendido")
#   regras.py:470    Candidato(..., "notacao compacta M<bitola>X<comprimento>")
#   pipeline.py:234  d.evidencia = f"coluna {coluna}"
#
# Eles chegam aqui por um caminho so: `Arbitro.incorporar_llm` faz
#     d.evidencia = (evidencias or {}).get(nome, "") or d.evidencia
# e, quando o LLM nao devolve evidencia para uma caixa que ele sobrescreveu, o
# rotulo da camada anterior sobra no campo e desce direto para `aprender()` como
# se fosse o termo. No caso de 'dicionario aprendido' isso e um ciclo: o rotulo
# de procedencia do proprio dicionario volta como entrada do dicionario.
#
# Nenhum deles chega a casar em descricao real, entao o dano medido e entrada
# morta, nao valor errado - mas entrada morta mente sobre o tamanho do
# dicionario e some com a auditoria. A correcao de raiz e em arbitro.py: nao
# usar `d.evidencia` como termo quando a evidencia nao veio do LLM. Ate la, a
# barreira e aqui, que e o unico lado que eu posso editar.
ROTULOS_INTERNOS = ("DICIONARIO APRENDIDO", "NOTACAO COMPACTA", "COLUNA ")

# Marca gravada em `fonte` quando a entrada e interpretacao de dominio, nao
# traducao de notacao (ver _aponta_um_valor). Vai no `fonte` em vez de um campo
# novo de proposito: o arquivo e lido por `Entrada(**item)`, e campo novo
# quebraria qualquer versao do codigo que ainda nao o conheca.
MARCA_INTERPRETACAO = "+interpretacao"


def _palavras_norm(s: str) -> list[str]:
    return [p for p in normalizar(s).split() if p]


def _parentes(a: str, b: str) -> bool:
    """Duas palavras da mesma familia: FLANGES~FLANGE, REDUTORA~REDUTOR,
    DISJUNTOR~MINIDISJUNTOR.

    Tres criterios, do mais estrito ao mais frouxo, e o piso de 5 letras existe
    para nao casar 'ACO'~'ACOPLAMENTO' nem '316'~'31600':
      igualdade          '316' == '316' (numero curto so casa exato)
      prefixo comum      FLANGES / FLANGE
      palavra composta   DISJUNTOR dentro de MINIDISJUNTOR
    """
    if a == b:
        return True
    curto, longo = sorted((a, b), key=len)
    if len(curto) < 5:
        return False
    return longo.startswith(curto[:5]) or curto in longo


def _palavras_do_enum(atributo) -> set[str]:
    return {p for v in atributo.valores for p in _palavras_norm(v)}


def _termo_sem_ruido(atributo, termo: str) -> list[str]:
    """Palavras do termo que existem no vocabulario do enum.

    Descartar o resto e o que faz a diferenca entre reprovar e aprovar uma
    traducao legitima: o LLM devolve como evidencia o trecho inteiro do texto,
    que vem com o nome da caixa e com qualificadores que o enum nao usa -
    'ROSCA METRICA FINA' (ROSCA nao esta no enum de ROSCA), 'MONTAGEM NAO
    FACEADO', 'DIAMETRO 7/8 POL'. Comparando palavra a palavra sem limpar isso,
    nenhuma delas casava inteira e todas caiam na regra do termo generico.
    """
    enum = _palavras_do_enum(atributo)
    return [t for t in _palavras_norm(termo)
            if any(_parentes(t, p) for p in enum)]


def _valores_que_o_termo_alcanca(atributo, toks: list[str], todas: bool) -> list[str]:
    """Valores do enum compativeis com as palavras uteis do termo.

    todas=True  exige que TODA palavra util tenha parente no valor
    todas=False basta UMA palavra util com parente no valor
    """
    if not toks:
        return []
    alcanca = []
    for v in atributo.valores:
        pv = _palavras_norm(v)
        casa = [any(_parentes(t, p) for p in pv) for t in toks]
        if (all(casa) if todas else any(casa)):
            alcanca.append(v)
    return alcanca


def _aponta_um_valor(atributo, termo: str, valor: str) -> bool:
    """O termo aponta lexicalmente para UM unico valor do enum?

    E o teste que separa TRADUCAO de DECISAO, medido contra as 487 entradas
    gravadas e contra o gold de caracteristicas:

      traduz (passa)                         interpreta (reprova)
      'FEMEA 90 JIC' -> FEMEA CURVA 90 ...   'FEMEA DKO' -> FEMEA RETA DKO
      'AISI 316'     -> ACO INOX 316         'FLANGES'   -> FLANGE RF
      'ACO ZINCADO'  -> ACO CARBONO ZINCADO  'ACO ESPECIAL' -> ACO CARBONO
      'CAIXA REDUTORA' -> REDUTOR            'VOLANTE'   -> ALAVANCA
      'BSP'          -> ROSCA BSP            'MANUAL'    -> ALAVANCA

    Duas passadas porque enum composto e enum de sinonimo falham por motivos
    opostos: em 'FEMEA CURVA 90 GRAUS JIC' nenhuma palavra e exclusiva (todas
    aparecem em outro valor) e so o CONJUNTO identifica; em 'AISI 316' a
    palavra do fabricante nao existe no enum e so '316' identifica. Exigir as
    duas coisas ao mesmo tempo reprovaria uma das duas familias.

    Reprovar nao apaga nada: a entrada fica como sugestao (`revisar=True`) e o
    caminho de promocao e `exportar_para_curar` -> `sinonimos.py`, onde uma
    pessoa decide. 'BUTT WELD' -> SOLDA TOPO BW, 'MANOPLA' -> ALAVANCA e as
    siglas ('ZB', '2RS', 'BUNA-N') caem aqui: estao certas, mas nao se provam
    pelo enum. Na pratica custa pouco, porque `sinonimos.py` - que e consultado
    ANTES do dicionario - ja carrega as siglas que importam.

    Isento atributo de grandeza (BITOLA, DIAMETRO, MODELO EQUIPAMENTO): ali
    termo diferente do valor e o esperado, nao sinal de interpretacao. E a mesma
    isencao que `revalidar` usa, pelo mesmo motivo.
    """
    from .llm import _vocabulario_puro

    if normalizar(valor) not in atributo.chaves:
        return False
    if not _vocabulario_puro(atributo):
        return True
    canonico = atributo.chaves[normalizar(valor)]
    toks = _termo_sem_ruido(atributo, termo)
    por_todas = _valores_que_o_termo_alcanca(atributo, toks, todas=True)
    if len(por_todas) == 1:
        return normalizar(por_todas[0]) == normalizar(canonico)
    if por_todas:
        return False                      # alcanca dois ou mais: ambiguo
    por_alguma = _valores_que_o_termo_alcanca(atributo, toks, todas=False)
    return len(por_alguma) == 1 and normalizar(por_alguma[0]) == normalizar(canonico)


@dataclass
class Entrada:
    atributo: str
    termo: str
    valor: str
    fonte: str                      # llm | bert | manual
    confirmacoes: int = 1
    primeira_vez: str = ""
    ultima_vez: str = ""
    classes: list[str] = field(default_factory=list)   # onde foi visto
    revisar: bool = True            # ate ser confirmado N vezes ou promovido
    # Codigos de material de onde o termo veio. Sem isto, uma regra aprendida do
    # LLM e aplicada em 255 registros sem que se possa voltar a linha que a
    # provisionou - e e justo essa linha que diz se a regra era leitura ou
    # palpite. Guarda os primeiros MAXIMO_ORIGENS; `confirmacoes` conta o total.
    origens: list[str] = field(default_factory=list)

    @property
    def chave(self) -> str:
        return f"{self.atributo}|{self.termo}"


class Aprendizado:
    """Dicionario persistente alimentado pelas camadas caras do pipeline."""

    def __init__(self, caminho: str | Path | None = None,
                 confirmacoes_para_confiar: int = 2, ativo: bool = True,
                 pdm=None, congelado: bool = False, travas: bool = True):
        self.caminho = Path(caminho) if caminho else None
        # Congelado: consulta normalmente, mas nao aprende nem grava. E o modo das
        # execucoes que precisam ser reprodutiveis: sem ele, o 04_extrair aprende
        # durante a execucao (com o que o BERT recorta) e grava no fim, e duas
        # execucoes seguidas partem de dicionarios diferentes.
        self.congelado = congelado
        self.limiar_confianca = confirmacoes_para_confiar
        self.ativo = ativo
        # Travas de aplicacao (G1 a G5, descritas em consultar() e aprender()).
        # Deixar desligavel e proposital: elas mudam o que o pipeline preenche, e
        # uma execucao de comparacao precisa poder reproduzir o comportamento
        # antigo sem editar codigo - `Aprendizado(..., travas=False)`.
        self.travas = travas
        # Candidato recusado por trava: vira fila de sugestao, nao vai para o
        # lixo. Quem consome e scripts/18_curar_aprendizado.py.
        self.bloqueados: list[dict] = []
        # Opcional. Com o PDM em maos, aprender() ja barra na ESCRITA o termo que
        # e o substantivo da classe; sem ele a mesma checagem so acontece em
        # revalidar(). Ver o comentario em revalidar() para por que isso importa.
        self.pdm = pdm
        self.entradas: dict[str, Entrada] = {}
        # Indice atributo -> entradas, do termo mais longo para o mais curto.
        # Sem ele, consultar() refazia o filtro e o sorted() a cada (registro,
        # atributo): com 2.000 termos e 23.554 registros sao centenas de milhoes
        # de comparacoes so para responder o que nao muda entre chamadas.
        self._indice: dict[str, list[Entrada]] | None = None
        self.contador = {"acertos": 0, "recusados_pelo_enum": 0,
                         "aprendidos": 0, "confirmados": 0, "rejeitados": 0}
        if self.caminho and self.caminho.exists():
            self.carregar()

    # --------------------------------------------------------------- leitura

    def _por_atributo(self, nome: str) -> list["Entrada"]:
        if self._indice is None:
            indice: dict[str, list[Entrada]] = {}
            for e in self.entradas.values():
                indice.setdefault(e.atributo, []).append(e)
            for lista in indice.values():
                lista.sort(key=lambda e: -len(e.termo))
            self._indice = indice
        return self._indice.get(nome, ())

    def consultar(self, atributo, texto: str) -> str | None:
        """Valor canonico para este atributo, se algum termo aprendido casar.

        O valor SEMPRE e revalidado contra o enum do atributo recebido - e isso
        que impede o aprendizado de vazar entre classes homonimas.

        Com `travas=True` (padrao), mais duas recusas. As duas foram medidas
        contra o conjunto-ouro (avaliacao/gold_caracteristicas.csv), onde esta
        camada preenchia 70 rotulos e errava 28:

        G1 traducao  o termo tem de apontar UM unico valor do enum DESTE
                     atributo (ver `_aponta_um_valor`). Verificado na hora de
                     aplicar, nao na de aprender, e por isso a entrada vale em
                     qualquer classe onde continue verificavel - 'PRETO' ->
                     OXIDADO PRETO, aprendido em PDM001, segue valendo em
                     PDM002 - enquanto 'VOLANTE' -> 'ALAVANCA' e 'FLANGES' ->
                     'FLANGE RF' nao valem em nenhuma.
        G5 contexto  se o texto do item alcanca DOIS valores distintos do mesmo
                     atributo, o dicionario se abstem. E o caso de TERMINAL A e
                     TERMINAL B: `_por_gazetteer` recebe o texto inteiro, nao a
                     caixa do atributo, e o casamento mais longo fazia o
                     terminal B decidir o terminal A ('FEM CURVA 90 JIC'
                     ganhando de 'FEMEA BSP').

        O numero de confirmacoes deliberadamente NAO entra aqui: ele mede
        repeticao, nao evidencia. Confirmar um sorteio ('FLANGES') quatro vezes
        nao o torna leitura, e uma traducao vista uma vez ('PONTAS CHANFRADAS'
        -> SOLDA TOPO BW) ja e verificavel. Ele continua governando a confianca
        do candidato (0,93 x 0,80) via `confiavel`.

        O que e recusado nao se perde: vai para `self.bloqueados`, que o
        18_curar_aprendizado.py transforma em fila de sugestao.
        """
        if not self.ativo or not texto or not atributo.fechado:
            return None
        chaves = atributo.chaves
        t = f" {normalizar(texto)} "

        # casamento mais longo primeiro: 'ACO INOX 316' antes de 'INOX'
        achados: list[tuple[Entrada, str]] = []
        for e in self._por_atributo(atributo.nome):
            if f" {e.termo} " not in t:
                continue
            canonico = chaves.get(normalizar(e.valor))
            if canonico is None:
                # aprendido para outro atributo homonimo: recusa e segue
                self.contador["recusados_pelo_enum"] += 1
                continue
            if self.travas and not _aponta_um_valor(atributo, e.termo, canonico):
                self._bloquear(atributo, e, canonico,
                               "termo nao aponta um unico valor do enum")
                continue
            achados.append((e, canonico))
            if not self.travas:
                break

        if not achados:
            return None
        distintos = {c for _, c in achados}
        if self.travas and len(distintos) > 1:
            for e, canonico in achados:
                self._bloquear(atributo, e, canonico,
                               f"contexto alcanca {len(distintos)} valores")
            return None
        self.contador["acertos"] += 1
        return achados[0][1]

    def _bloquear(self, atributo, e: "Entrada", valor: str, motivo: str) -> None:
        self.contador["bloqueados"] = self.contador.get("bloqueados", 0) + 1
        self.bloqueados.append({"atributo": atributo.nome, "id_pdm": atributo.id_pdm,
                                "termo": e.termo, "valor": valor,
                                "confirmacoes": e.confirmacoes, "motivo": motivo})

    def origem(self, atributo: str, valor: str, texto: str) -> str | None:
        """De onde veio o termo que levou a este valor neste texto (llm, bert, manual).

        Mesma regra de casamento de consultar() (termo mais longo primeiro). Serve
        a proveniencia: o termo aprendido do LLM e aplicado como se fosse regra, e
        sem isto o valor apareceria como 'aprendido' sem dizer que, na origem,
        quem concluiu foi o LLM.
        """
        t = f" {normalizar(texto)} "
        alvo = normalizar(valor)
        for e in self._por_atributo(atributo):
            if normalizar(e.valor) == alvo and f" {e.termo} " in t:
                return e.fonte
        return None

    def confiavel(self, atributo: str, termo_ou_valor: str) -> bool:
        """Entrada ja confirmada o bastante para dispensar revisao.

        Aceita o TERMO ou o VALOR canonico, e a tolerancia nao e cosmetica: quem
        pergunta e `ExtratorLexico._por_gazetteer`, que acabou de receber de
        `consultar()` o valor canonico e nao guardou qual termo casou. Chamando
        com o valor, a busca por chave nunca achava nada e TODA entrada
        aprendida saia reportada como 'a revisar', inclusive a ja confirmada
        varias vezes - a confianca do candidato ficava presa em 0,80.

        Pelo valor a resposta e conservadora: basta um termo que leva a este
        valor ainda em revisao para a resposta ser False.
        """
        e = self.entradas.get(f"{atributo}|{normalizar(termo_ou_valor)}")
        if e is not None:
            return not e.revisar
        alvo = normalizar(termo_ou_valor)
        pelo_valor = [x for x in self._por_atributo(atributo)
                      if normalizar(x.valor) == alvo]
        return bool(pelo_valor) and all(not x.revisar for x in pelo_valor)

    # --------------------------------------------------------------- escrita

    def _substantivos(self, id_pdm: str, pdm=None) -> set[str]:
        """Substantivos da classe, se algum PDM estiver disponivel."""
        pdm = pdm or self.pdm
        if not pdm or not id_pdm:
            return set()
        classe = pdm.classes.get(id_pdm)
        return {normalizar(s) for s in classe.substantivos} if classe else set()

    @staticmethod
    def _termo_proibido(atributo, termo: str, substantivos: set[str]) -> str:
        """Motivo para o termo nunca poder ser chave, ou "" se ele pode.

        Compartilhado pela escrita (`aprender`) e pela curadoria (`revalidar`):
        termo que entrou antes de uma destas regras existir tem de sair quando
        ela passa a existir, e manter as duas listas em sincronia a mao foi
        exatamente como 'PARAFUSO' sobreviveu a primeira limpeza.
        """
        t = normalizar(termo)
        if t == normalizar(atributo.nome):
            return "termo e o nome da propria caixa"
        if any(t.startswith(r) for r in ROTULOS_INTERNOS):
            return "termo e rotulo interno do pipeline, nao trecho do texto"
        if t in substantivos:
            return "termo e o substantivo da classe, nao um valor"
        # Sujeito abreviado: 'ARR LISA' em ARRUELA, 'PARAF CAB SEXTAVADA' em
        # PARAFUSO. O LLM descreve o item e nao o atributo, e o resultado e um
        # termo que casa em toda a classe: 'ARR LISA' -> ACABAMENTO SEM
        # ACABAMENTO aplicaria "sem acabamento" a qualquer arruela lisa, que e
        # inferencia sobre o produto, nao leitura do texto. Medido nas 288
        # entradas da amostra: pega 2, nenhum falso positivo.
        primeira = t.split()[0] if t.split() else ""
        if len(primeira) >= 3 and any(
                s.startswith(primeira) or primeira.startswith(s) for s in substantivos):
            return f"termo comeca pelo sujeito da classe ({primeira})"
        return ""

    def aprender(self, atributo, termo: str, valor: str, fonte: str,
                 id_pdm: str = "", codigos: str | tuple | list = ()) -> bool:
        """Registra termo -> valor. Devolve True se entrou ou foi confirmado.

        O chamador e responsavel por so chamar com valor JA APROVADO pelo
        validador do PDM: este modulo nao reinventa a validacao, so garante que
        o valor pertence ao enum do atributo em que esta sendo gravado.

        `codigos` e a procedencia: o codigo (ou os codigos) de material em que o
        termo foi lido. Opcional para nao quebrar chamador antigo, mas sem ele a
        regra fica sem a linha que a provisionou.
        """
        if self.congelado or not self.ativo or not atributo.fechado:
            return False
        t, v = normalizar(termo), normalizar(valor)
        if not (MINIMO_TERMO <= len(t) <= MAXIMO_TERMO) or not v:
            self.contador["rejeitados"] += 1
            return False
        if normalizar(valor) not in atributo.chaves:
            self.contador["rejeitados"] += 1
            return False
        if t in atributo.chaves:
            return False            # termo ja e o proprio valor canonico: inutil
        if t == v:
            return False
        # O NOME da caixa nao e valor da caixa. O BERT recorta 'ACABAMENTO' de
        # 'ACABAMENTO: ZINCADO' e o LLM as vezes repete o rotulo como evidencia;
        # guardar isso faz o termo casar em todo registro que use o rotulo.
        if self._termo_proibido(atributo, t, self._substantivos(id_pdm)):
            self.contador["rejeitados"] += 1
            return False

        # G1: traducao de notacao entra como regra; interpretacao de dominio
        # entra como sugestao e nunca sai de `revisar` so por repeticao -
        # confirmar um sorteio quatro vezes nao o transforma em leitura.
        interpreta = self.travas and not _aponta_um_valor(atributo, t, valor)

        hoje = date.today().isoformat()
        novos = [codigos] if isinstance(codigos, str) else list(codigos)
        novos = [str(c) for c in novos if c]
        chave = f"{atributo.nome}|{t}"
        e = self.entradas.get(chave)
        if e is None:
            self.entradas[chave] = Entrada(
                atributo=atributo.nome, termo=t, valor=atributo.chaves[v],
                fonte=fonte + (MARCA_INTERPRETACAO if interpreta else ""),
                primeira_vez=hoje, ultima_vez=hoje,
                classes=[id_pdm] if id_pdm else [],
                origens=novos[:MAXIMO_ORIGENS],
            )
            self._indice = None          # entrada nova muda a ordem do casamento
            self.contador["aprendidos"] += 1
            return True

        if normalizar(e.valor) != v:
            # mesmo termo, valor diferente: conflito. Marca para revisao e NAO
            # sobrescreve - duas respostas para a mesma pergunta e sinal de que
            # o termo e ambiguo e nao devia estar no dicionario. A linha que
            # discordou entra na procedencia: e ela que a revisao precisa abrir.
            e.revisar = True
            e.fonte = f"{e.fonte}+conflito"
            self._anotar_origens(e, novos)
            self.contador["rejeitados"] += 1
            return False

        self._anotar_origens(e, novos)
        e.confirmacoes += 1
        e.ultima_vez = hoje
        if id_pdm and id_pdm not in e.classes:
            e.classes.append(id_pdm)
        if interpreta and MARCA_INTERPRETACAO not in e.fonte:
            e.fonte += MARCA_INTERPRETACAO
        if e.confirmacoes >= self.limiar_confianca \
                and MARCA_INTERPRETACAO not in e.fonte:
            e.revisar = False
        self.contador["confirmados"] += 1
        return True

    @staticmethod
    def _anotar_origens(e: "Entrada", codigos: list[str]) -> None:
        for c in codigos:
            if len(e.origens) >= MAXIMO_ORIGENS:
                return
            if c not in e.origens:
                e.origens.append(c)

    def aprender_do_llm(self, classe, decisoes, evidencias: dict[str, str],
                        codigo: str = "") -> int:
        """Varre as decisoes de um registro e guarda o que veio do LLM/BERT.

        Usa a EVIDENCIA (o trecho do texto que originou o valor) como termo.
        Sem evidencia nao aprende: usar o texto inteiro como chave nao
        generaliza e seria apenas uma copia do cache que ja existe.

        `codigo` e o registro de onde a evidencia foi lida: e a linha que a
        regra vai citar como procedencia.
        """
        n = 0
        por_nome = {a.nome: a for a in classe.atributos}
        for d in decisoes.values():
            if d.fonte not in ("llm", "bert", "bert_desempata") or not d.valor:
                continue
            atributo = por_nome.get(d.atributo)
            if atributo is None:
                continue
            termo = evidencias.get(d.atributo) or d.evidencia
            if not termo:
                continue
            if self.aprender(atributo, termo, d.valor,
                             "llm" if d.fonte == "llm" else "bert", classe.id_pdm,
                             codigos=codigo):
                n += 1
        return n

    # --------------------------------------------------------------- curadoria

    def revalidar(self, pdm) -> list[tuple["Entrada", str]]:
        """Reaplica as travas de llm.py a um dicionario JA gravado e descarta o
        que elas reprovam. Devolve [(entrada, motivo)] do que saiu.

        Existe porque as travas sao de ESCRITA e o arquivo sobrevive ao codigo:
        termo aprendido antes de uma trava existir continuaria sendo consultado
        para sempre. Rodar isto depois de endurecer uma trava e o equivalente,
        para o dicionario, de reprocessar a base - mas sem pagar chamada.

        Nao substitui curadoria humana. Reprova so o que e verificavel contra o
        enum (numero trocado, trecho que serve a dois valores); erro de dominio
        como 'ACO LIGA' -> ACO CARBONO passa por aqui intacto, porque nada no
        PDM diz que esta errado - so quem conhece aco diz.
        """
        from .llm import _compacto, _digitos, _palavras, _vocabulario_puro

        fora: list[tuple[Entrada, str]] = []
        for chave, e in list(self.entradas.items()):
            # Qualquer atributo da classe serve para as regras de TERMO: elas
            # olham o nome da caixa e o sujeito da classe, nao o enum.
            qualquer = None
            alvos = []
            for cid in e.classes:
                classe = pdm.classes.get(cid)
                if classe is None:
                    continue
                for x in classe.atributos:
                    if x.nome != e.atributo:
                        continue
                    qualquer = qualquer or x
                    if _vocabulario_puro(x):
                        alvos.append(x)

            # Regras de TERMO primeiro, e fora do portao de vocabulario: elas
            # valem tambem em caixa de grandeza. Era por isso que
            # BITOLA 'DICIONARIO APRENDIDO' -> '1POL' sobrevivia a limpeza -
            # BITOLA nao e vocabulario puro, entao `alvos` ficava vazio e a
            # entrada era pulada antes de qualquer checagem.
            substantivos = {normalizar(s) for cid in e.classes
                            for s in self._substantivos(cid, pdm)}
            motivo = ""
            if qualquer is not None:
                motivo = self._termo_proibido(qualquer, e.termo, substantivos)

            if not motivo and not alvos:
                continue
            dig_t, dig_v = _digitos(e.termo), _digitos(e.valor)
            if motivo:
                pass
            elif dig_t and dig_v and not dig_t <= dig_v:
                motivo = "gemeo numerico"
            else:
                for a in alvos:
                    t, pal = _compacto(e.termo), _palavras(e.termo)
                    if len([v for v in a.valores if t in _compacto(v)]) >= 2:
                        motivo = "trecho serve a dois valores do enum"
                    elif len([v for v in a.valores if pal and pal <= _palavras(v)]) >= 2:
                        motivo = "palavras do trecho cabem em dois valores do enum"
                    if motivo:
                        break
            if motivo:
                del self.entradas[chave]
                self._indice = None
                fora.append((e, motivo))
        return fora

    def curar(self, pdm) -> list[tuple["Entrada", str]]:
        """Aplica G1 e G2 ao dicionario JA gravado, REBAIXANDO em vez de apagar.

        Diferenca de `revalidar`, que deleta: ali o motivo e verificavel contra o
        enum (numero trocado, rotulo interno) e a entrada nao serve a ninguem.
        Aqui o motivo e "nao da para provar que e traducao" - a entrada pode
        estar certa ('BUTT WELD' -> SOLDA TOPO BW esta), so nao pode virar regra
        automatica. Rebaixada, ela continua no arquivo, para de ser aplicada
        (G4 em consultar) e aparece em `exportar_para_curar` como candidata.

        G2 e o caso 'VOLANTE' -> 'ALAVANCA': termo que E valor legitimo do mesmo
        atributo em classe irma. A guarda de classe (G3) ja impede a aplicacao
        fora da classe de origem, mas a entrada em si e um convite a erro e fica
        marcada.

        Devolve [(entrada, motivo)] do que foi rebaixado.
        """
        rebaixadas: list[tuple[Entrada, str]] = []
        for e in self.entradas.values():
            alvos, irmas = [], set()
            for cid, classe in pdm.classes.items():
                for x in classe.atributos:
                    if x.nome != e.atributo or not x.fechado:
                        continue
                    if cid in e.classes:
                        alvos.append(x)
                    elif normalizar(e.termo) in x.chaves:
                        irmas.add(cid)
            motivo = ""
            if irmas and not any(normalizar(e.termo) in a.chaves for a in alvos):
                motivo = ("termo e valor valido deste atributo em "
                          + ", ".join(sorted(irmas)))
            elif alvos and not any(_aponta_um_valor(a, e.termo, e.valor)
                                   for a in alvos):
                motivo = "termo nao aponta um unico valor do enum (interpretacao)"
            if not motivo:
                continue
            if MARCA_INTERPRETACAO not in e.fonte:
                e.fonte += MARCA_INTERPRETACAO
            if not e.revisar:
                e.revisar = True
                rebaixadas.append((e, motivo))
        return rebaixadas

    # --------------------------------------------------------------- io

    def salvar(self) -> None:
        if not self.caminho or self.congelado:
            return
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "versao": 1,
            "limiar_confianca": self.limiar_confianca,
            "entradas": [asdict(e) for e in sorted(self.entradas.values(),
                                                   key=lambda x: (x.atributo, x.termo))],
        }
        self.caminho.write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                encoding="utf-8")

    def carregar(self) -> None:
        d = json.loads(self.caminho.read_text(encoding="utf-8"))
        self.entradas = {}
        self._indice = None
        # Campo que esta versao nao conhece e ignorado em vez de estourar em
        # TypeError. Era por esse risco que `+interpretacao` foi parar dentro de
        # `fonte` em vez de virar campo proprio: um dicionario gravado por uma
        # versao mais nova derrubava a mais antiga na leitura. Com o filtro, o
        # arquivo volta a ser compativel nos dois sentidos.
        conhecidos = {f.name for f in fields(Entrada)}
        for item in d.get("entradas", []):
            e = Entrada(**{k: v for k, v in item.items() if k in conhecidos})
            self.entradas[e.chave] = e

    # --------------------------------------------------------------- relatorio

    def estatisticas(self) -> dict:
        confiaveis = [e for e in self.entradas.values() if not e.revisar]
        por_fonte: dict[str, int] = {}
        for e in self.entradas.values():
            por_fonte[e.fonte] = por_fonte.get(e.fonte, 0) + 1
        return {
            "entradas": len(self.entradas),
            "confiaveis": len(confiaveis),
            "a_revisar": len(self.entradas) - len(confiaveis),
            "por_fonte": por_fonte,
            **self.contador,
        }

    def exportar_para_curar(self, destino: str | Path) -> int:
        """Gera um .py no formato de sinonimos.py com o que ja e confiavel.

        O caminho de promocao e manual de proposito: entrada aprendida que virou
        codigo curado passa a ser revisada por pessoa e versionada no git.
        """
        confiaveis = [e for e in self.entradas.values() if not e.revisar]
        por_valor: dict[tuple[str, str], list[str]] = {}
        for e in confiaveis:
            por_valor.setdefault((e.atributo, e.valor), []).append(e.termo)
        linhas = ['"""Termos aprendidos pelo pipeline, candidatos a entrar em sinonimos.py.',
                  "",
                  "Gerado por Aprendizado.exportar_para_curar(). REVISAR antes de promover.",
                  '"""', "", "CANDIDATOS = ["]
        for (attr, valor), termos in sorted(por_valor.items()):
            t = ", ".join(repr(x) for x in sorted(termos))
            linhas.append(f"    # {attr}")
            linhas.append(f"    ({valor!r}, [{t}]),")
        linhas.append("]")
        Path(destino).write_text("\n".join(linhas) + "\n", encoding="utf-8")
        return len(confiaveis)
