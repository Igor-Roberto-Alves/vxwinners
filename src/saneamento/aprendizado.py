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
                 confirmacoes_para_confiar: int = 2, ativo: bool = True):
        self.caminho = Path(caminho) if caminho else None
        self.limiar_confianca = confirmacoes_para_confiar
        self.ativo = ativo
        self.entradas: dict[str, Entrada] = {}
        self.contador = {"acertos": 0, "recusados_pelo_enum": 0,
                         "aprendidos": 0, "confirmados": 0, "rejeitados": 0}
        if self.caminho and self.caminho.exists():
            self.carregar()

    # --------------------------------------------------------------- leitura

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
        candidatas = sorted(
            (e for e in self.entradas.values() if e.atributo == atributo.nome),
            key=lambda e: -len(e.termo),
        )
        for e in candidatas:
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

    def confiavel(self, atributo: str, termo: str) -> bool:
        e = self.entradas.get(f"{atributo}|{normalizar(termo)}")
        return bool(e and not e.revisar)

    # --------------------------------------------------------------- escrita

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

        hoje = date.today().isoformat()
        chave = f"{atributo.nome}|{t}"
        e = self.entradas.get(chave)
        if e is None:
            self.entradas[chave] = Entrada(
                atributo=atributo.nome, termo=t, valor=atributo.chaves[v],
                fonte=fonte, primeira_vez=hoje, ultima_vez=hoje,
                classes=[id_pdm] if id_pdm else [],
            )
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
