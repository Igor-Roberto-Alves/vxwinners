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
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .texto import normalizar

# Termo curto demais nao vira entrada: 'C', 'D', 'A' casariam em qualquer texto.
MINIMO_TERMO = 2
# Termo longo demais e descricao inteira, nao termo: nao generaliza.
MAXIMO_TERMO = 40

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

    @property
    def chave(self) -> str:
        return f"{self.atributo}|{self.termo}"


class Aprendizado:
    """Dicionario persistente alimentado pelas camadas caras do pipeline."""

    def __init__(self, caminho: str | Path | None = None,
                 confirmacoes_para_confiar: int = 2, ativo: bool = True,
                 pdm=None):
        self.caminho = Path(caminho) if caminho else None
        self.limiar_confianca = confirmacoes_para_confiar
        self.ativo = ativo
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
        """
        if not self.ativo or not texto or not atributo.fechado:
            return None
        chaves = atributo.chaves
        t = f" {normalizar(texto)} "

        # casamento mais longo primeiro: 'ACO INOX 316' antes de 'INOX'
        for e in self._por_atributo(atributo.nome):
            if f" {e.termo} " not in t:
                continue
            canonico = chaves.get(normalizar(e.valor))
            if canonico is None:
                # aprendido para outro atributo homonimo: recusa e segue
                self.contador["recusados_pelo_enum"] += 1
                continue
            self.contador["acertos"] += 1
            return canonico
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
                 id_pdm: str = "") -> bool:
        """Registra termo -> valor. Devolve True se entrou ou foi confirmado.

        O chamador e responsavel por so chamar com valor JA APROVADO pelo
        validador do PDM: este modulo nao reinventa a validacao, so garante que
        o valor pertence ao enum do atributo em que esta sendo gravado.
        """
        if not self.ativo or not atributo.fechado:
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

        hoje = date.today().isoformat()
        chave = f"{atributo.nome}|{t}"
        e = self.entradas.get(chave)
        if e is None:
            self.entradas[chave] = Entrada(
                atributo=atributo.nome, termo=t, valor=atributo.chaves[v],
                fonte=fonte, primeira_vez=hoje, ultima_vez=hoje,
                classes=[id_pdm] if id_pdm else [],
            )
            self._indice = None          # entrada nova muda a ordem do casamento
            self.contador["aprendidos"] += 1
            return True

        if normalizar(e.valor) != v:
            # mesmo termo, valor diferente: conflito. Marca para revisao e NAO
            # sobrescreve - duas respostas para a mesma pergunta e sinal de que
            # o termo e ambiguo e nao devia estar no dicionario.
            e.revisar = True
            e.fonte = f"{e.fonte}+conflito"
            self.contador["rejeitados"] += 1
            return False

        e.confirmacoes += 1
        e.ultima_vez = hoje
        if id_pdm and id_pdm not in e.classes:
            e.classes.append(id_pdm)
        if e.confirmacoes >= self.limiar_confianca:
            e.revisar = False
        self.contador["confirmados"] += 1
        return True

    def aprender_do_llm(self, classe, decisoes, evidencias: dict[str, str]) -> int:
        """Varre as decisoes de um registro e guarda o que veio do LLM/BERT.

        Usa a EVIDENCIA (o trecho do texto que originou o valor) como termo.
        Sem evidencia nao aprende: usar o texto inteiro como chave nao
        generaliza e seria apenas uma copia do cache que ja existe.
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
                             "llm" if d.fonte == "llm" else "bert", classe.id_pdm):
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

    # --------------------------------------------------------------- io

    def salvar(self) -> None:
        if not self.caminho:
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
        for item in d.get("entradas", []):
            e = Entrada(**item)
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
